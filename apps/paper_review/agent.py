#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os
import json
import time
from typing import List, Dict, Any
from common import docx_meta_util
from common.docx_md_util import get_md_file_content, convert_md_to_docx, save_content_to_md_file, get_md_file_catalogue
import logging.config

from common.docx_meta_util import update_process_info_by_task_id

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output_doc"


class SectionReviewer:
    def __init__(self, criteria_data: str, review_file_path: str):
        """
        增强版分章节评审系统
        """
        self.criteria_data = criteria_data
        self.review_file_path = review_file_path
        self.sections_data = []
        self.review_results = []

    def extract_sections_content(self, catalogue: Dict) -> List[Dict]:
        """
        从Markdown文件中提取各章节内容
        """
        try:
            with open(self.review_file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            sections = []

            def extract_section_content(start_line, end_line=None):
                """提取指定行范围内的内容"""
                if end_line is None:
                    end_line = len(lines)
                content_lines = lines[start_line - 1:end_line]
                return ''.join(content_lines).strip()

            def process_node(node, parent_title=""):
                """递归处理目录节点"""
                current_title = node['title']
                full_title = f"{parent_title} > {current_title}" if parent_title else current_title

                # 提取本节内容
                start_line = node['line']

                # 找到下一节开始的行（如果有的话）
                end_line = len(lines) + 1
                if 'children' in node and node['children']:
                    # 找到第一个子节点的开始行作为结束位置
                    first_child = list(node['children'].values())[0]
                    end_line = first_child['line']

                content = extract_section_content(start_line, end_line)

                sections.append({
                    'title': full_title,
                    'level': node['level'],
                    'content': content,
                    'start_line': start_line,
                    'end_line': end_line - 1 if end_line <= len(lines) else len(lines)
                })

                # 递归处理子节点
                if 'children' in node:
                    for child in node['children'].values():
                        process_node(child, full_title)

            # 处理所有根节点
            for root_node in catalogue.values():
                process_node(root_node)

            logger.info(f"成功提取 {len(sections)} 个章节内容")
            return sections

        except Exception as e:
            logger.error(f"提取章节内容失败: {str(e)}")
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
                # TODO: 这里调用你的LLM接口
                # result = self.call_llm(prompt)
                # 暂时用模拟数据
                result = {
                    "score": 75 + (attempt * 5),  # 模拟数据
                    "strengths": ["结构清晰", "数据详实"],
                    "issues": ["缺乏最新行业数据", "风险评估不够全面"],
                    "suggestions": ["补充2024年行业数据", "增加敏感性分析"],
                    "risk_level": "中"
                }

                # 验证结果格式
                self._validate_review_result(result)
                return result

            except Exception as e:
                logger.warning(f"第{attempt + 1}次评审章节[{section_title}]失败: {str(e)}")
                if attempt == max_retries - 1:
                    # 最后一次尝试失败，返回基础评审结果
                    return self._get_fallback_result(section_title, str(e))
                time.sleep(1)  # 重试前等待

    def _validate_review_result(self, result: Dict):
        """验证评审结果格式"""
        required_fields = ['score', 'strengths', 'issues', 'suggestions']
        for field in required_fields:
            if field not in result:
                raise ValueError(f"评审结果缺少必要字段: {field}")

        if not isinstance(result['score'], int) or not (0 <= result['score'] <= 100):
            raise ValueError("评分必须在0-100之间")

    def _get_fallback_result(self, section_title: str, error_msg: str) -> Dict:
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

请按照 【评审标准】的模板， 填写相应内容，返回
"""
            # TODO: 调用LLM
            overall_result = {
                "overall_score": sum(r['score'] for r in section_results) // len(section_results),
                "overall_strengths": ["报告结构完整", "数据分析详实"],
                "overall_issues": ["部分章节深度不足", "风险分析需要加强"],
                "key_recommendations": ["建议补充行业最新数据", "建议增加敏感性分析"],
                "review_summary": "报告基本达到要求，但需要在数据更新和风险分析方面进一步加强。"
            }

            return overall_result

        except Exception as e:
            logger.error(f"整体评审失败: {str(e)}")
            return {
                "overall_score": 60,
                "overall_strengths": [],
                "overall_issues": ["整体评审过程出现技术问题"],
                "key_recommendations": ["建议人工复核整篇报告"],
                "review_summary": "由于技术原因，整体评审未能完成，建议专家人工评审。"
            }

    def generate_final_report(self, section_results: List[Dict], overall_result: Dict) -> str:
        """
        生成最终评审报告
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
        执行完整的评审流程
        """
        try:
            logger.info("开始执行文档评审流程")

            # 1. 解析目录结构
            catalogue = get_md_file_catalogue(self.review_file_path)
            if not catalogue:
                raise ValueError("无法解析文档目录结构")

            # 2. 提取章节内容
            self.sections_data = self.extract_sections_content(catalogue)
            if not self.sections_data:
                raise ValueError("无法提取章节内容")

            logger.info(f"开始逐章节评审，共{len(self.sections_data)}个章节")

            # 3. 逐章节评审
            for i, section in enumerate(self.sections_data):
                logger.info(f"评审章节 {i + 1}/{len(self.sections_data)}: {section['title']}")

                # 控制章节内容长度，避免过长
                content_preview = section['content'][:3000] + "..." if len(section['content']) > 3000 else section[
                    'content']

                section_result = self.review_single_section(
                    section['title'],
                    content_preview
                )
                section_result['section_title'] = section['title']
                self.review_results.append(section_result)

                logger.info(f"章节[{section['title']}]评审完成，评分: {section_result['score']}")

            # 4. 整体评审
            logger.info("开始整体评审")
            overall_result = self.review_whole_report(self.review_results)

            # 5. 生成最终报告
            logger.info("生成最终评审报告")
            final_report = self.generate_final_report(self.review_results, overall_result)

            logger.info("文档评审流程完成")
            return final_report

        except Exception as e:
            logger.error(f"评审流程执行失败: {str(e)}")
            return f"# 评审过程出现错误\n\n错误信息: {str(e)}\n\n请检查文档格式或联系技术支持。"


def start_ai_review(criteria_data: str, review_file_path: str) -> str:
    """
    根据评审标准文本和评审材料生成评审报告
    """
    try:
        # 创建评审器并执行评审
        reviewer = SectionReviewer(criteria_data, review_file_path)
        review_report = reviewer.execute_review()
        return review_report

    except Exception as e:
        logger.error(f"AI评审生成失败: {str(e)}")
        return f"评审报告生成失败: {str(e)}"


def generate_review_report(uid: int, doc_type: str, review_topic: str, task_id: int,
                           criteria_file: str, paper_file: str):
    """
    生成评审报告
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {review_topic}, "
                f"task_id: {task_id}, criteria_file: {criteria_file}, "
                f"review_file: {paper_file}")
    try:
        update_process_info_by_task_id(uid, task_id, "开始解析评审标准...", 0)

        # 获取评审标准的文件内容，格式为 Markdown
        criteria_data = get_md_file_content(criteria_file)
        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始分析评审材料...", 30)

        update_process_info_by_task_id(uid, task_id, "生成评审报告...", 60)

        # 调用AI评审生成
        review_result = start_ai_review(criteria_data, paper_file)

        # 生成输出文件
        output_file_name = f"output_{task_id}.md"
        output_md_file = save_content_to_md_file(review_result, output_file_name, output_abs_path=True)

        docx_file_full_path = convert_md_to_docx(output_md_file, output_abs_path=True)
        logger.info(f"{uid}, {task_id}, 评审报告生成成功, {docx_file_full_path}")

        update_process_info_by_task_id(uid, task_id, "评审报告生成完毕", 100)

    except Exception as e:
        update_process_info_by_task_id(uid, task_id, f"任务处理失败: {str(e)}")
        logger.exception("评审报告生成异常", e)