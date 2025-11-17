#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os
import json
import time
from typing import List, Dict

import requests


from common import docx_meta_util
from common.docx_md_util import get_md_file_content, convert_md_to_docx, save_content_to_md_file, get_md_file_catalogue, \
    convert_docx_to_md
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



class SectionReviewer:
    def __init__(self, uid: int, task_id: int, criteria_data: str, review_file_path: str, sys_cfg: dict):
        """
        分章节评审系统
        :param uid: 用户ID，标记哪个用户提交的任务
        :param task_id: 任务ID， 标记是哪个任务
        """
        self.uid = uid
        self.task_id = task_id
        self.criteria_data = criteria_data
        self.review_file_path = review_file_path
        self.sections_data = []
        self.review_results = []
        self.sys_cfg = sys_cfg

    def extract_sections_content(self, catalogue: Dict, extract_heading_level: int = 2) -> List[Dict]:
        """
        按指定标题层级提取章节内容，这个方法很重要，决定着后续的流程是否正确与否

        Args:
            catalogue: 目录结构
            extract_heading_level: 提取的标题层级，默认提取2级标题的内容
        """

        try:
            with open(self.review_file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            sections = []

            def collect_all_nodes(node, nodes_list=None):
                """收集所有节点"""
                if nodes_list is None:
                    nodes_list = []

                if isinstance(node, dict):
                    nodes_list.append(node)
                    children = node.get('children', {})
                    for child in children.values():
                        collect_all_nodes(child, nodes_list)

                return nodes_list

            def find_next_section_at_level(current_node, current_level, total_lines):
                """找到下一个同级或更高级别章节的开始行"""
                all_nodes = collect_all_nodes(catalogue)
                all_nodes.sort(key=lambda x: x.get('line', 1))

                current_line = current_node.get('line', 1)
                for node in all_nodes:
                    node_line = node.get('line', 1)
                    node_level = node.get('level', 1)
                    if node_line > current_line and node_level <= current_level:
                        return node_line

                return total_lines + 1

            def extract_content_at_level(node, parent_title="", current_level=1):
                """按指定层级提取章节内容"""
                if isinstance(node, dict):
                    current_title = node.get('title', '')
                    level = node.get('level', 1)
                    line_num = node.get('line', 1)

                    full_title = f"{parent_title} > {current_title}" if parent_title else current_title

                    # 如果当前节点层级等于或小于目标层级，提取内容
                    if level == extract_heading_level:
                        # 提取本节内容
                        start_line = line_num

                        # 找到下一同级或更高级别章节的开始行
                        end_line = find_next_section_at_level(node, level, len(lines))

                        content = ''.join(lines[start_line - 1:end_line]).strip()

                        sections.append({
                            'title': full_title,
                            'level': level,
                            'content': content,
                            'start_line': start_line,
                            'end_line': end_line - 1 if end_line <= len(lines) else len(lines)
                        })

                        logger.debug(
                            f"提取章节 '{full_title}': 层级 {level}, 行 {start_line}-{end_line - 1}, 长度 {len(content)} 个字符")

                    # 递归处理子节点
                    children = node.get('children', {})
                    for child in children.values():
                        extract_content_at_level(child, full_title, level)

            # 开始提取
            extract_content_at_level(catalogue)

            # 按行号排序
            sections.sort(key=lambda x: x['start_line'])

            logger.info(f"按{extract_heading_level}级标题提取了 {len(sections)} 个章节内容")

            # 输出提取的章节信息
            for i, section in enumerate(sections[:5]):  # 只显示前5个作为样例
                logger.info(
                    f"样例章节{i + 1}: '{section['title']}' (层级{section['level']}), 内容长度: {len(section['content'])}")

            return sections

        except Exception as e:
            logger.error(f"提取章节内容失败: {str(e)}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return []

    def review_single_section(self, section_title: str, section_content: str, max_retries: int = 3) -> Dict:
        """
        评审单个章节，带重试机制
        """
        for attempt in range(max_retries):
            try:
                prompt = f"""
作为可行性分析报告评审专家，请严格按照评审标准对以下章节进行专业评审：

【章节标题】
{section_title}

【章节内容】
{section_content}

【评审标准】
{self.criteria_data}

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
    作为资深评审专家，请基于各章节评审结果，对整篇可行性分析报告进行整体评估：

    【各章节评审概要】
    {json.dumps(section_summaries, ensure_ascii=False, indent=2)}

    【评审标准】
    {self.criteria_data}

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

## 分章节详细评审
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
            self.sections_data = self.extract_sections_content(catalogue)
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
            logger.info("文档评审流程完成")
            return final_report

        except Exception as e:
            logger.error(f"评审流程执行失败: {str(e)}")
            return f"# 评审过程出现错误\n\n错误信息: {str(e)}\n\n请检查文档格式或联系技术支持。"


def start_ai_review(uid:int, task_id: int, criteria_data: str, review_file_path: str, sys_cfg: dict) -> str:
    """
    :param uid: 用户ID
    :param task_id: 当前任务ID
    :param criteria_data: 评审标准和要求文本
    :param review_file_path: 被评审的材料文件的绝对路径
    :param sys_cfg： 系统配置信息
    根据评审标准文本和评审材料生成评审报告
    """
    try:
        # 创建评审器并执行评审
        reviewer = SectionReviewer(uid, task_id, criteria_data, review_file_path, sys_cfg)
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
        criteria_data = get_md_file_content(criteria_file)
        update_process_info_by_task_id(uid, task_id, "开始分析评审材料...")

        # 调用AI评审生成
        review_result = start_ai_review(uid, task_id, criteria_data, paper_file, sys_cfg)

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
    my_criteria_xlsx_file = "/home/rd/workspace/llm_agent/apps/paper_review/评审标准.xlsx"
    my_paper_docx_file = "/home/rd/workspace/llm_agent/apps/paper_review/天然气零售系统可行性研究报告.docx"
    my_paper_file = convert_docx_to_md(my_paper_docx_file, True)
    logger.info(f"my_paper_file {my_paper_file}")
    my_criteria_file = convert_xlsx_to_md(my_criteria_xlsx_file, True, True)
    logger.info(f"my_criteria_file {my_criteria_file}")
    my_criteria_data = get_md_file_content(my_criteria_file)
    start_ai_review(my_criteria_data, my_paper_file, my_cfg)