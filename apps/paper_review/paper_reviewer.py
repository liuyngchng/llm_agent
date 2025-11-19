#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os
import json
import time
from typing import List, Dict

import requests

from common.docx_md_util import get_md_file_content, convert_md_to_docx, save_content_to_md_file, get_md_file_catalogue, \
    convert_docx_to_md, extract_sections_content, split_md_file_with_catalogue, split_md_content_with_catalogue
import logging.config

from common.docx_meta_util import update_process_info_by_task_id, save_output_file_path_by_task_id
from common.sys_init import init_yml_cfg
from common.xlsx_md_util import convert_xlsx_to_md

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output_doc"

MAX_SECTION_LENGTH = 3000  # 3000 字符

# 关闭request请求产生的警告信息 (客户端没有进行服务端 SSL 的证书验证，正常会产生警告信息)， 只要清楚自己在做什么
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(category=InsecureRequestWarning)





class PaperReviewer:
    def __init__(self, uid: int, task_id: int, review_topic:str, criteria_markdown_data: str, review_file_path: str, sys_cfg: dict):
        """
        分章节评审系统
        :param uid: 用户ID，标记哪个用户提交的任务
        :param task_id: 任务ID， 标记是哪个任务
        :param review_topic: 评审主题， 例如 xxxx系统概要涉及评审
        :param criteria_markdown_data: 评审标准 markdown 文本
        :param review_file_path: 评审文件 markdown 路径
        :param sys_cfg: 系统配置
        """
        self.uid = uid
        self.task_id = task_id
        self.review_topic = review_topic
        self.criteria_markdown_data = criteria_markdown_data
        self.review_file_path = review_file_path
        self.sections_data = []
        self.review_results = []
        self.sys_cfg = sys_cfg



    def review_single_section(self, section_title: str, section_content: str, max_retries: int = 3) -> Dict:
        """
        评审单个章节，带重试机制
        """
        for attempt in range(max_retries):
            try:
                prompt = f"""
作为 {self.review_topic} 评审专家，请严格按照评审标准对以下章节进行专业评审：

【章节标题】
{section_title}

【章节内容】
{section_content}

【评审标准】
{self.criteria_markdown_data}

请从以下维度进行专业评审：
1. 内容完整性 - 是否涵盖必要要素，有无重大遗漏
2. 论证逻辑性 - 论点论据是否合理，逻辑是否严密
3. 数据充分性 - 数据是否详实，支撑是否有力
4. 专业规范性 - 是否符合行业规范和标准要求
5. 风险识别度 - 风险分析是否全面客观

请严格按照以下JSON格式返回评审结果：
{{
    "score": 85,
    "strengths": ["优点1", "优点2"],
    "issues": ["问题1", "问题2", "问题3"],
    "suggestions": ["建议1", "建议2"],
    "risk_level": "低/中/高"
}}

请确保：
- score为0-100的整数
- strengths、issues、suggestions为数组格式
- 问题描述要具体明确
- 建议要具有可操作性
"""
                result = self.call_llm_api(prompt)
                # # 暂时用模拟数据
                # result = {
                #     "score": 75 + (attempt * 5),  # 模拟数据
                #     "strengths": ["结构清晰", "数据详实"],
                #     "issues": ["缺乏最新行业数据", "风险评估不够全面"],
                #     "suggestions": ["补充2024年行业数据", "增加敏感性分析"],
                #     "risk_level": "中"
                # }

                # 验证结果格式
                self._validate_review_result(result)
                return result

            except Exception as e:
                logger.warning(f"第{attempt + 1}次评审章节[{section_title}]失败: {str(e)}")
                if attempt == max_retries - 1:
                    # 最后一次尝试失败，返回基础评审结果
                    return self._get_fallback_result(section_title, str(e))
                time.sleep(1)  # 重试前等待

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
                        "score": 60,
                        "strengths": ["内容结构完整"],
                        "issues": [f"AI评审解析失败: {str(e)}", "建议人工复核"],
                        "suggestions": ["请专家人工评审该章节"],
                        "risk_level": "未知"
                    }
            else:
                error_msg = f"LLM API调用失败:{uri}, {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    "score": 60,
                    "strengths": ["章节结构完整"],
                    "issues": [f"API调用失败: {response.status_code}"],
                    "suggestions": ["请专家人工评审该章节"],
                    "risk_level": "未知"
                }
        except Exception as e:
            error_msg = f"LLM API调用异常: {uri}, {str(e)}"
            logger.error(error_msg)
            return {
                "score": 60,
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
        整体报告评审
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

            prompt = f"""
    作为资深评审专家，请基于各章节评审结果，对整篇 {self.review_topic} 进行整体评估：

    【各章节评审概要】
    {json.dumps(section_summaries, ensure_ascii=False, indent=2)}

    【评审标准】
    {self.criteria_markdown_data}

    请从以下维度进行整体评估：
    1. 整体逻辑连贯性 - 各章节之间逻辑是否连贯，论证是否形成完整链条
    2. 前后论证一致性 - 前后数据、结论是否一致，有无矛盾之处
    3. 风险评估全面性 - 整体风险识别是否全面，应对措施是否有效
    4. 经济效益合理性 - 经济效益分析是否合理可信
    5. 报告整体质量 - 综合各章节评分给出整体评价

    请按照以下JSON格式返回评审结果：
    {{
        "overall_score": 85,
        "overall_strengths": ["优势1", "优势2"],
        "overall_issues": ["问题1", "问题2"],
        "key_recommendations": ["建议1", "建议2"],
        "review_summary": "整体评价摘要"
    }}

    请确保返回有效的JSON格式数据。
    """
            overall_result = self.call_llm_api(prompt)

            # 添加结果验证和降级处理
            if not overall_result or 'overall_score' not in overall_result:
                logger.warning("整体评审返回结果格式异常，使用降级结果")
                return self._get_fallback_overall_result(section_results)

            return overall_result

        except Exception as e:
            logger.error(f"整体评审失败: {str(e)}")
            return self._get_fallback_overall_result(section_results)

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

    @staticmethod
    def generate_final_report(section_results: List[Dict], overall_result: Dict) -> str:
        """
        生成最终评审报告的内容
        """
        try:
            report_content = f"""# 可行性分析报告评审报告

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
        执行完整的评审流程， 返回生成的报告文本
        """
        try:
            logger.info("开始执行文档评审流程")

            # 1. 解析目录结构
            catalogue = get_md_file_catalogue(self.review_file_path)
            if not catalogue:
                raise ValueError("无法解析文档目录结构")
            logger.info(f"文档目录，{catalogue}")
            update_process_info_by_task_id(self.uid, self.task_id, "开始解析章节内容...")
            # 2. 提取章节内容
            self.sections_data = extract_sections_content(self.review_file_path, catalogue)
            if not self.sections_data:
                raise ValueError("无法提取章节内容")
            logger.debug(f"章节内容，{self.sections_data}")
            section_count = len(self.sections_data)
            logger.info(f"开始逐章节评审，共{section_count}个章节")

            # 3. 逐章节评审
            for i, section in enumerate(self.sections_data):
                logger.info(f"评审章节 {i + 1}/{len(self.sections_data)}: {section['title']}")
                current_percent = min(95.0, round((i + 1) / len(self.sections_data) * 100, 1))
                update_process_info_by_task_id(self.uid, self.task_id, f"正在处理第{i + 1}/{section_count}个章节", current_percent)
                # 控制章节内容长度，避免过长
                content_preview = section['content'][:MAX_SECTION_LENGTH] + "..." if len(section['content']) > MAX_SECTION_LENGTH else section[
                    'content']

                section_result = self.review_single_section(
                    section['title'],
                    content_preview
                )
                section_result['section_title'] = section['title']
                self.review_results.append(section_result)

                logger.info(f"章节[{section['title']}]评审完成，评分: {section_result['score']}")

            # 4. 整体评审
            logger.info("开始进行评审意见总结")
            update_process_info_by_task_id(self.uid, self.task_id, f"开始进行评审意见总结")
            overall_result = self.review_whole_report(self.review_results)

            # 5. 生成最终报告
            logger.info("生成最终评审报告")
            final_report = self.generate_final_report(self.review_results, overall_result)

            update_process_info_by_task_id(self.uid, self.task_id, f"形成格式化的评审意见报告")
            logger.debug(f"fill_all_formatted_markdown_report_with_final_report\n{final_report}")
            formatted_report = self.fill_all_formatted_markdown_report_with_final_report(final_report)
            logger.info("文档评审流程完成")
            return formatted_report

        except Exception as e:
            logger.exception(f"评审流程执行失败")
            return f"# 评审过程出现错误\n\n错误信息: {str(e)}\n\n请检查文档格式或联系技术支持。"

    def fill_all_formatted_markdown_report_with_final_report(self, final_report_txt: str) -> str:
        """
        使用大语言模型将最终评审结果自动填写到标准格式的评审表格中

        Args:
            final_report_txt: 生成的最终评审报告文本

        Returns:
            填充后的格式化评审报告
        """
        split_md_list = split_md_content_with_catalogue(self.criteria_markdown_data)
        logger.debug(f"split_md_list, {split_md_list}")
        all_txt = ""
        for md in split_md_list:
            single_title = md['title']
            single_criteria = md['content']
            logger.debug(f"get_single_criteria_md, \n##{single_title}\n{single_criteria}")
            single_report = self.fill_single_md_table(final_report_txt, single_criteria)
            single_txt = f"## {single_title}  \n\n {single_report}"
            all_txt = all_txt  + "\n\n" + single_txt
        return all_txt

    def fill_single_md_table(self, final_report_txt: str, single_criteria: str) -> str:
        """
        使用大语言模型将最终评审结果自动填写到标准格式的评审表格中

        Args:
            final_report_txt: 生成的最终评审报告文本
            single_criteria: 评审标准中的一个表格

        Returns:
            填充后的格式化评审报告文本
        """
        prompt = f"""
        作为专业的 {self.review_topic} 评审专家，请将以下评审结果按照标准评审表格的格式进行填写：

        【标准评审表格格式】
        {single_criteria}

        【最终评审结果】
        {final_report_txt}

        请严格按照以下要求进行操作：
        1. 仔细分析标准评审表格的结构和内容要求
        2. 从最终评审结果中提取对应的评分、优点、问题、建议等信息
        3. 将提取的信息准确填写到标准评审表格的相应位置
        4. 保持表格原有的格式和结构不变
        5. 对于每个评审项，都需要填写具体的评分和评审意见
        6. 评审意见要基于最终评审结果中的具体内容，不能凭空编造
        7. 整体评分和总结部分也要相应填写

        请直接返回填充完整的标准评审表格内容，保持原有的Markdown表格格式。
        """
        try:
            logger.info("开始使用LLM将评审结果填充到标准格式表格中")
            # 调用大语言模型API
            filled_report = self.call_llm_api_for_formatting(prompt)

            # 验证返回结果
            if filled_report and self._is_valid_filled_report(filled_report):
                logger.info("成功生成格式化评审报告")
                return filled_report
            else:
                logger.warning("LLM返回的格式化报告不完整，返回原始报告")
                return final_report_txt

        except Exception as e:
            logger.error(f"使用LLM填充格式化报告失败: {str(e)}")
        # 如果填充失败，返回原始报告
        return final_report_txt

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
                    'temperature': 0.3,
                    'max_tokens': 32767,
                    'stream': False  # 确保非流式响应
                }

                logger.info(f"开始调用LLM进行报告格式化 (第{attempt + 1}次尝试)")

                # 动态调整超时时间
                timeout = 180 if attempt == 0 else 300  # 第一次180秒，重试时300秒

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
                        return None
                    time.sleep(2)  # 重试前等待

            except requests.exceptions.Timeout:
                logger.warning(f"第{attempt + 1}次调用LLM API超时")
                if attempt == max_retries - 1:
                    logger.error("所有重试尝试均超时")
                    return None
                time.sleep(3)  # 超时后等待更长时间

            except Exception as e:
                error_msg = f"LLM格式化API调用异常 (第{attempt + 1}次): {str(e)}"
                logger.error(error_msg)
                if attempt == max_retries - 1:
                    return None
                time.sleep(2)

        return None
    @staticmethod
    def _is_valid_filled_report(report: str) -> bool:
        """
        验证填充后的报告是否有效
        """
        if not report or len(report.strip()) < 100:
            return False

        # 检查是否包含表格特征
        table_indicators = ['|', '---', '评分', '评审意见']
        indicators_found = sum(1 for indicator in table_indicators if indicator in report)

        # 如果找到至少2个表格特征，认为报告有效
        return indicators_found >= 2


def start_ai_review(uid:int, task_id: int, review_topic:str, criteria_markdown_data: str, review_file_path: str, sys_cfg: dict) -> str:
    """
    :param uid: 用户ID
    :param task_id: 当前任务ID
    :param review_topic: 评审主题
    :param criteria_markdown_data: 评审标准和要求markdown 文本
    :param review_file_path: 被评审的材料文件的绝对路径
    :param sys_cfg： 系统配置信息
    根据评审标准文本和评审材料生成评审报告
    """
    try:
        # 创建评审器并执行评审
        reviewer = PaperReviewer(uid, task_id, review_topic, criteria_markdown_data, review_file_path, sys_cfg)
        review_report = reviewer.execute_review()
        return review_report

    except Exception as e:
        logger.error(f"AI评审生成失败: {str(e)}")
        return f"评审报告生成失败: {str(e)}"


def generate_review_report(uid: int, doc_type: str, review_topic: str, task_id: int,
                           criteria_file: str, paper_file: str, sys_cfg: dict):
    """
    生成评审报告
    :param uid: 用户ID
    :param doc_type: 评审的文档内容，例如可行性研究报告，概要设计， AI应用设计等
    :param review_topic : 评审的主题， 例如关于xxxx的评审
    :param task_id: 任务ID
    :param criteria_file: 评审标准文件的绝对路径
    :param paper_file: 评审材料文件的绝对路径
    :param sys_cfg: 系统配置信息
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {review_topic}, "
                f"task_id: {task_id}, criteria_file: {criteria_file}, "
                f"review_file: {paper_file}")
    try:
        update_process_info_by_task_id(uid, task_id, "开始解析评审标准...")
        # 获取评审标准的文件内容，格式为 Markdown
        criteria_markdown_data = get_md_file_content(criteria_file)
        update_process_info_by_task_id(uid, task_id, "开始分析评审材料...")

        # 调用AI评审生成
        review_result = start_ai_review(uid, task_id, review_topic, criteria_markdown_data, paper_file, sys_cfg)

        # 生成输出文件
        output_file_name = f"output_{task_id}.md"
        output_md_file = save_content_to_md_file(review_result, output_file_name, output_abs_path=True)

        docx_file_full_path = convert_md_to_docx(output_md_file, output_abs_path=True)
        save_output_file_path_by_task_id(task_id, docx_file_full_path)
        logger.info(f"{uid}, {task_id}, 评审报告生成成功, {docx_file_full_path}")
        update_process_info_by_task_id(uid, task_id, "评审报告生成完毕", 100)

    except Exception as e:
        update_process_info_by_task_id(uid, task_id, f"任务处理失败: {str(e)}")
        logger.exception("评审报告生成异常", e)


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
    start_ai_review(1, 1, my_review_topic, my_criteria_data, my_paper_file, my_cfg)