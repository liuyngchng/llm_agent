#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import hashlib
import logging.config
import os
import re
from pathlib import Path

from common.const import OUTPUT_DIR, MAX_SECTION_LENGTH

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def save_content_to_md_file(md_txt: str, file_path: str, output_abs_path: bool = False) -> str:
    """
    :param md_txt markdown 格式的文本
    :param file_path 输出的markdown 文件的绝对路径
    :param output_abs_path: 是否需要输出 markdown 文件的绝对路径
    """
    try:
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_txt)
        # 根据参数决定返回相对路径还是绝对路径
        if output_abs_path:
            logger.info(f"成功保存文件: {file_path}")
            return str(file_path)
        else:
            logger.info(f"成功保存文件: {file_path}")
            return str(file_path)

    except Exception as e:
        # 处理可能的写入错误
        error_msg = f"写入文件时出错: {str(e)}"
        logging.error(error_msg)
        return error_msg


def convert_docx_to_md(docx_path: str, output_abs_path: bool = False) -> str:
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
        pypandoc.convert_file(
            docx_path, 'md', outputfile=md_path, format='docx',
            extra_args=[
                '--number-sections',          # 自动编号
                '--number-offset=0',          # 编号起始值
                '--top-level-division=chapter' # 顶层分割级别
            ]
        )

        abs_path = os.path.abspath(md_path)
        # 修复 Mermaid 图表格式
        _fix_mermaid_charts(abs_path)
        logger.info(f"成功转换文档: {docx_path} -> {md_path}")
        if output_abs_path:
            return abs_path
        else:
            return md_path

    except Exception as e:
        logger.error(f"docx_to_md_error, file {docx_path}, {str(e)}")
        return ""


def _fix_mermaid_charts(md_file_path: str):
    """
    修复 Markdown 文件中的 Mermaid 图表格式
    将转义的 Mermaid 代码转换为标准的 ```mermaid 代码块格式
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配转义的 Mermaid 代码块
        # 匹配 <mermaid> 标签格式
        mermaid_pattern1 = r'\\<mermaid\\>([\s\S]*?)\\</mermaid\\>'

        # 匹配可能存在的其他转义格式
        mermaid_pattern2 = r'&lt;mermaid&gt;([\s\S]*?)&lt;/mermaid&gt;'

        def replace_mermaid(match):
            mermaid_content = match.group(1)
            # 清理转义字符
            cleaned_content = mermaid_content.replace('\\', '').replace('&gt;', '>').replace('&lt;', '<')
            # 移除多余的换行和空格
            cleaned_content = re.sub(r'\n\s*\n', '\n', cleaned_content).strip()
            return f"\r\n```mermaid\n{cleaned_content}\n```\r\n"

        # 应用替换
        new_content = re.sub(mermaid_pattern1, replace_mermaid, content)
        new_content = re.sub(mermaid_pattern2, replace_mermaid, new_content)

        # 如果内容有变化，则写回文件
        if new_content != content:
            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            logger.info(f"已修复 Mermaid 图表格式: {md_file_path}")

    except Exception as e:
        logger.error(f"修复 Mermaid 图表失败: {md_file_path}, 错误: {str(e)}")


def convert_md_to_docx(md_path: str, output_abs_path: bool = False,
                       output_dir: str = None, output_filename: str = None) -> str:
    """
    将 Markdown 文件转换为 Word 文档

    # 使用前需要安装 pandoc: https://pandoc.org/installing.html
    # pip install pypandoc
    # sudo apt-get install pandoc
    :param md_path: Markdown 文件的路径
    :param output_abs_path: 是否输出绝对路径
    :param output_dir: 自定义输出目录，如果为None则使用默认OUTPUT_DIR
    :param output_filename: 自定义输出文件名，如果为None则使用原文件名
    :return: Word 文档保存在磁盘的路径
    """
    import pypandoc
    try:
        # 确定输出目录
        if output_dir is None:
            output_dir = OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        # 确定输出文件名
        if output_filename is None:
            md_file = Path(md_path)
            docx_filename = md_file.stem + ".docx"
        else:
            docx_filename = output_filename
            if not docx_filename.endswith('.docx'):
                docx_filename += '.docx'

        docx_path = os.path.join(output_dir, docx_filename)

        # 转换并保存到文件
        pypandoc.convert_file(md_path, 'docx', outputfile=docx_path, format='md')
        abs_path = os.path.abspath(docx_path)
        logger.info(f"成功转换文档: {md_path} -> {docx_path}")

        if output_abs_path:
            return abs_path
        else:
            return docx_path

    except FileNotFoundError:
        logger.error(f"Markdown文件不存在: {md_path}")
        return ""
    except Exception as e:
        logger.error(f"md_to_docx_error, file {md_path}, {str(e)}")
        return ""

def get_md_file_content(md_file_path:str, max_length: int = 327670) -> str:
    """
    从 Markdown 文件中获取文件内容
    :param md_file_path: Markdown 文件的绝对路径
    :param max_length: 可读取的最长字符数量
    :return: 文件内容
    """
    if not os.path.exists(md_file_path):
        logger.error(f"文件不存在, {md_file_path}")
        raise RuntimeError(f"文件不存在, {md_file_path}")
    try:

        with open(md_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if len(content) <max_length:
            return content
        else:
            return f"{content[:max_length]}\n\n ***请注意，文件字符数量超过 {max_length}，已截断。请通过目录按章节浏览。***"
    except FileNotFoundError:
        logger.error(f"Markdown文件不存在: {md_file_path}")
        raise FileNotFoundError(f"file_not_exist, {md_file_path}")
    except Exception as e:
        logger.error(f"error_occurred")
        return ""

def get_md_file_catalogue(md_file_path: str) -> dict:
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

def extract_sections_content(markdown_file_path: str, catalogue: dict, extract_heading_level: int = 2,
        max_content_length: int = MAX_SECTION_LENGTH) -> list[dict]:
    """
    按指定标题层级提取 Markdown 文件的章节内容，并将内容按最大长度分割

    Args:
        markdown_file_path: Markdown 文件的绝对路径
        catalogue: 目录结构
        extract_heading_level: 提取的标题层级，默认提取2级标题的内容
        max_content_length: 每个内容部分的最大长度
    Return:
        返回[{"heading1->header2" : ["content_part1 under heading2", "content_part2 under heading2"]}]
    """

    try:
        with open(markdown_file_path, 'r', encoding='utf-8') as file:
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

        def split_content_by_length(content: str, max_length: int) -> list[str]:
            """
            将内容按最大长度分割，尽量在段落边界处分割

            Args:
                content: 要分割的内容
                max_length: 每个部分的最大长度

            Returns:
                分割后的内容列表
            """
            if len(content) <= max_length:
                return [content]

            parts = []
            current_part = ""
            paragraphs = content.split('\n\n')

            for paragraph in paragraphs:
                # 如果当前段落加上分隔符的长度超过限制，且当前部分不为空，则保存当前部分
                if current_part and len(current_part) + len(paragraph) + 2 > max_length:
                    parts.append(current_part.strip())
                    current_part = ""

                # 如果单个段落就超过最大长度，需要按字符分割
                if len(paragraph) > max_length:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = ""

                    # 按字符分割长段落
                    start = 0
                    while start < len(paragraph):
                        end = start + max_length
                        if end < len(paragraph):
                            # 尽量在句子结束处分割
                            last_period = paragraph.rfind('.', start, end)
                            last_newline = paragraph.rfind('\n', start, end)
                            if last_period > start and (last_period - start) > max_length * 0.5:
                                end = last_period + 1
                            elif last_newline > start:
                                end = last_newline + 1

                        part = paragraph[start:end].strip()
                        if part:
                            parts.append(part)
                        start = end
                else:
                    # 添加段落到当前部分
                    if current_part:
                        current_part += '\n\n' + paragraph
                    else:
                        current_part = paragraph

            # 添加最后的部分
            if current_part:
                parts.append(current_part.strip())

            return parts

        def extract_content_at_level(node, parent_title="", current_level=1):
            """按指定层级提取章节内容并分割"""
            if isinstance(node, dict):
                current_title = node.get('title', '')
                level = node.get('level', 1)
                line_num = node.get('line', 1)

                full_title = f"{parent_title}->{current_title}" if parent_title else current_title

                # 如果当前节点层级等于或小于目标层级，提取内容
                if level == extract_heading_level:
                    # 提取本节内容
                    start_line = line_num

                    # 找到下一同级或更高级别章节的开始行
                    end_line = find_next_section_at_level(node, level, len(lines))

                    content = ''.join(lines[start_line - 1:end_line]).strip()

                    # 按最大长度分割内容
                    content_parts = split_content_by_length(content, max_content_length)

                    sections.append({
                        'title': full_title,
                        'level': level,
                        'content_parts': content_parts,
                        'start_line': start_line,
                        'end_line': end_line - 1 if end_line <= len(lines) else len(lines),
                        'total_length': len(content),
                        'parts_count': len(content_parts)
                    })

                    logger.debug(
                        f"提取章节 '{full_title}': 层级 {level}, 行 {start_line}-{end_line - 1}, "
                        f"总长度 {len(content)} 个字符, 分割为 {len(content_parts)} 部分")

                # 递归处理子节点
                children = node.get('children', {})
                for child in children.values():
                    extract_content_at_level(child, full_title, level)

        # 开始提取
        extract_content_at_level(catalogue)

        # 按行号排序
        sections.sort(key=lambda x: x['start_line'])

        logger.info(
            f"按{extract_heading_level}级标题提取了 {len(sections)} 个章节内容，最大内容长度限制: {max_content_length}")

        # 输出提取的章节信息
        for i, section in enumerate(sections[:5]):  # 只显示前5个作为样例
            logger.info(
                f"样例章节{i + 1}: '{section['title']}' (层级{section['level']}), "
                f"总长度: {section['total_length']}, 分割为: {section['parts_count']} 部分")

        # 转换为要求的格式: [{"heading1->header2": ["content_part1", "content_part2"]}]
        result = []
        for section in sections:
            result.append({
                section['title']: section['content_parts']
            })

        return result

    except Exception as e:
        logger.error(f"提取章节内容失败: {str(e)}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return []


def calculate_file_md5(file_stream) ->str:
    """计算文件流的MD5，支持大文件"""
    md5_hash = hashlib.md5()

    # 分块读取，避免内存占用过大
    for chunk in iter(lambda: file_stream.read(4096), b""):
        md5_hash.update(chunk)

    # 重置文件指针
    file_stream.seek(0)
    return md5_hash.hexdigest()

def split_md_file_with_catalogue(file_path: str, heading_level: int = 2) -> list[dict]:
    """
    将Markdown文件按指定标题级别分割，并返回包含目录结构的数据

    Args:
        file_path: Markdown文件路径
        heading_level: 标题级别，默认为2(##)

    Returns:
        包含章节信息的字典列表，每个字典包含:
        - level: 标题级别
        - title: 标题内容
        - content: 章节内容
        - children: 子章节列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return split_md_content_with_catalogue(content, heading_level)


def split_md_content_with_catalogue(content: str, heading_level: int=2) -> list[dict]:
    """
    将Markdown文件按指定标题级别分割，并返回包含目录结构的数据

    Args:
        content: Markdown 文本
        heading_level: 标题级别，默认为2(##)

    Returns:
        包含章节信息的字典列表，每个字典包含:
        - level: 标题级别
        - title: 标题内容
        - content: 章节内容
        - children: 子章节列表
    """
    # 根据heading_level构建正则表达式
    if heading_level == 1:
        pattern = r'^(# )(.+)$'
    elif heading_level == 2:
        pattern = r'^(## )(.+)$'
    elif heading_level == 3:
        pattern = r'^(### )(.+)$'
    else:
        raise ValueError("heading_level must be 1, 2, or 3")

    # 分割内容
    sections = []
    lines = content.split('\n')
    current_section = None

    for line in lines:
        match = re.match(pattern, line)
        if match:
            # 保存前一个章节
            if current_section:
                sections.append(current_section)

            # 开始新章节
            current_section = {
                'level': heading_level,
                'title': match.group(2).strip(),
                'content': line + '\n',
                'children': []
            }

        elif current_section is not None:
            # 检查是否是子标题（更高级别的标题）

            sub_match_1 = re.match(r'^(# )(.+)$', line)
            sub_match_2 = re.match(r'^(## )(.+)$', line) if heading_level == 1 else None
            sub_match_3 = re.match(r'^(### )(.+)$', line) if heading_level <= 2 else None

            sub_match = sub_match_1 or sub_match_2 or sub_match_3
            if sub_match and sub_match != match:
                # 这是子章节
                sub_level = len(sub_match.group(1).strip())
                current_section['children'].append({
                    'level': sub_level,
                    'title': sub_match.group(2).strip(),
                    'content': line + '\n',
                    'children': []
                })
            else:
                # 普通内容行
                current_section['content'] += line + '\n'

    # 添加最后一个章节
    if current_section:
        sections.append(current_section)

    return sections






# 使用示例
if __name__ == "__main__":
    my_docx_file = "/home/output_1763814024469.docx"  # 替换为你的docx文件路径
    my_md_file_path = convert_docx_to_md(my_docx_file, True)
    if not my_md_file_path:
        logger.info("转换失败")
    logger.info(f"Markdown文件已保存到: {my_md_file_path}")
    heading1 = "包依赖管理"
    txt = get_md_para_by_heading(my_md_file_path, heading1)
    logger.info(f"txt for {heading1}, {txt[:100]}...")

