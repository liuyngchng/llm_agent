#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import os
import re
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "upload_doc"

def get_docx_md_file(docx_path: str, output_dir: str = OUTPUT_DIR) ->  Optional[str]:
    """
    将 Word 文档转换为 Markdown 格式

    使用前需要安装:
    1. pandoc: https://pandoc.org/installing.html
    2. pip install pypandoc

    Args:
        docx_path: Word 文档的路径
        output_dir: 输出目录，默认为 OUTPUT_DIR

    Returns:
        str: 生成的 Markdown 文件路径
        None: 转换失败时返回 None
    """
    # 输入验证
    if not docx_path or not os.path.exists(docx_path):
        logger.error(f"文档路径不存在或为空: {docx_path}")
        return None

    if not docx_path.lower().endswith('.docx'):
        logger.error(f"文件格式不支持，期望 .docx 文件: {docx_path}")
        return None

    # 确保输出目录存在
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        logger.error(f"创建输出目录失败: {output_dir}, 错误: {str(e)}")
        # 回退到临时目录
        output_dir = tempfile.gettempdir()

    # 生成输出文件路径
    input_file = Path(docx_path)
    output_filename = f"{input_file.stem}.md"
    output_path = os.path.join(output_dir, output_filename)

    try:
        import pypandoc

        # 检查 pandoc 是否可用
        pypandoc.get_pandoc_version()

        # 转换为 markdown，直接输出到文件
        output = pypandoc.convert_file(
            docx_path,
            'md',
            format='docx',
            outputfile=output_path
        )

        logger.info(f"文档转换成功: {docx_path} -> {output_path}")
        return output_path

    except ImportError:
        logger.error("pypandoc 未安装，请执行: pip install pypandoc")
        return None
    except FileNotFoundError:
        logger.error("pandoc 未安装，请从 https://pandoc.org/installing.html 安装")
        return None
    except Exception as e:
        logger.error(f"文档转换失败: {docx_path}, 错误: {str(e)}")

        # 清理可能生成的不完整文件
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        return None


def parse_markdown_structure_advanced(markdown_content: str, max_heading_level: int = 6,
      include_empty_sections: bool = False) -> list[dict[str, str]]:
    """
    增强版的markdown结构解析
    """
    lines = markdown_content.split('\n')
    structured_data = []

    current_hierarchy = []
    current_content = []

    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

    for line in lines:
        heading_match = heading_pattern.match(line.strip())

        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            # 检查标题层级是否在允许范围内
            if heading_level > max_heading_level:
                # 作为普通内容处理
                if current_hierarchy:
                    current_content.append(line)
                continue

            # 保存之前章节的内容
            if current_hierarchy and (current_content or include_empty_sections):
                hierarchy_key = '##'.join(current_hierarchy)
                content_text = '\n'.join(current_content).strip()
                if content_text or include_empty_sections:
                    structured_data.append({hierarchy_key: content_text})
                current_content = []

            # 更新层级
            current_hierarchy = current_hierarchy[:heading_level - 1]
            current_hierarchy.append(f"#{heading_text}")

        else:
            # 非标题行
            if current_hierarchy and line.strip():
                current_content.append(line)

    # 处理最后一个章节
    if current_hierarchy and (current_content or include_empty_sections):
        hierarchy_key = '##'.join(current_hierarchy)
        content_text = '\n'.join(current_content).strip()
        if content_text or include_empty_sections:
            structured_data.append({hierarchy_key: content_text})

    return structured_data

