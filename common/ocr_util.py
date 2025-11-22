#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import base64
import requests
import json
import time
import logging.config
from typing import Any, Optional
import mimetypes
from pathlib import Path

from common.sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
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
        self.api_uri = sys_cfg['api']['llm_api_uri']
        self.api_token = sys_cfg['api']['llm_api_key']
        self.model_name = sys_cfg['api'].get('llm_model_name', 'qwen2-7b-vl')


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
                error_msg = f"API调用失败: {response.status_code} - {response.text}"
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


# 使用示例
def test():
    my_cfg = init_yml_cfg()
    # 初始化OCR
    ocr = ImageOCR(my_cfg)

    # 识别图片文字
    image_path = "/home/rd/Downloads/manuscript.jpeg"  # 替换为你的图片路径

    try:
        # 方式1：获取详细信息
        result = ocr.extract_text_from_image(image_path)

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
    test()