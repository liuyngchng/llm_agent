#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import os
import logging.config
import base64
import time
from typing import List, Dict

import requests
from PIL import Image
import io

from common.const import get_const
from common.docx_md_util import save_content_to_md_file, convert_md_to_docx, get_md_file_content
from common.docx_meta_util import update_process_info, get_doc_info
from common.my_enums import FileType, AppType
from common.sys_init import init_yml_cfg
from common.xlsx_util import convert_md_to_xlsx

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

# 关闭request请求产生的警告信息 (客户端没有进行服务端 SSL 的证书验证，正常会产生警告信息)， 只要清楚自己在做什么
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(category=InsecureRequestWarning)


class TeamBuilder:
    def __init__(self, uid: int, task_id: int, review_type: str, review_topic: str,
                 criteria_file_path: str, review_file_path: str, criteria_file_type, sys_cfg: dict):
        """
        思想汇报手写体评审系统
        :param uid: 用户ID，标记哪个用户提交的任务
        :param task_id: 任务ID，标记是哪个任务
        :param review_type: 评审类型, 例如 思想汇报评审
        :param review_topic: 评审主题，例如 xxx同志思想汇报评审
        :param criteria_file_path: 评审标准 markdown 文本文件的绝对路径
        :param review_file_path: 评审文件路径（图片或文档），可能会是多个路径，
        :param criteria_file_type: 评审标准的文件类型
        :param sys_cfg: 系统配置
        """
        self.uid = uid
        self.task_id = task_id
        self.review_type = review_type
        self.review_topic = review_topic
        self.criteria_file_path = criteria_file_path
        self.criteria_file_type = criteria_file_type
        self.review_file_path = review_file_path
        self.sys_cfg = sys_cfg
        self.ocr_text = ""
        self.review_results = {}

    def call_llm_api_for_ocr(self, image_path: str) -> str:
        """
        调用大语言模型进行OCR文本识别
        :param image_path: image file full path
        return
            识别的文本内容
        """
        prompt = """请准确识别这张手写图片中的所有文字内容。要求：
1. 保持原文的段落结构
2. 准确识别手写字体，包括可能的连笔字
3. 保留标点符号
4. 如有个别字无法识别，用[?]标记
5. 输出纯文本格式"""
        try:
            # 读取并编码图片
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            key = self.sys_cfg['api']['vlm_api_key']
            model = self.sys_cfg['api']['vlm_model_name']
            uri = f"{self.sys_cfg['api']['vlm_api_uri']}/chat/completions"

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}'
            }

            # 构建消息 - 支持图片的模型需要特殊格式
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]

            payload = {
                'model': model,
                'messages': messages,
                'max_tokens': 4000,
                'temperature': 0.1
            }

            logger.info(f"开始OCR识别: {image_path}")
            response = requests.post(
                url=uri,
                headers=headers,
                json=payload,
                timeout=120,
                verify=False,
            )

            if response.status_code == 200:
                result = response.json()
                ocr_text = result['choices'][0]['message']['content']
                logger.info(f"OCR识别成功，识别文本长度: {len(ocr_text)}")
                return ocr_text
            else:
                error_msg = f"OCR API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return ""

        except Exception as e:
            logger.error(f"OCR识别异常: {str(e)}")
            return ""

    @staticmethod
    def preprocess_image(image_path: str) -> str:
        """
        图片预处理（如果需要）
        """
        try:
            # 简单的图片预处理 - 调整大小和增强对比度
            with Image.open(image_path) as img:
                # 调整图片大小，提高识别效率
                if max(img.size) > 2000:
                    img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)

                # 转换为RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # 保存处理后的图片
                processed_path = image_path.replace('.', '_processed.')
                img.save(processed_path, 'JPEG', quality=85)
                abs_path = os.path.abspath(processed_path)
                logger.info(f"图片预处理完成: {abs_path}")
                return abs_path

        except Exception as e:
            logger.error(f"图片预处理失败: {str(e)}")
            return image_path  # 返回原路径

    def extract_text_from_images(self, max_retries: int = 2) -> str:
        """
        从图片中提取文本（支持多种图片格式）
        """
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif']
        files = self.review_file_path.split(',')
        img_file_count = len(files)

        all_txt = ""
        i = 0
        for img_file in files:
            file_ext = os.path.splitext(img_file)[1]
            if file_ext not in supported_formats:
                logger.error(f"不支持的图片格式: {file_ext}, {img_file}")
                i += 1
                continue
            i += 1
            update_process_info(self.uid, self.task_id, f"开始识别第{i}/{img_file_count}个图片...", i * 5)
            img_ocr_txt = self.extract_text_from_image(img_file, max_retries)
            all_txt = all_txt + img_ocr_txt
        return all_txt


    def extract_text_from_image(self, file_path: str, max_retries: int = 2) -> str:
        """
        从单个图片中提取文本（支持多种图片格式）
        :param file_path: 图片文件的绝对路径
        :param max_retries: 最大尝试次数
        """

        for attempt in range(max_retries):
            try:
                # 预处理图片
                processed_path = self.preprocess_image(file_path)
                # OCR识别
                ocr_text = self.call_llm_api_for_ocr(processed_path)
                if ocr_text and len(ocr_text.strip()) > 10:  # 确保有有效内容
                    self.ocr_text = ocr_text
                    logger.info(f"成功提取文本，长度: {len(ocr_text)}")
                    # 清理临时处理的图片
                    if processed_path != self.review_file_path and os.path.exists(processed_path):
                        os.remove(processed_path)
                    return ocr_text
                else:
                    logger.warning(f"第{attempt + 1}次OCR识别返回空文本或文本过短")
            except Exception as e:
                logger.error(f"第{attempt + 1}次文本提取失败: {str(e)}")
                if attempt == max_retries - 1:
                    return ""

        return ""

    def evaluate_thought_report(self) -> Dict:
        """
        评价思想汇报写作质量
        """
        try:
            template = self.sys_cfg['prompts']['thought_report_evaluation_msg']
            if not template:
                raise RuntimeError("未找到文本评价的提示词模板 thought_report_evaluation_msg")
            criteria = get_md_file_content(self.criteria_file_path)
            logger.debug(f"文本评审标准如下:\n{criteria}")
            prompt = template.format(
                review_type=self.review_type,
                review_topic=self.review_topic,
                report_content=self.ocr_text,
                criteria=criteria
            )

            result = self.call_llm_api(prompt)
            logger.debug(f"{self.uid}, {self.task_id}, _validate_evaluation_result")
            self._validate_evaluation_result(result)
            logger.debug(f"{self.uid}, {self.task_id}, _validate_evaluation_result_finish")
            return result

        except Exception as e:
            logger.error(f"文本质量评价失败: {str(e)}")
            return self._get_fallback_evaluation_result(str(e))

    @staticmethod
    def _validate_evaluation_result(result: Dict):
        """验证评价结果格式"""
        required_fields = ['overall_score', 'content_quality', 'ideological_depth',
                           'writing_standard', 'strengths', 'improvement_suggestions']
        for field in required_fields:
            if field not in result:
                raise ValueError(f"评价结果缺少必要字段: {field}")

        if not isinstance(result['overall_score'], int) or not (0 <= result['overall_score'] <= 100):
            raise ValueError("整体评分必须在0-100之间")

    @staticmethod
    def _get_fallback_evaluation_result(error_msg: str) -> Dict:
        """获取降级评价结果"""
        return {
            "overall_score": 60,
            "content_quality": "内容完整但需要进一步深化",
            "ideological_depth": "思想表达基本清晰",
            "writing_standard": "格式基本规范",
            "strengths": ["态度端正", "内容完整"],
            "improvement_suggestions": [f"技术问题: {error_msg}", "建议人工复核"],
            "evaluation_failed": True
        }

    def generate_party_member_development_suggestion(self, employee_data: str) -> str:
        """
        根据部门员工信息生成党员发展建议
        :param employee_data: 员工信息的markdown文本
        :return: 党员发展建议报告
        """
        try:
            template = self.sys_cfg['prompts']['party_member_development_msg']
            if not template:
                raise RuntimeError("未找到党员发展建议提示词模板")

            prompt = template.format(
                review_type=self.review_type,
                review_topic=self.review_topic,
                employee_data=employee_data,
                criteria=self.criteria_file_path
            )

            result = self.call_llm_api_for_development_suggestion(prompt)
            return self._format_development_suggestion(result)

        except Exception as e:
            logger.error(f"生成党员发展建议失败: {str(e)}")
            return self._get_fallback_development_suggestion(str(e))

    def call_llm_api_for_development_suggestion(self, prompt: str) -> Dict:
        """
        专门用于党员发展建议的LLM调用
        """
        try:
            key = self.sys_cfg['api']['llm_api_key']
            model = self.sys_cfg['api']['llm_model_name']
            uri = f"{self.sys_cfg['api']['llm_api_uri']}/chat/completions"

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}'
            }

            messages = [
                {
                    "role": "system",
                    "content": "你是一名党组织负责人，擅长分析员工信息并提出党员发展建议。请基于员工的政治表现、工作能力、思想状况等方面进行分析。"
                },
                {"role": "user", "content": prompt}
            ]

            payload = {
                'model': model,
                'messages': messages,
                'temperature': 0.3,
                'max_tokens': 3000
            }

            logger.info("开始生成党员发展建议")
            response = requests.post(
                url=uri,
                headers=headers,
                json=payload,
                timeout=120,
                verify=False,
            )

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']

                # 解析JSON结果
                try:
                    if content.strip().startswith('```json'):
                        json_str = content.strip().replace('```json', '').replace('```', '').strip()
                        return json.loads(json_str)
                    else:
                        return json.loads(content)
                except json.JSONDecodeError:
                    # 如果不是JSON，返回原始文本
                    return {"suggestion_text": content}
            else:
                error_msg = f"党员发展建议API调用失败: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}

        except Exception as e:
            logger.error(f"党员发展建议API调用异常: {str(e)}")
            return {"error": str(e)}

    def _format_development_suggestion(self, result: Dict) -> str:
        """格式化党员发展建议报告"""
        try:
            if "error" in result:
                return f"生成党员发展建议时出现错误: {result['error']}"

            # 如果有结构化的数据，按格式输出
            if "suggestions" in result:
                report = f"""# 【{self.review_topic}】党员发展建议报告

## 生成时间
{time.strftime('%Y-%m-%d %H:%M:%S')}

## 总体分析
{result.get('overall_analysis', '基于员工信息进行的总体分析')}

## 重点发展对象建议
"""

                for i, suggestion in enumerate(result['suggestions'], 1):
                    report += f"""
### 建议 {i}: {suggestion.get('employee_name', '员工')}
- **发展优先级**: {suggestion.get('priority', '中')}
- **主要优势**: {suggestion.get('strengths', '待补充')}
- **培养方向**: {suggestion.get('development_direction', '待补充')}
- **建议措施**: {suggestion.get('suggested_actions', '待补充')}
"""

                report += f"""
## 培养计划建议
{result.get('training_plan', '具体的培养计划和建议')}

## 注意事项
{result.get('precautions', '发展党员过程中需要注意的事项')}

---
*本建议基于AI分析生成，请党组织结合实际情况进行决策*
"""
            else:
                # 如果是文本格式的结果
                report = result.get('suggestion_text', '未能生成有效的党员发展建议')

            return report

        except Exception as e:
            logger.error(f"格式化党员发展建议失败: {str(e)}")
            return "党员发展建议格式化失败，请查看原始数据。"

    @staticmethod
    def _get_fallback_development_suggestion(error_msg: str) -> str:
        """获取降级的党员发展建议"""
        return f"""# 党员发展建议生成失败

## 错误信息
{error_msg}

## 建议
请检查员工信息数据的完整性和格式，或联系技术支持。
"""

    def generate_evaluation_report(self) -> str:
        """
        生成思想汇报评价报告
        """
        try:
            evaluation = self.evaluate_thought_report()
            report_content = f"""# 【{self.review_topic}】思想汇报评价报告
## 基本信息
- 评价时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- 整体评分: {evaluation['overall_score']}/100
- 评价结论: {'优秀' if evaluation['overall_score'] >= 85 else '良好' if evaluation['overall_score'] >= 70 else '合格' if evaluation['overall_score'] >= 60 else '需要改进'}

## 详细评价

### 内容质量
{evaluation['content_quality']}

### 思想深度  
{evaluation['ideological_depth']}

### 写作规范
{evaluation['writing_standard']}

### 主要优点
{chr(10).join(f"- {strength}" for strength in evaluation['strengths'])}

### 改进建议
{chr(10).join(f"- {suggestion}" for suggestion in evaluation['improvement_suggestions'])}

## 识别文本预览
{self.ocr_text[:500]}...
（完整文本共{len(self.ocr_text)}字）
## 评价说明
本评价报告基于AI自动识别和评价生成，建议结合人工评审最终确定。
"""
            return report_content
        except Exception as e:
            logger.error(f"生成评价报告失败: {str(e)}")
            return f"# 评价报告生成失败\n\n错误信息: {str(e)}\n\n请检查图片质量或联系技术支持。"

    def execute_evaluation(self) -> str:
        """
        执行完整的思想汇报评价流程
        """
        try:
            logger.info("开始执行文本质量评估流程")

            # 1. OCR文本识别
            update_process_info(self.uid, self.task_id, "开始识别手写文字...", 1)
            ocr_result = self.extract_text_from_images()

            if not ocr_result:
                raise ValueError("无法从图片中识别出有效文本，请检查图片质量")
            logger.debug(f"ocr_result_txt=\n{ocr_result}")
            # 2. 文本质量评价
            update_process_info(self.uid, self.task_id, "文本已提取，开始分析内容质量...", 30)
            evaluation_report = self.generate_evaluation_report()

            logger.info("已对文本质量作出评估")
            return evaluation_report

        except Exception as e:
            logger.exception("已对文本质量作出评估执行失败")
            return f"# 评价过程出现错误\n\n错误信息: {str(e)}\n\n请检查文件格式或联系技术支持。"

    def call_llm_api(self, prompt: str) -> dict:
        """直接调用LLM API"""
        key = self.sys_cfg['api']['llm_api_key']
        model = self.sys_cfg['api']['llm_model_name']
        uri = f"{self.sys_cfg['api']['llm_api_uri']}/chat/completions"
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}'
            }

            messages = [
                {"role": "user", "content": prompt}
            ]

            payload = {
                'model': model,
                'messages': messages,
                'temperature': 0.7,
                'response_format': {"type": "json_object"}
            }

            logger.info(f"开始LLM请求: {uri}, {model}")
            response = requests.post(
                url=uri,
                headers=headers,
                json=payload,
                timeout=120,
                verify=False,
            )

            logger.info(f"响应状态: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                logger.debug(f"LLM返回的原始内容: {content}")

                try:
                    if content.strip().startswith('```json'):
                        json_str = content.strip().replace('```json', '').replace('```', '').strip()
                        parsed_result = json.loads(json_str)
                    else:
                        parsed_result = json.loads(content)

                    logger.info("成功解析LLM返回的JSON")
                    return parsed_result

                except json.JSONDecodeError as e:
                    logger.error(f"解析LLM返回的JSON失败: {str(e)}")
                    logger.error(f"原始内容: {content}")
                    return self._get_fallback_evaluation_result(f"JSON解析失败: {str(e)}")

            else:
                error_msg = f"LLM API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return self._get_fallback_evaluation_result(f"API调用失败: {response.status_code}")

        except Exception as e:
            error_msg = f"LLM API调用异常: {str(e)}"
            logger.error(error_msg)
            return self._get_fallback_evaluation_result(f"API调用异常: {str(e)}")

    def fill_markdown_table(self, conclusion: str, criteria_title: str, single_criteria: str) -> str:
        """
        使用大语言模型将最终评审结果自动填写到标准格式的评审表格中

        Args:
            conclusion: 生成的最终评审结论
            criteria_title: 评审标准中的一个表格的标题
            single_criteria: 评审标准中的一个表格

        Returns:
            填充后的格式化评审报告文本
        """
        template = self.sys_cfg['prompts']['fill_md_table_msg']
        if not template:
            raise RuntimeError("prompts_fill_md_table_msg_err")
        prompt = template.format(
            review_type = self.review_type,
            review_topic = self.review_topic,
            criteria=single_criteria,
            conclusion=conclusion,
        )
        try:
            logger.info(f"开始使用LLM将评审结果填充到标准格式表格中, title={criteria_title}")
            # 调用大语言模型API
            start_time = time.time()
            filled_report = self.call_llm_api_for_formatting(prompt)
            end_time = time.time()
            execution_time = end_time - start_time
            # 验证返回结果
            if filled_report and self._is_valid_filled_report(filled_report):
                logger.info(f"成功生成格式化评审报告, 耗时: {execution_time:.2f} 秒, title={criteria_title}")
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

        # 如果找到至少1个表格特征，认为报告有效
        return indicators_found >= 1





def start_thought_evaluation(uid: int, task_id: int, review_type: str, review_topic: str,
                             criteria_file_path: str, review_file_path: str, criteria_file_type: int,
                             sys_cfg: dict) -> str:
    """
    开始思想汇报评价流程
    :param uid: 用户ID
    :param task_id: 任务ID
    :param review_type: 评审类型
    :param review_topic: 评审主题
    :param criteria_file_path: 评审标准markdown文本文件的绝对路径
    :param review_file_path: 思想汇报文件路径（图片）
    :param criteria_file_type: 评审标准文件类型
    :param sys_cfg: 系统配置
    """
    logger.info(f"{uid}, {task_id}, start_thought_evaluation")
    try:
        evaluator = TeamBuilder(uid, task_id, review_type, review_topic, criteria_file_path,
                                review_file_path, criteria_file_type, sys_cfg)
        evaluation_report = evaluator.execute_evaluation()
        output_report_title = get_const('output_report_title', AppType.TEAM_BUILDING.name.lower())
        if not output_report_title:
            raise RuntimeError("pls config cfg.db for const key output_report_title")
        logger.debug(f"output_report_title = {output_report_title}")
        review_result = evaluator.fill_markdown_table(evaluation_report,
                                                      output_report_title, criteria_file_path)
        doc_info=get_doc_info(task_id)
        output_file_path = doc_info[0]['output_file_path']
        logger.debug(f"output_file_path = {output_file_path}")
        output_md_file = save_content_to_md_file(review_result, output_file_path, output_abs_path=True)
        logger.debug(f"output_md_file = {output_md_file}")
        if FileType.XLSX.value == criteria_file_type:
            output_file = convert_md_to_xlsx(output_md_file, True)
        else:
            output_file = convert_md_to_docx(output_md_file, True)
        logger.info(f"{uid}, {task_id}, 评审报告生成成功, {output_file}")
        update_process_info(uid, task_id, "评审报告生成完毕", 100)
        return evaluation_report

    except Exception as e:
        logger.error(f"思想汇报评价生成失败: {str(e)}")
        return f"思想汇报评价生成失败: {str(e)}"

def generate_party_member_suggestion(uid: int, task_id: int, review_type: str, review_topic: str,
                                     criteria_markdown_data: str, employee_data: str, sys_cfg: dict) -> str:
    """
    生成党员发展建议
    :param uid: 用户ID
    :param task_id: 任务ID
    :param review_type: 评审类型
    :param review_topic: 评审主题
    :param criteria_markdown_data: 评审标准markdown文本
    :param employee_data: 员工信息markdown文本
    :param sys_cfg: 系统配置
    :return: 党员发展建议报告
    """
    logger.info(f"{uid}, {task_id}, generate_party_member_suggestion")
    try:
        # 使用空的review_file_path和默认的criteria_file_type
        builder = TeamBuilder(uid, task_id, review_type, review_topic,
                              criteria_markdown_data, "", 0, sys_cfg)

        update_process_info(uid, task_id, "正在分析员工信息并生成党员发展建议...")
        suggestion_report = builder.generate_party_member_development_suggestion(employee_data)

        logger.info("党员发展建议生成成功")
        return suggestion_report

    except Exception as e:
        logger.error(f"党员发展建议生成失败: {str(e)}")
        update_process_info(uid, task_id, f"党员发展建议生成失败: {str(e)}")
        return f"党员发展建议生成失败: {str(e)}"


if __name__ == "__main__":

    file = "/home/rd/Downloads/manuscript.jpeg"
    file1 = TeamBuilder.preprocess_image(file)
    logger.info(f"file1 = {file1}")
    my_cfg = init_yml_cfg()
    tb = TeamBuilder(123, 123, "test", "test", "test",
"test", "test", my_cfg)
    ocr_txt = tb.call_llm_api_for_ocr(file1)
    logger.info(f"ocr_txt={ocr_txt}")