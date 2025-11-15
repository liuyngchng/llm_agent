#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import os
from pathlib import Path

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output_doc"


def get_docx_md_file_path(docx_path: str, output_abs_path: bool = False) -> str:
    """
    # 使用前需要安装 pandoc: https://pandoc.org/installing.html
    # pip install pypandoc
    # sudo apt-get install pandoc
    :param docx_path: Word 文档的路径
    :param output_abs_path: 是否输出绝对路径
    :return: markdown 文档保存在磁盘的路径
    """
    import pypandoc
    try:
        # 确保输出目录存在
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 获取原文件名（不含扩展名）
        docx_file = Path(docx_path)
        md_filename = docx_file.stem + ".md"
        md_path = os.path.join(OUTPUT_DIR, md_filename)

        # 转换并保存到文件
        pypandoc.convert_file(docx_path, 'md', outputfile=md_path, format='docx')
        abs_path = os.path.abspath(md_path)
        logger.info(f"成功转换文档: {docx_path} -> {md_path}")
        if output_abs_path:
            return abs_path
        else:
            return md_path

    except Exception as e:
        logger.error(f"docx_to_md_error, file {docx_path}, {str(e)}")
        return ""

def get_md_file_content(md_file_path:str) -> str:
    """
    从 Markdown 文件中获取文件内容
    :param md_file_path: Markdown 文件路径
    :return: 文件内容
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if len(content) <32767:
            return content
        else:
            return f"{content[:32767]}\n\n ***请注意，文件全文太长，已截断。请通过目录按章节浏览。***"
    except FileNotFoundError:
        logger.error(f"Markdown文件不存在: {md_file_path}")
        raise FileNotFoundError(f"file_not_exist, {md_file_path}")
    except Exception as e:
        logger.error(f"error_occurred")
        return ""

def get_md_catalog(md_file_path: str) -> dict:
    """
    从 Markdown 文件中获取目录
    :param md_file_path: Markdown 文件路径
    :return: 目录内容字典，多级目录嵌套
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        catalog = {}
        current_levels = {0: catalog}  # 用于跟踪各级别的当前节点
        last_level = 0

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # 检查标题行 (从 # 到 ######)
            if line.startswith('#'):
                # 计算标题级别
                level = 0
                for char in line:
                    if char == '#':
                        level += 1
                    else:
                        break

                if level > 6:  # Markdown 最多支持6级标题
                    continue

                # 提取标题文本
                title = line[level:].strip()
                if not title:  # 跳过空标题
                    continue

                # 创建标题节点
                node = {
                    'title': title,
                    'level': level,
                    'line': line_num,
                    'children': {}
                }

                # 找到父级别
                parent_level = level - 1
                while parent_level >= 0 and parent_level not in current_levels:
                    parent_level -= 1

                if parent_level >= 0:
                    # 添加到父级的children中
                    parent_node = current_levels[parent_level]
                    if 'children' not in parent_node:
                        parent_node['children'] = {}
                    parent_node['children'][title] = node
                else:
                    # 作为根节点
                    catalog[title] = node

                # 更新当前级别
                current_levels[level] = node
                last_level = level

        logger.info(f"成功提取目录结构，共找到 {len(catalog)} 个根级标题")
        return catalog

    except FileNotFoundError:
        logger.error(f"Markdown文件不存在: {md_file_path}")
        return {}
    except Exception as e:
        logger.error(f"提取目录失败: {md_file_path}, 错误: {str(e)}")
        return {}


def get_md_para_by_heading(md_file_path: str, heading1: str, heading2: str = None) -> str:
    """
    从 Markdown 文件中获取指定标题下的文本内容
    :param md_file_path: Markdown 文件路径
    :param heading1: 一级标题
    :param heading2: 二级标题（可选）
    :return: 指定标题下的文本内容（包含子标题）
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        start_index = -1
        end_index = -1
        current_heading1 = None
        current_heading2 = None
        found_target = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 跳过空行（但保留空行的原始位置）
            if not line_stripped:
                continue

            # 检查标题行
            if line_stripped.startswith('#'):
                # 计算标题级别和提取标题文本
                level = 0
                for char in line_stripped:
                    if char == '#':
                        level += 1
                    else:
                        break

                title = line_stripped[level:].strip()

                if level == 1:
                    # 遇到新的一级标题
                    current_heading1 = title
                    current_heading2 = None

                    # 如果已经找到目标内容，设置结束位置
                    if found_target:
                        end_index = i
                        break

                    # 检查是否匹配目标一级标题
                    if title == heading1:
                        if heading2 is None:
                            # 只需要一级标题，开始记录（包含一级标题本身）
                            start_index = i
                            found_target = True
                        else:
                            # 需要继续寻找二级标题
                            found_target = False

                elif level == 2 and current_heading1 == heading1:
                    # 在目标一级标题下的二级标题
                    current_heading2 = title

                    # 如果已经找到目标内容，设置结束位置
                    if found_target and heading2 is not None and title != heading2:
                        end_index = i
                        break

                    # 检查是否匹配目标二级标题
                    if heading2 is not None and title == heading2:
                        # 包含二级标题本身
                        start_index = i
                        found_target = True

                elif level == 1 and found_target:
                    # 遇到新的一级标题，结束当前部分
                    end_index = i
                    break

        # 如果没有设置结束位置且已经找到目标，则到文件末尾
        if found_target and end_index == -1:
            end_index = len(lines)

        # 提取内容
        if start_index != -1 and end_index != -1 and start_index < end_index:
            content_lines = lines[start_index:end_index]

            # 直接返回内容，保留所有子标题和格式
            content = ''.join(content_lines).strip()

            logger.info(f"成功提取内容: {heading1}" + (f" -> {heading2}" if heading2 else ""))
            return content

        logger.warning(f"未找到指定标题内容: {heading1}" + (f" -> {heading2}" if heading2 else ""))
        return ""

    except FileNotFoundError:
        logger.error(f"Markdown文件不存在: {md_file_path}")
        return ""
    except Exception as e:
        logger.error(f"提取内容失败: {md_file_path}, 错误: {str(e)}")
        return ""

# 使用示例
if __name__ == "__main__":
    my_docx_file = "/home/rd/Downloads/java.tutorial.docx"  # 替换为你的docx文件路径
    my_md_file_path = get_docx_md_file_path(my_docx_file)
    if not my_md_file_path:
        logger.info("转换失败")
    logger.info(f"Markdown文件已保存到: {my_md_file_path}")
    heading1 = "包依赖管理"
    txt = get_md_para_by_heading(my_md_file_path, heading1)
    logger.info(f"txt for {heading1}, {txt[:100]}...")
