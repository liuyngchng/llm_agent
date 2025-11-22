#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
import os
import re
from pathlib import Path
import pandas as pd

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output_doc"


def convert_md_to_xlsx(markdown_file_path: str, output_abs_path: bool = False) -> str:
    """
    将 markdown 文件中的表格转换为 excel 表格，如果markdown 中有多个表格，则excel文件中就有多个sheet页
    :param markdown_file_path: markdown 文件的绝对路径
    :param output_abs_path: 是否输出绝对路径
    return
        xlsx 文件的路径
    """
    try:
        # 确保输出目录存在
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 获取原文件名（不含扩展名）并生成 excel 文件名
        md_file = Path(markdown_file_path)
        xlsx_filename = md_file.stem + ".xlsx"
        xlsx_path = os.path.join(OUTPUT_DIR, xlsx_filename)

        # 读取 markdown 文件内容
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析 markdown 内容，提取表格和工作表信息
        tables_data = parse_markdown_tables(content)

        if not tables_data:
            logger.warning(f"在 Markdown 文件中未找到表格: {markdown_file_path}")
            return ""

        # 创建 Excel writer
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            sheet_count = 0

            for i, table_data in enumerate(tables_data):
                sheet_name = table_data.get('sheet_name', f'Sheet{i + 1}')
                df = table_data.get('dataframe')

                if df is not None and not df.empty:
                    # 清理 sheet 名称（Excel sheet 名称限制）
                    sheet_name = clean_sheet_name(sheet_name, i + 1)

                    # 写入 Excel
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    sheet_count += 1

                    logger.debug(f"成功写入工作表: {sheet_name}, 数据形状: {df.shape}")

        abs_path = os.path.abspath(xlsx_path)
        logger.info(f"成功转换 Markdown 文件: {markdown_file_path} -> {abs_path}, 包含 {sheet_count} 个工作表")

        return abs_path if output_abs_path else xlsx_path

    except Exception as e:
        logger.error(f"md_to_xlsx_error, file {markdown_file_path}, {str(e)}")
        return ""


def parse_markdown_tables(content: str) -> list:
    """
    解析 markdown 内容，提取表格数据和工作表名称
    """
    tables_data = []

    # 分割内容为不同的部分（基于工作表标题）
    sections = split_markdown_sections(content)

    for section in sections:
        sheet_name = section.get('sheet_name', '')
        section_content = section.get('content', '')

        # 在当前章节中查找所有表格
        tables = extract_tables_from_content(section_content)

        for j, table in enumerate(tables):
            df = markdown_table_to_dataframe(table)
            if df is not None:
                # 如果只有一个表格，使用章节名作为工作表名
                # 如果有多个表格，添加序号
                final_sheet_name = sheet_name
                if len(tables) > 1:
                    final_sheet_name = f"{sheet_name}_表格{j + 1}" if sheet_name else f"Table{j + 1}"

                tables_data.append({
                    'sheet_name': final_sheet_name,
                    'dataframe': df,
                    'original_table': table
                })

    # 如果没有找到工作表标题，但找到了表格，创建默认工作表
    if not tables_data:
        tables = extract_tables_from_content(content)
        for i, table in enumerate(tables):
            df = markdown_table_to_dataframe(table)
            if df is not None:
                tables_data.append({
                    'sheet_name': f'Table{i + 1}',
                    'dataframe': df,
                    'original_table': table
                })

    return tables_data


def split_markdown_sections(content: str) -> list:
    """
    根据工作表标题分割 markdown 内容
    支持的工作表标题格式：
    - ## 工作表: 名称
    - ## 📊 工作表: 名称
    - ## Sheet: 名称
    """
    sections = []

    # 匹配工作表标题的正则表达式
    sheet_pattern = r'^##\s*[📊\s]*工作表:\s*(.+?)$|^##\s*Sheet:\s*(.+?)$'

    lines = content.split('\n')
    current_section = {'sheet_name': '', 'content': ''}
    in_section = False

    for line in lines:
        sheet_match = re.match(sheet_pattern, line.strip(), re.IGNORECASE)
        if sheet_match:
            # 找到新的工作表标题
            if in_section and current_section['content'].strip():
                sections.append(current_section.copy())

            # 提取工作表名称
            sheet_name = sheet_match.group(1) or sheet_match.group(2)
            current_section = {
                'sheet_name': sheet_name.strip(),
                'content': ''
            }
            in_section = True
        else:
            if in_section:
                current_section['content'] += line + '\n'
            else:
                # 没有明确工作表标题的内容
                if line.strip() and not current_section['sheet_name']:
                    current_section['content'] += line + '\n'

    # 添加最后一个章节
    if in_section and current_section['content'].strip():
        sections.append(current_section)

    return sections


def extract_tables_from_content(content: str) -> list:
    """
    从 markdown 内容中提取表格
    返回表格的原始文本列表
    """
    tables = []

    # 表格模式：以 | 开始的行，包含表头和分隔线
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 检查是否是表格开始（包含 | 的行）
        if line.startswith('|') and '|' in line[1:]:
            table_lines = [line]
            i += 1

            # 继续收集表格行，直到遇到非表格行
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith('|') and '|' in next_line[1:]:
                    table_lines.append(next_line)
                    i += 1
                else:
                    break

            # 验证表格格式（至少包含表头和分隔线）
            if len(table_lines) >= 2 and any('---' in line for line in table_lines):
                tables.append('\n'.join(table_lines))

        i += 1

    return tables


def markdown_table_to_dataframe(table_text: str) -> pd.DataFrame:
    """
    将 markdown 表格文本转换为 pandas DataFrame
    """
    try:
        lines = [line.strip() for line in table_text.split('\n') if line.strip()]

        if len(lines) < 2:
            return None

        # 分离表头、分隔线和数据行
        header_line = lines[0]
        separator_line = lines[1] if len(lines) > 1 else ""
        data_lines = lines[2:] if len(lines) > 2 else []

        # 解析表头
        headers = parse_table_row(header_line)

        # 解析数据行
        data = []
        for data_line in data_lines:
            # 跳过分隔线
            if '---' in data_line or '===' in data_line:
                continue
            row_data = parse_table_row(data_line)
            if len(row_data) == len(headers):
                data.append(row_data)

        # 创建 DataFrame
        if headers and data:
            df = pd.DataFrame(data, columns=headers)
            return df
        elif headers:
            # 只有表头的情况
            df = pd.DataFrame(columns=headers)
            return df
        else:
            return None

    except Exception as e:
        logger.warning(f"解析 markdown 表格失败: {str(e)}")
        return None


def parse_table_row(row_line: str) -> list:
    """
    解析表格行，分割单元格内容
    """
    # 移除行首尾的 |
    cleaned_line = row_line.strip()
    if cleaned_line.startswith('|'):
        cleaned_line = cleaned_line[1:]
    if cleaned_line.endswith('|'):
        cleaned_line = cleaned_line[:-1]

    # 分割单元格
    cells = [cell.strip() for cell in cleaned_line.split('|')]
    return cells


def clean_sheet_name(sheet_name: str, index: int) -> str:
    """
    清理工作表名称，确保符合 Excel 限制
    - 最大 31 个字符
    - 不能包含特殊字符: \ / * ? [ ] :
    """
    # 替换非法字符
    cleaned = re.sub(r'[\\/*?\[\]:]', '_', sheet_name)

    # 截断到最大长度
    if len(cleaned) > 31:
        cleaned = cleaned[:28] + f"_{index}"

    # 确保不为空
    if not cleaned.strip():
        cleaned = f"Sheet{index}"

    return cleaned


def convert_md_to_xlsx_simple(markdown_file_path: str, output_abs_path: bool = False) -> str:
    """
    简化版本：直接将所有表格转换为工作表，不解析工作表标题
    """
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        md_file = Path(markdown_file_path)
        xlsx_filename = md_file.stem + ".xlsx"
        xlsx_path = os.path.join(OUTPUT_DIR, xlsx_filename)

        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 直接提取所有表格
        tables = extract_tables_from_content(content)

        if not tables:
            logger.warning(f"在 Markdown 文件中未找到表格: {markdown_file_path}")
            return ""

        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            for i, table in enumerate(tables):
                df = markdown_table_to_dataframe(table)
                if df is not None and not df.empty:
                    sheet_name = clean_sheet_name(f"Table{i + 1}", i + 1)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

        abs_path = os.path.abspath(xlsx_path)
        logger.info(f"成功转换 Markdown 文件: {markdown_file_path} -> {abs_path}")

        return abs_path if output_abs_path else xlsx_path

    except Exception as e:
        logger.error(f"md_to_xlsx_simple_error, file {markdown_file_path}, {str(e)}")
        return ""


# 使用示例
if __name__ == "__main__":
    # 测试转换功能
    my_md_file = "/home/rd/workspace/llm_agent/tests/apps/paper_review/formatted_report.md"  # 替换为你的 Markdown 文件路径
    xlsx_file_path = convert_md_to_xlsx(my_md_file, True)

    if xlsx_file_path:
        logger.info(f"Excel 文件已保存到: {xlsx_file_path}")
    else:
        logger.info("转换失败")