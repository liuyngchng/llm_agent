#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import os
import time
from typing import List, Dict

import requests

from common.vdb_meta_util import VdbMeta
from common.cfg_util import get_usr_prompt_template
from common.cm_utils import estimate_tokens
from common.docx_md_util import get_md_file_content, convert_md_to_docx, save_content_to_md_file, get_md_file_catalogue, \
    convert_docx_to_md, extract_sections_content, split_md_file_with_catalogue, split_md_content_with_catalogue
import logging.config

from common.docx_meta_util import update_process_info, get_doc_info
from common.my_enums import FileType
from common.statistic_util import add_input_token_by_uid, add_output_token_by_uid
from common.sys_init import init_yml_cfg
from common.vdb_util import search_txt
from common.xlsx_util import convert_md_to_xlsx, convert_xlsx_to_md
from common.const import MAX_SECTION_LENGTH, VDB_PREFIX

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

# 关闭request请求产生的警告信息 (客户端没有进行服务端 SSL 的证书验证，正常会产生警告信息)， 只要清楚自己在做什么
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(category=InsecureRequestWarning)

class PaperReviewer:
    def __init__(self, uid: int, task_id: int, review_type: str, review_topic:str,
         criteria_markdown_data: str, review_file_path: str, criteria_file_type, sys_cfg: dict):
        """
        分章节评审系统
        :param uid: 用户ID，标记哪个用户提交的任务
        :param task_id: 任务ID， 标记是哪个任务
        :param review_type: 评审类型, 例如 信息系统概要设计评审
        :param review_topic: 评审主题， 例如 xxxx系统概要涉及评审
        :param criteria_markdown_data: 评审标准 markdown 文本
        :param review_file_path: 评审文件 markdown 路径
        :param criteria_file_type: 评审标准的文件类型
        :param sys_cfg: 系统配置
        """
        self.uid = uid
        self.task_id = task_id
        self.review_type = review_type
        self.review_topic = review_topic
        self.criteria_markdown_data = criteria_markdown_data
        self.criteria_file_type = criteria_file_type
        self.review_file_path = review_file_path
        self.sections_data = []
        self.review_results = []
        self.sys_cfg = sys_cfg



    def review_single_section(self, section_title: str, section_content: str, vdb_dir: str, max_retries: int = 3) -> Dict:
        """
        评审单个章节，带重试机制
        """
        for attempt in range(max_retries):
            try:
                template_name = "section_review_msg"
                template = get_usr_prompt_template(template_name, self.sys_cfg)
                if not template:
                    err_info = f"prompt_template_config_err, {template_name}"
                    raise RuntimeError(err_info)
                reference = get_reference_from_vdb(section_content, vdb_dir, self.sys_cfg['api'])
                logger.info(f"review_single_section_get_reference, {reference}, for_section_content, {section_content}")
                prompt = template.format(
                    review_type = self.review_type,
                    review_topic=self.review_topic,
                    section_title=section_title,
                    section_content=section_content,
                    criteria=self.criteria_markdown_data,
                    reference = reference,
                )
                input_tokens = estimate_tokens(prompt)
                logger.info(f"{self.uid}, input_tokens, {input_tokens}")
                add_input_token_by_uid(self.uid, input_tokens)
                result = self.call_llm_api(prompt)
                output_tokens = estimate_tokens(json.dumps(result))
                logger.info(f"{self.uid}, output_tokens, {output_tokens}")
                add_output_token_by_uid(self.uid, output_tokens)
                # 验证结果格式
                PaperReviewer._validate_review_result(result)
                return result

            except Exception as e:
                logger.exception(f"第{attempt + 1}次评审章节[{section_title}]失败")
                if attempt == max_retries - 1:
                    # 最后一次尝试失败，返回基础评审结果
                    return self._get_fallback_result(section_title, str(e))
                time.sleep(1)  # 重试前等待
        logger.error("nothing_return_here, pay attention.")
        return {}

    def call_llm_api(self, prompt: str) -> dict:
        """直接调用LLM API，支持流式输出"""
        key = self.sys_cfg['api']['llm_api_key']
        model = self.sys_cfg['api']['llm_model_name']
        uri = f"{self.sys_cfg['api']['llm_api_uri']}/chat/completions"
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}'
            }

            # 构建消息
            messages = [
                {"role": "user", "content": prompt}
            ]

            # 构建请求体
            payload = {
                'model': model,
                'messages': messages,
                'temperature': 0.7,  # 降低温度以获得更稳定的JSON输出
                'response_format': {"type": "json_object"}  # 强制JSON格式输出
            }
            logger.info(f"start_request, {uri}, {model}, 提示词: {prompt[:400]}")
            response = requests.post(
                url=uri,
                headers=headers,
                json=payload,
                timeout=60,
                verify=False,
            )
            logger.info(f"response_status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                logger.info(f"LLM 响应解析成功")

                # 提取LLM返回的内容
                content = result['choices'][0]['message']['content']
                logger.debug(f"LLM返回的原始内容: {content}")

                try:
                    # 尝试直接解析JSON
                    if content.strip().startswith('```json'):
                        # 如果包含代码块，提取JSON部分
                        json_str = content.strip().replace('```json', '').replace('```', '').strip()
                        parsed_result = json.loads(json_str)
                    else:
                        # 直接解析
                        parsed_result = json.loads(content)

                    logger.info(f"成功解析LLM返回的JSON: {parsed_result}")
                    return parsed_result

                except json.JSONDecodeError as e:
                    logger.error(f"解析LLM返回的JSON失败: {str(e)}")
                    logger.error(f"原始内容: {content}")
                    # 返回降级结果
                    return {
                        "score": 0,
                        "strengths": ["内容结构完整"],
                        "issues": [f"AI评审解析失败: {str(e)}", "建议人工复核"],
                        "suggestions": ["请专家人工评审该章节"],
                        "risk_level": "未知"
                    }
            else:
                error_msg = f"LLM API调用失败:{uri}, {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    "score": 0,
                    "strengths": ["章节结构完整"],
                    "issues": [f"LLM API调用失败: {response.status_code}- {response.text}"],
                    "suggestions": ["请专家人工评审该章节"],
                    "risk_level": "未知"
                }
        except Exception as e:
            error_msg = f"LLM API调用异常: {uri}, {str(e)}"
            logger.error(error_msg)
            return {
                "score": 0,
                "strengths": ["章节结构完整"],
                "issues": [f"API调用异常: {str(e)}"],
                "suggestions": ["请专家人工评审该章节"],
                "risk_level": "未知"
            }

    @staticmethod
    def _validate_review_result(result: Dict):
        """验证评审结果格式"""
        required_fields = ['score', 'strengths', 'issues', 'suggestions']
        for field in required_fields:
            if field not in result:
                raise ValueError(f"评审结果缺少必要字段: {field}")

        if not isinstance(result['score'], int) or not (0 <= result['score'] <= 100):
            raise ValueError("评分必须在0-100之间")

    @staticmethod
    def _get_fallback_result(section_title: str, error_msg: str) -> Dict:
        """获取降级评审结果"""
        return {
            "score": 60,
            "strengths": ["章节结构完整"],
            "issues": [f"评审过程中出现技术问题: {error_msg}", "建议人工复核"],
            "suggestions": ["请专家人工评审该章节"],
            "risk_level": "未知",
            "review_failed": True
        }

    def review_whole_report(self, section_results: List[Dict]) -> Dict:
        """
        根据各个章节的评审结果，进行整体评审
        """
        try:
            # 生成各章节概要
            section_summaries = []
            for result in section_results:
                summary = {
                    'title': result['section_title'],
                    'score': result['score'],
                    'main_issues': result['issues'][:2] if result['issues'] else [],
                    'risk_level': result.get('risk_level', '未知')
                }
                section_summaries.append(summary)
            template_name = "paper_review_msg"
            template = get_usr_prompt_template(template_name, self.sys_cfg)
            if not template:
                err_info = f"prompt_template_config_err, {template_name}"
                raise RuntimeError(err_info)
            prompt = template.format(
                review_type = self.review_type,
                review_topic = self.review_topic,
                section_summary = json.dumps(section_summaries, ensure_ascii=False, indent=2),
                criteria = self.criteria_markdown_data,
            )
            input_tokens = estimate_tokens(prompt)
            logger.info(f"{self.uid}, input_tokens, {input_tokens}")
            add_input_token_by_uid(self.uid, input_tokens)
            overall_result = self.call_llm_api(prompt)
            output_tokens = estimate_tokens(json.dumps(overall_result))
            logger.info(f"{self.uid}, output_tokens, {output_tokens}")
            add_output_token_by_uid(self.uid, output_tokens)
            # 添加结果验证和降级处理
            if not overall_result or 'overall_score' not in overall_result:
                logger.warning("整体评审返回结果格式异常，使用降级结果")
                return PaperReviewer._get_fallback_overall_result(section_results)
            return overall_result

        except Exception as e:
            logger.error(f"整体评审失败: {str(e)}")
            return PaperReviewer._get_fallback_overall_result(section_results)

    @staticmethod
    def _get_fallback_overall_result(section_results: List[Dict]) -> Dict:
        """获取整体评审的降级结果"""
        try:
            # 计算平均分
            avg_score = sum(r['score'] for r in section_results) // len(section_results) if section_results else 60

            return {
                "overall_score": avg_score,
                "overall_strengths": ["报告结构完整"],
                "overall_issues": ["整体评审过程出现技术问题，建议人工复核"],
                "key_recommendations": ["建议专家对整篇报告进行人工评审"],
                "review_summary": f"报告各章节平均评分为{avg_score}分。由于技术原因，整体评审未能完成，建议专家人工复核整篇报告。"
            }
        except Exception as e:
            logger.error(f"生成降级整体结果失败: {str(e)}")
            return {
                "overall_score": 60,
                "overall_strengths": [],
                "overall_issues": ["评审系统出现技术故障"],
                "key_recommendations": ["请专家进行完整人工评审"],
                "review_summary": "评审系统出现技术问题，建议专家进行完整人工评审。"
            }

    def generate_final_report(self, section_results: List[Dict], overall_result: Dict) -> str:
        """
        生成最终评审报告的内容
        """
        try:
            report_content = f"""# 【 {self.review_topic} 】 评审报告

## 评审概述
- 评审时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- 整体评分: {overall_result['overall_score']}/100
- 评审结论: {'通过' if overall_result['overall_score'] >= 60 else '需要修改'}

## 整体评价
{overall_result['review_summary']}

### 主要优势
{chr(10).join(f"- {strength}" for strength in overall_result['overall_strengths'])}

### 主要问题  
{chr(10).join(f"- {issue}" for issue in overall_result['overall_issues'])}

### 关键建议
{chr(10).join(f"- {recommendation}" for recommendation in overall_result['key_recommendations'])}

## 各章节评审结果
"""

            for section_result in section_results:
                report_content += f"""
### {section_result['section_title']}
- **评分**: {section_result['score']}/100
- **风险等级**: {section_result.get('risk_level', '未知')}

#### 优点
{chr(10).join(f"  - {strength}" for strength in section_result['strengths'])}

#### 问题
{chr(10).join(f"  - {issue}" for issue in section_result['issues'])}

#### 改进建议
{chr(10).join(f"  - {suggestion}" for suggestion in section_result['suggestions'])}

"""

            report_content += """
## 评审说明
本评审报告由AI系统生成，建议结合专家人工评审最终确定。
"""

            return report_content

        except Exception as e:
            logger.error(f"生成最终报告失败: {str(e)}")
            return f"# 评审报告生成失败\n\n错误信息: {str(e)}\n\n请联系技术支持。"

    def execute_review(self) -> str:
        """
        执行完整的评审流程，返回生成的报告文本
        """
        try:
            logger.info("开始执行文档评审流程")

            # 1. 解析目录结构
            catalogue = get_md_file_catalogue(self.review_file_path)
            if not catalogue:
                info = f"无法解析文档目录结构, {self.review_file_path}"
                raise ValueError(info)
            logger.info(f"文档目录，{catalogue}")
            update_process_info(self.uid, self.task_id, "开始解析章节内容...")

            # 2. 提取章节内容
            # extract_sections_content 返回的数据格式： [{"heading1->header2" : ["content_part1 under heading2", "content_part2 under heading2"]}]
            self.sections_data = extract_sections_content(self.review_file_path, catalogue,
                                                          max_content_length=MAX_SECTION_LENGTH)
            if not self.sections_data:
                raise ValueError("无法提取章节内容")
            logger.debug(f"章节内容，{self.sections_data}")

            # 计算总章节数（包括分割后的部分）
            total_sections = 0
            for section in self.sections_data:
                for title, content_parts in section.items():
                    total_sections += len(content_parts)

            doc_info = get_doc_info(self.task_id)
            if not doc_info or not doc_info[0]:
                info = f"no_doc_info_found_for_task_id ,{self.task_id}"
                raise RuntimeError(info)
            vdb_id = doc_info[0]['vdb_id']
            vdb_info = VdbMeta.get_vdb_info_by_id(vdb_id)
            if vdb_info:
                my_vector_db_dir = f"{VDB_PREFIX}{vdb_info[0]['uid']}_{vdb_id}"
            else:
                my_vector_db_dir = ""
            logger.info(f"my_vector_db_dir {my_vector_db_dir}")
            logger.info(f"开始逐章节评审，共 {len(self.sections_data)} 个原始章节，{total_sections} 个内容部分")

            # 3. 逐章节评审
            processed_parts = 0
            for i, section in enumerate(self.sections_data):
                # 每个section是一个字典：{"heading1->header2": ["content_part1", "content_part2", ...]}
                for section_title, content_parts in section.items():
                    logger.info(
                        f"评审章节 {i + 1}/{len(self.sections_data)}: {section_title} (包含{len(content_parts)}个部分)")

                    # 对每个内容部分进行评审
                    for part_index, content_part in enumerate(content_parts):
                        processed_parts += 1
                        current_percent = min(95.0, round(processed_parts / total_sections * 100, 1))

                        part_description = f"第{part_index + 1}部分" if len(content_parts) > 1 else "完整内容"
                        process_info = f"正在评审章节 {section_title} 的{part_description} ({processed_parts}/{total_sections})"
                        update_process_info(self.uid, self.task_id, process_info, current_percent)

                        # 构建完整的部分标题（包含部分信息）
                        full_section_title = f"{section_title} [第{part_index + 1}部分]" if len(
                            content_parts) > 1 else section_title

                        logger.debug(f"评审内容部分: {full_section_title}, 长度: {len(content_part)}")

                        section_result = self.review_single_section(full_section_title, content_part, my_vector_db_dir)
                        section_result['section_title'] = section_title  # 保存原始标题
                        section_result['part_index'] = part_index
                        section_result['total_parts'] = len(content_parts)
                        self.review_results.append(section_result)
                        logger.info(f"章节[{full_section_title}]评审完成，评分: {section_result['score']}")

            # 4. 合并同一章节的多个部分结果
            merged_results = PaperReviewer._merge_section_results(self.review_results)
            # 5. 整体评审
            logger.info("总结评审意见")
            update_process_info(self.uid, self.task_id, "开始总结评审意见")
            overall_result = self.review_whole_report(merged_results)

            # 6. 生成最终报告
            logger.info("生成最终评审报告")
            final_report = self.generate_final_report(merged_results, overall_result)
            if FileType.XLSX.value == self.criteria_file_type:
                update_process_info(self.uid, self.task_id, "生成格式化的评审报告")
                logger.debug(f"fill_all_formatted_markdown_report_with_final_report\n{final_report}")
                formatted_report = self.fill_all_formatted_markdown_report_with_final_report(final_report)
            else:
                formatted_report = final_report
            logger.info("文档评审流程完成")
            return formatted_report

        except Exception as e:
            logger.exception(f"评审流程执行失败")
            return f"# 评审过程出现错误\n\n错误信息: {str(e)}\n\n请检查文档格式或联系技术支持。"

    @staticmethod
    def _merge_section_results(all_results: List[Dict]) -> List[Dict]:
        """
        合并同一章节的多个部分评审结果

        Args:
            all_results: 所有部分的评审结果

        Returns:
            合并后的章节评审结果
        """
        merged_results = {}

        for result in all_results:
            section_title = result['section_title']
            part_index = result.get('part_index', 0)
            total_parts = result.get('total_parts', 1)

            if section_title not in merged_results:
                # 初始化章节结果
                merged_results[section_title] = {
                    'section_title': section_title,
                    'scores': [],
                    'strengths': [],
                    'issues': [],
                    'suggestions': [],
                    'risk_levels': [],
                    'part_count': total_parts
                }

            # 收集各部分结果
            merged_results[section_title]['scores'].append(result['score'])
            merged_results[section_title]['strengths'].extend(result['strengths'])
            merged_results[section_title]['issues'].extend(result['issues'])
            merged_results[section_title]['suggestions'].extend(result['suggestions'])
            merged_results[section_title]['risk_levels'].append(result.get('risk_level', '未知'))

        # 生成最终合并结果
        final_results = []
        for section_title, data in merged_results.items():
            # 计算平均分
            avg_score = sum(data['scores']) // len(data['scores'])

            # 去重并保留重要信息
            unique_strengths = list(dict.fromkeys(data['strengths']))  # 保持顺序去重
            unique_issues = list(dict.fromkeys(data['issues']))
            unique_suggestions = list(dict.fromkeys(data['suggestions']))

            # 确定主要风险等级（取最严重的）
            risk_levels = data['risk_levels']
            risk_priority = {'高': 3, '中': 2, '低': 1, '未知': 0}
            main_risk_level = max(risk_levels, key=lambda x: risk_priority.get(x, 0))

            final_result = {
                'section_title': section_title,
                'score': avg_score,
                'strengths': unique_strengths[:5],  # 限制数量，取前5个
                'issues': unique_issues[:10],  # 限制数量，取前10个
                'suggestions': unique_suggestions[:5],  # 限制数量，取前5个
                'risk_level': main_risk_level,
                'original_parts_count': data['part_count']
            }

            final_results.append(final_result)

            logger.info(f"合并章节[{section_title}]结果: 平均分{avg_score}, 原始部分数{data['part_count']}")

        return final_results

    def fill_all_formatted_markdown_report_with_final_report(self, final_report_txt: str) -> str:
        """
        使用大语言模型将最终评审结果自动填写到标准格式的评审表格中

        Args:
            final_report_txt: 生成的最终评审报告文本

        Returns:
            填充后的格式化评审报告文本
        """
        split_md_list = split_md_content_with_catalogue(self.criteria_markdown_data)
        logger.debug(f"split_md_list, {split_md_list}")
        all_txt = ""
        for md in split_md_list:
            single_title = md['title']
            single_criteria = md['content']
            logger.debug(f"get_single_criteria_md, \n{single_criteria}")
            single_report = self.fill_md_table(final_report_txt, single_title, single_criteria)
            all_txt = all_txt  + "\n\n" + single_report
        return all_txt

    def fill_md_table(self, conclusion: str, single_criteria_title: str, single_criteria: str) -> str:
        """
        使用大语言模型将最终评审结果自动填写到标准格式的评审表格中

        Args:
            conclusion: 生成的最终评审结论
            single_criteria_title: 评审标准中的一个表格的标题
            single_criteria: 评审标准中的一个表格

        Returns:
            填充后的格式化评审报告文本
        """
        template_name = "fill_md_table_msg"
        template = get_usr_prompt_template(template_name, self.sys_cfg)
        if not template:
            err_info = f"prompt_template_config_err, {template_name}"
            raise RuntimeError(err_info)
        prompt = template.format(
            review_type = self.review_type,
            review_topic = self.review_topic,
            criteria=single_criteria,
            conclusion=conclusion,
        )
        try:
            logger.info(f"开始使用LLM将评审结果填充到标准格式表格中, title={single_criteria_title}")
            # 调用大语言模型API
            start_time = time.time()
            filled_report = self.call_llm_api_for_formatting(prompt)
            end_time = time.time()
            execution_time = end_time - start_time
            # 验证返回结果
            if filled_report and self._is_valid_filled_report(filled_report):
                logger.info(f"成功生成格式化评审报告, 耗时: {execution_time:.2f} 秒, title={single_criteria_title}")
                return filled_report
            else:
                logger.warning("LLM返回的格式化报告不完整，返回原始报告")
                return conclusion

        except Exception as e:
            logger.error(f"使用LLM填充格式化报告失败: {str(e)}")
        # 如果填充失败，返回原始报告
        return conclusion

    def call_llm_api_for_formatting(self, prompt: str, max_retries: int = 2) -> str:
        """专门用于格式化报告的大语言模型调用，增加重试机制"""
        key = self.sys_cfg['api']['llm_api_key']
        model = self.sys_cfg['api']['llm_model_name']
        uri = f"{self.sys_cfg['api']['llm_api_uri']}/chat/completions"

        for attempt in range(max_retries):
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {key}'
                }

                # 构建消息
                messages = [
                    {"role": "system",
                     "content": f"你是一个专业的 {self.review_topic} 文档评审专家，擅长将评审结果按照标准表格格式进行整理和填写。请严格按照给定的表格格式要求进行操作。"},
                    {"role": "user", "content": prompt}
                ]

                # 构建请求体 - 优化参数
                payload = {
                    'model': model,
                    'messages': messages,
                    'temperature': 0.1,
                    'max_tokens': 8192,
                    'stream': False  # 确保非流式响应
                }

                logger.info(f"开始调用LLM进行报告格式化 (第{attempt + 1}次尝试)")

                # 动态调整超时时间
                timeout = 300 if attempt == 0 else 600  # 第一次180秒，重试时300秒

                response = requests.post(
                    url=uri,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    verify=False,
                )

                logger.info(f"LLM格式化响应状态: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']

                    # 清理返回内容
                    if content.strip().startswith('```'):
                        lines = content.strip().split('\n')
                        if lines[0].startswith('```'):
                            lines = lines[1:]
                        if lines and lines[-1].startswith('```'):
                            lines = lines[:-1]
                        content = '\n'.join(lines).strip()

                    logger.info(f"成功获取LLM格式化的报告，长度: {len(content)}")
                    return content

                else:
                    error_msg = f"LLM格式化API调用失败: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    if attempt == max_retries - 1:
                        return ""
                    time.sleep(2)  # 重试前等待

            except requests.exceptions.Timeout:
                logger.warning(f"第{attempt + 1}次调用LLM API超时")
                if attempt == max_retries - 1:
                    logger.error("所有重试尝试均超时")
                    return ""
                time.sleep(3)  # 超时后等待更长时间

            except Exception as e:
                error_msg = f"LLM格式化API调用异常 (第{attempt + 1}次): {str(e)}"
                logger.error(error_msg)
                if attempt == max_retries - 1:
                    return ""
                time.sleep(2)

        return ""


    @staticmethod
    def _is_valid_filled_report(report: str) -> bool:
        """
        验证填充后的报告是否有效
        """
        if not report or len(report.strip()) < 100:
            return False

        # 检查是否包含表格特征
        table_indicators = ['|', '---', '评分', '得分', '评审意见']
        indicators_found = sum(1 for indicator in table_indicators if indicator in report)

        # 如果找到至少2个表格特征，认为报告有效
        return indicators_found >= 2

def start_ai_review(uid:int, task_id: int, review_type: str, review_topic:str,
        criteria_markdown_data: str, review_file_path: str, criteria_file_type: int , sys_cfg: dict) -> str:
    """
    :param uid: 用户ID
    :param task_id: 当前任务ID
    :param review_type 评审类型
    :param review_topic: 评审主题
    :param criteria_markdown_data: 评审标准和要求markdown 文本
    :param review_file_path: 被评审的材料文件的绝对路径
    :param criteria_file_type: 评审标准文件的类型
    :param sys_cfg： 系统配置信息
    根据评审标准文本和评审材料生成评审报告
    """
    try:
        # 创建评审器并执行评审
        reviewer = PaperReviewer(uid, task_id, review_type, review_topic, criteria_markdown_data, review_file_path, criteria_file_type, sys_cfg)
        review_report = reviewer.execute_review()
        return review_report

    except Exception as e:
        logger.error(f"AI评审生成失败: {str(e)}")
        return f"评审报告生成失败: {str(e)}"


def generate_review_report(uid: int, task_id: int, doc_type: str, review_topic: str,
                           criteria_file: str, paper_file: str, criteria_file_type: int, sys_cfg: dict):
    """
    生成评审报告
    :param uid: 用户ID
    :param doc_type: 评审的文档内容，例如可行性研究报告，概要设计， AI应用设计等
    :param review_topic : 评审的主题， 例如关于xxxx的评审
    :param task_id: 任务ID
    :param criteria_file: 评审标准文件的绝对路径
    :param paper_file: 评审材料文件的绝对路径
    :param criteria_file_type: 评审标准文件的类型
    :param sys_cfg: 系统配置信息
    """
    logger.info(f"{uid}, {task_id},doc_type: {doc_type}, doc_title: {review_topic}, "
                f"criteria_file: {criteria_file}, review_file: {paper_file}")
    try:
        update_process_info(uid, task_id, "开始解析评审标准...")
        # 获取评审标准的文件内容，格式为 Markdown
        criteria_markdown_data = get_md_file_content(criteria_file)
        update_process_info(uid, task_id, "开始分析评审材料...")

        # 调用AI评审生成
        review_result = start_ai_review(uid, task_id, doc_type, review_topic,
            criteria_markdown_data, paper_file, criteria_file_type, sys_cfg)

        doc_info = get_doc_info(task_id)
        if not doc_info or not doc_info[0]:
            info = f"no_doc_info_found_for_task_id ,{task_id}"
            raise RuntimeError(info)
        output_file_path = doc_info[0]['output_file_path']
        output_md_file = save_content_to_md_file(review_result, output_file_path, output_abs_path=True)
        if FileType.XLSX.value ==  criteria_file_type:
            output_file = convert_md_to_xlsx(output_md_file, True)
        else:
            output_file = convert_md_to_docx(output_md_file, True)
        logger.info(f"{uid}, {task_id}, 评审报告生成成功, {output_file}")
        update_process_info(uid, task_id, "评审报告生成完毕", 100)

    except Exception as e:
        update_process_info(uid, task_id, f"任务处理失败: {str(e)}")
        logger.exception("评审报告生成异常", e)

def get_reference_from_vdb(keywords: str, vdb_dir: str, llm_cfg: dict) -> str:
    """
    获取vdb中与关键词相关的文本
    :param keywords: 关键词
    :param vdb_dir: 向量数据库目录
    :param llm_cfg: 系统配置中的LLM API config
    :return: 文本
    """
    logger.debug(f"vdb_dir, {vdb_dir}")
    reference = ""
    if not vdb_dir:
        return reference

    try:
        if "" != vdb_dir and os.path.exists(vdb_dir):
            reference = search_txt(keywords, vdb_dir, 0.2, llm_cfg, 2).strip()
        else:
            logger.warning(f"vdb_dir_not_exist: {vdb_dir}, get no references")
            reference = ""
        # logging.info(f"vdb_get_txt:\n{reference}\nby_search_{keywords}")
    except Exception as exp:
        logger.exception(f"get_references_from_vdb_failed, {keywords}")
    return reference


if __name__ == '__main__':
    my_cfg = init_yml_cfg()
    logger.info("my_cfg", my_cfg)
    my_criteria_xlsx_file = "/home/rd/Downloads/1.xlsx"
    my_paper_docx_file = "/home/rd/Downloads/3.docx"
    my_paper_file = convert_docx_to_md(my_paper_docx_file, True)
    logger.info(f"my_paper_file {my_paper_file}")
    my_criteria_file = convert_xlsx_to_md(my_criteria_xlsx_file, True, True)
    logger.info(f"my_criteria_file {my_criteria_file}")
    my_criteria_data = get_md_file_content(my_criteria_file)
    split_md = split_md_file_with_catalogue(my_criteria_file)
    my_review_topic = "天然气零售信息系统概要设计文档评审"
    start_ai_review(1, 1, my_review_topic, my_criteria_data, my_paper_file, 0, my_cfg)