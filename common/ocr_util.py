#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import base64
import os

import requests
import json
import time
import logging.config
from typing import Any, Optional
import mimetypes
from pathlib import Path

from common.sys_init import init_yml_cfg

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(category=InsecureRequestWarning)



class ImageOCR:
    def __init__(self, sys_cfg: dict):
        """
        初始化OCR识别器

        Args:
            sys_cfg: 系统配置
        """
        self.api_uri = sys_cfg['api'].get('ocr_api_uri', sys_cfg['api']['llm_api_uri'])
        self.api_token = sys_cfg['api'].get('ocr_api_key', sys_cfg['api']['llm_api_key'])
        self.model_name = sys_cfg['api'].get('ocr_model_name',
                           sys_cfg['api'].get('llm_model_name', 'qwen2-7b-vl'))


    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        """
        将图片转换为base64编码

        Args:
            image_path: 图片文件的绝对路径

        Returns:
            base64编码的图片数据URL
        """
        try:
            # 检查文件是否存在
            if not Path(image_path).exists():
                raise FileNotFoundError(f"图片文件不存在: {image_path}")

            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                mime_type = "image/jpeg"  # 默认类型

            # 读取并编码图片
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                base64_encoded = base64.b64encode(image_data).decode('utf-8')

            # 构建数据URL
            data_url = f"data:{mime_type};base64,{base64_encoded}"
            logger.debug(f"图片编码成功: {image_path} -> {mime_type}, 数据长度: {len(base64_encoded)}")
            return data_url

        except Exception as e:
            logger.error(f"图片编码失败: {str(e)}")
            raise

    def extract_text_from_image(self, image_path: str, timeout: int = 60) -> dict[str, Any]:
        """
        从图片中提取文字

        Args:
            image_path: 图片文件路径
            timeout: 请求超时时间（秒）

        Returns:
            包含识别结果的字典
        """
        start_time = time.time()

        try:
            logger.info(f"开始识别图片文字: {image_path}")

            # 1. 将图片转换为base64
            image_base64 = ImageOCR._image_to_base64(image_path)

            # 2. 构建API请求
            api_url = f"{self.api_uri}/chat/completions"

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_token}'
            }

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text",
                         "text": "请准确识别并输出图片中的所有文字内容。如果图片中没有文字，请返回'未识别到文字'。"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        }
                    ]
                }
            ]

            payload = {
                'model': self.model_name,
                'messages': messages,
                'max_tokens': 2000,
                'temperature': 0.1  # 低温度以获得更稳定的输出
            }

            # 打印请求信息（类似bash脚本的调试信息）
            logger.info(f"request_api: {api_url}")
            logger.debug(f"request_payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:200]}")

            # 3. 发送请求
            response = requests.post(
                url=api_url,
                headers=headers,
                json=payload,
                timeout=timeout,
                verify=False  # 跳过SSL验证，与bash脚本一致
            )

            # 4. 处理响应
            execution_time = time.time() - start_time
            logger.info(f"API响应状态: {response.status_code}, 执行时间: {execution_time:.2f}秒")

            if response.status_code == 200:
                result = response.json()

                # 提取返回内容
                content = result['choices'][0]['message']['content']
                usage = result.get('usage', {})

                logger.info(f"文字识别成功，返回内容长度: {len(content)}")

                return {
                    'success': True,
                    'text': content,
                    'usage': usage,
                    'execution_time': execution_time,
                    'model': self.model_name
                }

            else:
                error_msg = f"LLM API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)

                return {
                    'success': False,
                    'error': error_msg,
                    'execution_time': execution_time,
                    'status_code': response.status_code
                }

        except requests.exceptions.Timeout:
            execution_time = time.time() - start_time
            error_msg = f"请求超时: {timeout}秒"
            logger.error(error_msg)

            return {
                'success': False,
                'error': error_msg,
                'execution_time': execution_time
            }

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"OCR处理异常: {str(e)}"
            logger.error(error_msg)

            return {
                'success': False,
                'error': error_msg,
                'execution_time': execution_time
            }

    def extract_text_simple(self, image_path: str) -> Optional[str]:
        """
        简化版的文字提取，只返回识别到的文字内容

        Args:
            image_path: 图片文件路径

        Returns:
            识别到的文字内容，失败时返回None
        """
        result = self.extract_text_from_image(image_path)

        if result['success']:
            return result['text']
        else:
            logger.error(f"文字提取失败: {result.get('error', '未知错误')}")
            return None

    def extract_uml_diagram_from_image(self, image_path: str, diagram_type: str = "auto",
                                       detail_level: str = "normal", timeout: int = 90) -> dict[str, Any]:
        """
        从图片中提取和理解UML图、架构图、数据库ER图等技术图表内容

        Args:
            image_path: 图片文件路径
            diagram_type: 图表类型，可选值：
                - "auto": 自动识别（推荐）
                - "architecture": 系统架构图
                - "uml": UML类图/时序图等
                - "er": 数据库ER图
                - "flowchart": 流程图
                - "network": 网络拓扑图
            detail_level: 详细程度，可选值：
                - "brief": 简要描述主要组件和关系
                - "normal": 详细描述所有元素和关系（默认）
                - "comprehensive": 包含技术细节和属性
            timeout: 请求超时时间（秒）

        Returns:
            包含图表分析结果的字典
        """
        start_time = time.time()

        try:
            logger.info(f"开始分析技术图表: {image_path}, 类型: {diagram_type}, 详细度: {detail_level}")

            # 1. 将图片转换为base64
            image_base64 = self._image_to_base64(image_path)

            # 2. 构建专业的提示词
            system_prompt = """你是一位专业的软件架构师和系统分析师。你的任务是分析技术文档中的图表，
            包括但不限于：系统架构图、UML图、数据库ER图、流程图、网络拓扑图等。

            请遵循以下原则：
            1. 准确识别图表类型和用途
            2. 提取所有可见的文本元素
            3. 描述图表的结构、组件和它们之间的关系
            4. 保持技术准确性和专业性
            5. 如果图表包含代码、接口定义或技术规范，请完整提取"""

            # 根据图表类型和详细程度调整用户提示词
            diagram_type_instruction = ""
            if diagram_type != "auto":
                diagram_type_instruction = f"这是一个{diagram_type}图表，请按照此类图表的专业标准进行分析。"
            else:
                diagram_type_instruction = "请自动识别图表类型，并按照相应类型的专业标准进行分析。"

            detail_instructions = {
                "brief": "请提供简要描述，重点说明图表的主要组件、核心关系和整体架构。",
                "normal": "请提供详细描述，包括所有可见的文本元素、组件之间的关系、数据流向和关键接口。",
                "comprehensive": "请提供全面的技术分析，包括：组件详细属性、接口定义、技术栈信息、部署关系、性能考虑等所有可见的技术细节。"
            }

            user_prompt = f"""{diagram_type_instruction}
            {detail_instructions.get(detail_level, detail_instructions["normal"])}

            请按照以下结构化格式输出分析结果：

            1. 【图表类型识别】
               - 类型： [识别的图表类型，如：微服务架构图、UML类图、数据库ER图等]
               - 用途： [图表的主要用途]
               - 专业领域： [涉及的技术领域，如：云计算、数据库设计、系统集成等]

            2. 【图表总体描述】
               - 核心主题： [图表的中心主题]
               - 主要层次： [识别出的层次结构，如：表示层、服务层、数据层等]
               - 设计模式： [如果可识别，指出使用的设计模式]

            3. 【组件与元素分析】
               按层次或分组列出所有可见的组件、模块、实体、节点等，包括它们的：
               - 名称/标签
               - 类型/角色
               - 技术栈/实现方式（如果可识别）
               - 与其他元素的关系

            4. 【关系与连接分析】
               描述组件之间的所有关系：
               - 连接类型： [如：API调用、数据流、继承关系、关联关系等]
               - 方向性： [单向/双向]
               - 协议/接口： [如果标注了协议或接口]

            5. 【数据流与业务流程】
               - 主要数据流： [描述图中的数据流向]
               - 关键业务流程： [如果图表描述了业务流程]

            6. 【关键发现与技术洞察】
               - 架构特点： [如：分布式、微服务、事件驱动等]
               - 潜在的技术决策： [从图表中推断出的设计决策]
               - 可改进点或风险： [基于最佳实践的分析]

            7. 【提取的原始文本】
               以清单形式列出图片中所有可见的文字内容（保持原格式）：
               - [文本1]
               - [文本2]
               - ...

            如果图片中不包含技术图表，或者无法识别为有效的技术图表，请明确指出并尽可能描述图片内容。
            """

            # 3. 构建API请求
            api_url = f"{self.api_uri}/chat/completions"

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_token}'
            }

            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64,
                                "detail": "high"  # 使用高细节模式以获得更好的图表识别
                            }
                        }
                    ]
                }
            ]

            # 根据详细程度调整token数量
            max_tokens_map = {
                "brief": 1500,
                "normal": 3000,
                "comprehensive": 5000
            }

            payload = {
                'model': self.model_name,
                'messages': messages,
                'max_tokens': max_tokens_map.get(detail_level, 3000),
                'temperature': 0.1,  # 低温度确保技术描述的准确性
                'top_p': 0.9
            }

            logger.info(f"图表分析请求: {api_url}, {self.model_name}")
            logger.debug(f"请求参数: 类型={diagram_type}, 详细度={detail_level}")

            # 4. 发送请求
            response = requests.post(
                url=api_url,
                headers=headers,
                json=payload,
                timeout=timeout,
                verify=False
            )

            # 5. 处理响应
            execution_time = time.time() - start_time
            logger.info(f"API响应状态: {response.status_code}, 执行时间: {execution_time:.2f}秒")

            if response.status_code == 200:
                result = response.json()

                # 提取返回内容
                content = result['choices'][0]['message']['content']
                usage = result.get('usage', {})

                # 尝试从响应中提取图表类型（如果模型识别到了）
                diagram_type_detected = "未知"
                lines = content.split('\n')
                for line in lines:
                    if '类型：' in line or '图表类型：' in line:
                        diagram_type_detected = line.split('：')[-1].strip()
                        break

                logger.info(f"图表分析成功，类型: {diagram_type_detected}, 内容长度: {len(content)}字符")

                return {
                    'success': True,
                    'analysis': content,
                    'diagram_type': diagram_type_detected,
                    'requested_type': diagram_type,
                    'detail_level': detail_level,
                    'usage': usage,
                    'execution_time': execution_time,
                    'model': self.model_name,
                    'raw_response': result  # 保留原始响应，便于调试
                }

            else:
                error_msg = f"图表分析API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)

                return {
                    'success': False,
                    'error': error_msg,
                    'execution_time': execution_time,
                    'status_code': response.status_code
                }

        except requests.exceptions.Timeout:
            execution_time = time.time() - start_time
            error_msg = f"图表分析请求超时: {timeout}秒"
            logger.error(error_msg)

            return {
                'success': False,
                'error': error_msg,
                'execution_time': execution_time
            }

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"图表分析处理异常: {str(e)}"
            logger.error(error_msg)

            return {
                'success': False,
                'error': error_msg,
                'execution_time': execution_time
            }

    def extract_uml_simple(self, image_path: str) -> Optional[str]:
        """
        简化版的图表分析，只返回分析内容

        Args:
            image_path: 图片文件路径

        Returns:
            图表分析内容，失败时返回None
        """
        result = self.extract_uml_diagram_from_image(
            image_path,
            diagram_type="auto",
            detail_level="normal"
        )

        if result['success']:
            return result['analysis']
        else:
            logger.error(f"图表分析失败: {result.get('error', '未知错误')}")
            return None

    def extract_text_and_diagrams(self, document_paths: list[str],
                                  include_diagrams: bool = True) -> dict[str, Any]:
        """
        批量处理文档中的图片，提取文字和图表分析

        Args:
            document_paths: 图片文件路径列表
            include_diagrams: 是否包含图表分析

        Returns:
            包含所有提取结果的字典
        """
        results = {
            'text_content': [],
            'diagram_analyses': [],
            'errors': [],
            'total_execution_time': 0
        }

        start_time = time.time()

        for idx, img_path in enumerate(document_paths, 1):
            try:
                logger.info(f"处理文档 ({idx}/{len(document_paths)}): {img_path}")

                # 提取文字
                text_result = self.extract_text_from_image(img_path)

                if text_result['success']:
                    results['text_content'].append({
                        'file': img_path,
                        'text': text_result['text'],
                        'execution_time': text_result['execution_time']
                    })
                else:
                    results['errors'].append({
                        'file': img_path,
                        'type': 'text_extraction',
                        'error': text_result.get('error', '未知错误')
                    })

                # 提取图表分析（如果启用）
                if include_diagrams:
                    diagram_result = self.extract_uml_diagram_from_image(img_path)

                    if diagram_result['success']:
                        results['diagram_analyses'].append({
                            'file': img_path,
                            'diagram_type': diagram_result['diagram_type'],
                            'analysis': diagram_result['analysis'],
                            'execution_time': diagram_result['execution_time']
                        })
                    else:
                        results['errors'].append({
                            'file': img_path,
                            'type': 'diagram_analysis',
                            'error': diagram_result.get('error', '未知错误')
                        })

            except Exception as e:
                error_msg = f"处理文件异常 {img_path}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append({
                    'file': img_path,
                    'type': 'processing',
                    'error': error_msg
                })

        results['total_execution_time'] = time.time() - start_time
        logger.info(f"批量处理完成: 成功提取{len(results['text_content'])}个文本, "
                    f"{len(results['diagram_analyses'])}个图表, 错误: {len(results['errors'])}")

        return results


# 使用示例
def test_get_txt():
    my_cfg = init_yml_cfg()
    # 初始化OCR
    ocr = ImageOCR(my_cfg)

    # 识别图片文字
    image_path = "/home/rd/workspace/llm_agent/deploy/arch.drawio.png"  # 替换为你的图片路径

    try:
        # 方式1：获取详细信息
        result = ocr.extract_uml_diagram_from_image(image_path)
        logger.info(f"识别结果: {result}")
        if result['success']:
            logger.info("✅ 文字识别成功！")
            logger.info(f"📝 识别结果: {result['text']}")
            logger.info(f"⏱️ 执行时间: {result['execution_time']:.2f}秒")
            logger.info(f"🤖 使用模型: {result['model']}")
            if 'usage' in result:
                logger.info(f"📊 Token使用: {result['usage']}")
        else:
            logger.info(f"❌ 识别失败: {result.get('error', '未知错误')}")

        logger.info("\n" + "=" * 50 + "\n")

        # 方式2：只获取文字内容
        text = ocr.extract_text_simple(image_path)
        if text:
            logger.info(f"简化版结果: {text}")

    except Exception as e:
        logger.exception(f"OCR处理异常, {image_path}")


# 在你的测试函数中添加
def test_get_uml_diagram():
    my_cfg = init_yml_cfg()
    ocr = ImageOCR(my_cfg)

    # 测试图表分析
    diagram_image = "/home/rd/workspace/llm_agent/deploy/arch.drawio.png"

    # 详细分析架构图
    result = ocr.extract_uml_diagram_from_image(
        diagram_image,
        diagram_type="architecture",  # 明确指定类型
        detail_level="comprehensive"  # 最详细的分析
    )

    if result['success']:
        logger.info(f"✅ 图表分析成功！类型: {result['diagram_type']}")
        logger.info(f"📊 分析内容摘要: {result['analysis'][:500]}...")  # 只显示前500字符

        # 保存分析结果
        output_file = f"{diagram_image}.analysis.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result['analysis'])
        logger.info(f"💾 分析结果已保存至: {output_file}")


def get_txt_with_paddle(img_path: str) -> str:
    from paddleocr import PaddleOCR

    # 指定你手动下载的模型路径
    ocr = PaddleOCR(
        det_model_dir='PaddleOCR_models/ch_PP-OCRv4_det_infer',  # 检测模型路径
        rec_model_dir='PaddleOCR_models/ch_PP-OCRv4_rec_infer',  # 识别模型路径
        cls_model_dir='PaddleOCR_models/ch_ppocr_mobile_v2.0_cls_infer',  # 分类模型路径
        use_angle_cls=True,
        lang='ch'
    )

    # ocr = PaddleOCR(use_angle_cls=True, lang='ch')

    # 进行一次OCR识别，触发下载（如果模型未下载）
    result = ocr.ocr(img_path, cls=True)

    # 打印结果
    for idx in range(len(result)):
        res = result[idx]
        for line in res:
            print(line)



if __name__ == "__main__":
    # test_get_txt()
    test_get_uml_diagram()