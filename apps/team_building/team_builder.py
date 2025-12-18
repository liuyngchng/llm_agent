#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import os
import logging.config
import base64
import time
from typing import Dict

import requests
from PIL import Image

from common.cfg_util import get_usr_prompt_template
from common.const import get_const
from common.docx_md_util import save_content_to_md_file, convert_md_to_docx, get_md_file_content
from common.docx_meta_util import update_process_info, get_doc_info
from common.my_enums import FileType, AppType, DataType
from common.sys_init import init_yml_cfg
from common.xlsx_util import convert_md_to_xlsx

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

# 关闭request请求产生的警告信息 (客户端没有进行服务端 SSL 的证书验证，正常会产生警告信息)， 只要清楚自己在做什么
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(category=InsecureRequestWarning)


class TeamBuilder:
    def __init__(self, uid: int, task_id: int, review_type: str, review_topic: str,
                 criteria_file_path: str, review_file_path: str, criteria_file_type: str, sys_cfg: dict):
        """
        团队建设材料评审系统
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
        self.review_txt = ""
        self.review_txt_err_msg = None
        self.review_results = {}

    def call_llm_api_for_ocr(self, image_path: str) -> dict:
        """
        调用大语言模型进行OCR文本识别
        :param image_path: image file full path
        return
            识别的文本内容及错误信息
            {"dt":"识别的文本信息", "err_msg":"识别出错的信息"}
        """
        prompt = get_usr_prompt_template("manuscript_ocr_msg", self.sys_cfg)
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
                return {"dt": ocr_text, "err_msg": ""}
            else:
                error_msg = f"LLM API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"dt": "", "err_msg": error_msg}

        except Exception as e:
            logger.error(f"OCR识别异常: {str(e)}")
            return {"dt": "", "err_msg": str(e)}

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

    def extract_text_from_images(self, max_retries: int = 2) -> list[dict]:
        """
        从图片中提取文本（支持多种图片格式）
        :param max_retries， 最大尝试次数
        return
            [{"dt": "识别的文本", "err_msg": 识别文本时的出错信息}]
        """
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.heic', '.heif']
        files = self.review_file_path.split(',')
        img_file_count = len(files)

        all_txt = []
        i = 0
        for img_file in files:
            file_ext = os.path.splitext(img_file)[1]
            if file_ext not in supported_formats:
                logger.error(f"不支持的图片格式: {file_ext}, {img_file}")
                i += 1
                continue
            i += 1
            update_process_info(self.uid, self.task_id, f"开始识别第{i}/{img_file_count}个图片...", i * 5)
            img_ocr_result = self.extract_text_from_image(img_file, max_retries)
            all_txt.append(img_ocr_result)
        return all_txt


    def extract_text_from_image(self, file_path: str, max_retries: int = 2) -> dict:
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
                ocr_result = self.call_llm_api_for_ocr(processed_path)
                if ocr_result:  # 确保有有效内容
                    logger.info(f"{self.uid}, {self.task_id}, 提取文本结果，长度: {len(ocr_result['dt'])}，错误信息 {ocr_result['err_msg']}, file {processed_path}")
                    # 清理临时处理的图片
                    if processed_path != self.review_file_path and os.path.exists(processed_path):
                        os.remove(processed_path)
                    return ocr_result
                else:
                    err_msg = f"第 {attempt + 1} 次尝试 OCR 识别返回空文本"
                    logger.warning(f"{self.uid}, {self.task_id},{err_msg}")
                    return {"dt": "", "err_msg": err_msg}
            except Exception as e:
                err_msg = f"第{attempt + 1}次文本提取失败: {str(e)}"
                logger.error(err_msg)
                if attempt == max_retries - 1:
                    return {"dt": "", "err_msg": err_msg}

        return  {"dt": "", "err_msg": "多次尝试提取文本出现错误"}


    def evaluate_material_quality(self) -> dict:
        """
        评价材料质量
        """
        if self.review_txt_err_msg:
            return self._get_fallback_material_evaluation_result(self.review_txt_err_msg)
        try:
            template_name = "material_quality_evaluation_msg"
            template = get_usr_prompt_template(template_name, self.sys_cfg)
            if not template:
                err_info = f"未找到材料质量评价的提示词模板 {template_name}"
                return self._get_fallback_material_evaluation_result(err_info)
            logger.debug(f"template_content_for_name {template_name}, {template}")
            criteria = get_md_file_content(self.criteria_file_path)
            logger.debug(f"材料质量评审标准如下:\n{criteria}")

            prompt = template.format(
                review_type=self.review_type,
                review_topic=self.review_topic,
                report_content=self.review_txt,
                criteria=criteria
            )
            logger.debug(f"{self.uid}, {self.task_id}, start_call_llm_api")
            result = self.call_llm_api_to_evaluate_material_quality(prompt)
            logger.debug(f"{self.uid}, {self.task_id}, call_llm_api_result, {result}")
            logger.debug(f"{self.uid}, {self.task_id}, _validate_material_evaluation_result")
            self._validate_material_evaluation_result(result)
            logger.debug(f"{self.uid}, {self.task_id}, _validate_material_evaluation_result_finish")
            return result

        except Exception as e:
            logger.exception(f"材料质量评价失败: {str(e)}")
            return self._get_fallback_material_evaluation_result(str(e))

    @staticmethod
    def _validate_material_evaluation_result(result: Dict):
        """验证材料质量评价结果格式"""
        required_fields = ['score_summary', 'content_evaluation', 'strengths',
                           'improvement_suggestions', 'final_assessment']
        for field in required_fields:
            if field not in result:
                raise ValueError(f"材料质量评价结果缺少必要字段: {field}")

        # 验证详细分数结构
        if 'detailed_scores' not in result['score_summary']:
            raise ValueError("缺少详细分数结构")

        score_components = ['content_quality', 'political_ideology', 'originality',
                            'format_standard', 'timeliness']
        for component in score_components:
            if component not in result['score_summary']['detailed_scores']:
                raise ValueError(f"缺少评分项: {component}")

    @staticmethod
    def _get_fallback_material_evaluation_result(error_msg: str) -> Dict:
        """获取材料质量评价的降级结果（修复格式）"""
        return {
            "score_summary": {
                "overall_score": 65,
                "detailed_scores": {
                    "content_quality": {
                        "score": 0,
                        "comments": "因评估失败，采用默认评分"
                    },
                    "political_ideology": {
                        "score": 0,
                        "assessment": "因评估失败，采用默认评估"
                    },
                    "originality": {
                        "score": 0,
                        "plagiarism_level": "因评估失败，无法确定"
                    },
                    "format_standard": {
                        "score": 0,
                        "compliance_level": "因评估失败，无法确定"
                    },
                    "timeliness": {
                        "score": 0,
                        "timeliness_assessment": "因评估失败，无法确定"
                    }
                }
            },
            "content_evaluation": {
                "main_arguments": "内容基本完整，但需要进一步深化",
                "evidence_support": "论据基本充分，建议补充更多实例",
                "logic_structure": "逻辑结构基本清晰"
            },
            "strengths": ["主题基本明确", "格式基本规范"],
            "improvement_suggestions": [f"技术问题: {error_msg}", "建议补充具体案例", "需要加强论证深度"],
            "final_assessment": {
                "quality_rating": "未知",
                "usage_recommendation": "修改后采用",
                "key_improvements_needed": "需要改进内容和论证方式"
            },
            "evaluation_failed": True
        }


    def generate_tb_suggestion(self, review_files_path: str) -> str:
        """
        根据部门员工信息生成成员发展建议
        :param review_files_path: 员工信息的markdown文件的绝对路径
        :return: 成员发展建议报告
        """
        try:
            template_name = "team_member_development_msg"
            template = get_usr_prompt_template(template_name, self.sys_cfg)
            if not template:
                err_info = f"未找到成员发展建议提示词模板，{template_name}"
                return self._get_fallback_development_suggestion(err_info)
            employee_data = get_md_file_content(review_files_path)
            criteria_data = get_md_file_content(self.criteria_file_path)
            prompt = template.format(
                review_type=self.review_type,
                review_topic=self.review_topic,
                employee_data=employee_data,
                criteria=criteria_data
            )

            logger.info("start_call_llm_api_for_tb_suggestion")
            result = self.call_llm_api_for_tb_suggestion(prompt)
            logger.info("start_format_tb_suggestion")
            return self._format_tb_suggestion(result)

        except Exception as e:
            logger.error(f"生成成员发展建议失败: {str(e)}")
            return self._get_fallback_development_suggestion(str(e))

    def call_llm_api_for_tb_suggestion(self, prompt: str) -> dict:
        """
        专门用于成员发展建议的LLM调用
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
                    "content": get_const('role_content', AppType.TEAM_BUILDING.name.lower())
                },
                {"role": "user", "content": prompt}
            ]

            payload = {
                'model': model,
                'messages': messages,
                'temperature': 0.3,
                'max_tokens': 3000
            }

            logger.info("开始生成成员发展建议")
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
                error_msg = f"成员发展建议API调用失败: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}

        except Exception as e:
            logger.error(f"成员发展建议API调用异常: {str(e)}")
            return {"error": str(e)}

    def _format_tb_suggestion(self, result: Dict) -> str:
        """格式化成员发展建议报告"""
        try:
            if "error" in result:
                return f"生成成员发展建议时出现错误: {result['error']}"

            # 如果有结构化的数据，按格式输出
            if "suggestions" in result:
                report = f"""# 【{self.review_topic}】成员发展建议报告

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
{result.get('precautions', '发展成员过程中需要注意的事项')}

---
*本建议基于AI分析生成，请组织结合实际情况进行决策*
"""
            else:
                # 如果是文本格式的结果
                report = result.get('suggestion_text', '未能生成有效的成员发展建议')

            return report

        except Exception as e:
            logger.error(f"格式化成员发展建议失败: {str(e)}")
            return "成员发展建议格式化失败，请查看原始数据。"

    @staticmethod
    def _get_fallback_development_suggestion(error_msg: str) -> str:
        """获取降级的成员发展建议"""
        return f"""# 成员发展建议生成失败

## 错误信息
{error_msg}

## 建议
请检查员工信息数据的完整性和格式，或联系技术支持。
"""

    def generate_material_quality_report(self) -> str:
        """
        生成材料质量评价报告
        """
        try:
            evaluation = self.evaluate_material_quality()
            report_title = get_const('output_report_title', AppType.TEAM_BUILDING.name.lower())

            # 计算各项得分
            detailed_scores = evaluation['score_summary']['detailed_scores']

            report_content = f"""# 【{self.review_topic}】{report_title}
            
## 1. 基本信息
- 评审时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- 整体评分: {evaluation['score_summary']['overall_score']}/100
- 质量等级: {evaluation['final_assessment']['quality_rating']}
- 使用建议: {evaluation['final_assessment']['usage_recommendation']}

## 2. 详细评分结果

### 2.1 内容质量 (30分)
**得分: {detailed_scores['content_quality']['score']}分**

分析要点:
{evaluation['content_evaluation']['main_arguments']}

### 2.2 政治思想 (25分)
**得分: {detailed_scores['political_ideology']['score']}分**

政治立场评估:
{detailed_scores['political_ideology'].get('assessment', '待评估')}

### 2.3 原创性 (20分)
**得分: {detailed_scores['originality']['score']}分**

原创性等级: {detailed_scores['originality'].get('plagiarism_level', '待评估')}

### 2.4 格式规范 (15分)
**得分: {detailed_scores['format_standard']['score']}分**

格式合规性: {detailed_scores['format_standard'].get('compliance_level', '待评估')}

### 2.5 时效性 (10分)
**得分: {detailed_scores['timeliness']['score']}分**

时效性评估: {detailed_scores['timeliness'].get('timeliness_assessment', '待评估')}

## 3. 综合评价

### 3.1 主要优点
{chr(10).join(f"- {strength}" for strength in evaluation['strengths'])}

### 3.2 改进建议
{chr(10).join(f"- {suggestion}" for suggestion in evaluation['improvement_suggestions'])}

### 3.3 关键改进点
{evaluation['final_assessment']['key_improvements_needed']}

## 4. 材料内容预览
{self.review_txt[:500]}...
（完整材料共{len(self.review_txt)}字）

## 5. 评审说明

*** 本评价报告基于AI自动评审生成，建议结合专家评审最终确定。

评审专家: {AppType.TEAM_BUILDING.value}评委

评审时间: {time.strftime('%Y-%m-%d')}
"""
            return report_content

        except Exception as e:
            logger.error(f"生成材料质量评价报告失败: {str(e)}")
            return f"# 材料质量评价报告生成失败\n\n错误信息: {str(e)}\n\n请检查材料内容或联系技术支持。"

    def call_llm_api_to_evaluate_material_quality(self, prompt: str) -> dict:
        """直接调用LLM API"""
        key = self.sys_cfg['api']['llm_api_key']
        model = self.sys_cfg['api']['llm_model_name']
        uri = f"{self.sys_cfg['api']['llm_api_uri']}/chat/completions"
        try:
            headers = {'Content-Type': 'application/json','Authorization': f'Bearer {key}'}
            messages = [{"role": "user", "content": prompt}]

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
                    return self._get_fallback_material_evaluation_result(f"JSON解析失败: {str(e)}")

            else:
                error_msg = f"LLM API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return self._get_fallback_material_evaluation_result(error_msg)

        except Exception as e:
            error_msg = f"LLM API调用异常: {str(e)}"
            logger.error(error_msg)
            return self._get_fallback_material_evaluation_result(f"API调用异常: {str(e)}")



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
                logger.debug(f"formatting_msg, {messages}")
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

    def execute_material_quality_evaluation(self) -> str:
        """
        执行完整的材料质量评价流程
        """
        try:
            logger.info("开始执行材料质量评估流程")

            # 1. OCR文本识别（如果是图片材料）
            update_process_info(self.uid, self.task_id, "开始材料文本识别...", 1)
            extension = os.path.splitext(self.review_file_path)[1][1:]
            if DataType.MD.value == extension:
                logger.info(f"get_txt_from_md_file, {self.review_file_path}, extension {extension}")
                # 是Markdown 文本文件，直接读取
                self.review_txt = get_md_file_content(self.review_file_path)
            else:
                # 如果是图片文件，进行OCR识别
                logger.info(f"get_txt_from_img_file, {self.review_file_path}, extension {extension}")
                ocr_result = self.extract_text_from_images()
                tmp_ocr_txt = ""
                tmp_ocr_err = ""
                for index, item in enumerate(ocr_result, start=1):  # 从1开始计数
                    if item['dt']:
                        tmp_ocr_txt += item['dt']
                        tmp_ocr_txt += ', '
                    if item['err_msg']:
                        tmp_ocr_err += f"第 {index} 个图片识别时出错: {item['err_msg']}, "
                self.review_txt_err_msg = tmp_ocr_err
                self.review_txt = tmp_ocr_txt

            logger.debug(f"材料文本内容长度: {len(self.review_txt)}")

            # 2. 材料质量评价
            update_process_info(self.uid, self.task_id, f"已提取材料内容，开始质量评估...", 30)
            evaluation_report = self.generate_material_quality_report()

            logger.info("材料质量评估完成")
            return evaluation_report

        except Exception as e:
            logger.exception("材料质量评估执行失败")
            return f"# 材料质量评估过程出现错误\n\n错误信息: {str(e)}\n\n请检查材料格式或联系技术支持。"


def evaluation_material_quality(uid: int, task_id: int, review_type: str, review_topic: str,
        criteria_file_path: str, review_file_path: str, criteria_file_type: str, sys_cfg: dict) -> None:
    """
    材料质量评价流程
    :param uid: 用户ID
    :param task_id: 任务ID
    :param review_type: 评审类型
    :param review_topic: 评审主题
    :param criteria_file_path: 评审标准markdown文本文件的绝对路径
    :param review_file_path: 材料文件路径（图片或文档）
    :param criteria_file_type: 评审标准文件类型
    :param sys_cfg: 系统配置
    """
    logger.info(f"{uid}, {task_id}, evaluation_material_quality, "
        f"{review_type}, {review_topic}, {criteria_file_path}, "
        f"{review_file_path}, {criteria_file_type}, {sys_cfg}")
    try:
        evaluator = TeamBuilder(uid, task_id, review_type, review_topic, criteria_file_path,
            review_file_path, criteria_file_type, sys_cfg)

        # 执行材料质量评估
        evaluation_report = evaluator.execute_material_quality_evaluation()
        output_report_title = get_const('output_material_quality_title',
            AppType.TEAM_BUILDING.name.lower()) or "材料质量评审报告"
        logger.debug(f"output_report_title = {output_report_title}")

        doc_info = get_doc_info(task_id)
        output_file_path = doc_info[0]['output_file_path']
        logger.debug(f"output_file_path = {output_file_path}")
        # 保存结果
        output_md_file = save_content_to_md_file(evaluation_report, output_file_path, output_abs_path=True)
        if FileType.XLSX.value == criteria_file_type:
            output_file = convert_md_to_xlsx(output_md_file, True)
        else:
            output_file = convert_md_to_docx(output_md_file, True)
        logger.info(f"{uid}, {task_id}, 材料质量评审报告生成成功, {output_file}")
        update_process_info(uid, task_id, "材料质量评审报告生成完毕", 100)
    except Exception as e:
        logger.error(f"材料质量评价生成失败: {str(e)}")

def generate_tb_suggestion(uid: int, task_id: int, review_type: str, review_topic: str,
                           criteria_markdown_file: str, review_files_path: str, sys_cfg: dict) -> None:
    """
    生成团队成员发展建议
    :param uid: 用户ID
    :param task_id: 任务ID
    :param review_type: 评审类型
    :param review_topic: 评审主题
    :param criteria_markdown_file: 评审标准 markdown 文件的全文路径
    :param review_files_path: 员工信息markdown文件的全文路径，可能包含多个文件绝对路径
    :param sys_cfg: 系统配置
    :return: 团队成员发展建议报告
    """
    logger.info(f"{uid}, {task_id}, generate_tb_suggestion, {review_type}, {review_topic}, "
        f"{criteria_markdown_file}, {review_files_path}, {sys_cfg}")
    try:
        builder = TeamBuilder(uid, task_id, review_type, review_topic,
            criteria_markdown_file, review_files_path, DataType.MD.value, sys_cfg)

        update_process_info(uid, task_id, "开始分析团队成员信息...", 10)
        suggestion_report = builder.generate_tb_suggestion(review_files_path)
        logger.info(f"{uid}, {task_id}, tb_suggestion_txt_generated")
        update_process_info(uid, task_id, "团队建设建议已生成...", 70)
        output_report_title = get_const('output_tb_suggestion_title',
                                        AppType.TEAM_BUILDING.name.lower()) or "团队建设建议报告"
        logger.info(f"output_report_title = {output_report_title}")
        doc_info = get_doc_info(task_id)
        output_file_path = doc_info[0]['output_file_path']
        logger.debug(f"output_file_path = {output_file_path}")

        # 保存结果
        output_md_file = save_content_to_md_file(suggestion_report, output_file_path, output_abs_path=True)
        output_file = convert_md_to_docx(output_md_file, True)

        logger.info(f"{uid}, {task_id}, tb_suggestion_txt_saved_to_output_file, {output_file}")
        update_process_info(uid, task_id, "团队建设建议报告生成完毕", 100)

    except Exception as e:
        logger.error(f"团队建设建议报告生成失败: {str(e)}")
        update_process_info(uid, task_id, f"团队建设建议报告生成失败: {str(e)}", 100)
        return f"团队建设建议报告生成失败: {str(e)}"


if __name__ == "__main__":

    file = "/home/rd/Downloads/manuscript.jpeg"
    file1 = TeamBuilder.preprocess_image(file)
    logger.info(f"file1 = {file1}")
    my_cfg = init_yml_cfg()
    tb = TeamBuilder(123, 123, "test", "test", "test",
"test", "test", my_cfg)
    ocr_txt = tb.call_llm_api_for_ocr(file1)
    logger.info(f"ocr_txt={ocr_txt}")