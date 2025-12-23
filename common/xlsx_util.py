#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import functools
import logging.config
import os
import re
from pathlib import Path
import pandas as pd

from common.const import OUTPUT_DIR

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

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
    - 不能包含特殊字符: \\ / * ? [ ] :
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

def convert_xlsx_to_md(excel_path: str, include_sheet_names: bool = True,
                       output_abs_path: bool = False) -> str:
    """
    高级版本：将Excel转换为更易读的Markdown格式
    """
    import pandas as pd
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        excel_file = Path(excel_path)
        md_filename = excel_file.stem + ".md"
        md_path = os.path.join(OUTPUT_DIR, md_filename)

        excel_file_obj = pd.ExcelFile(excel_path)
        markdown_parts = []

        for idx, sheet_name in enumerate(excel_file_obj.sheet_names, start=1):
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine='openpyxl')
            if df.empty:
                continue

            if include_sheet_names:
                markdown_parts.append(f"## {idx}. 📊 : 工作表{idx} {sheet_name}")
                markdown_parts.append("")
            df = df.fillna('')
            df = df.replace(r'^Unnamed.*$', '', regex=True)
            df.columns = ['' if 'Unnamed' in str(col) else col
                          for i, col in enumerate(df.columns)]
            df = df.replace(r'\n', '<br>', regex=True)
            # markdown_parts.append("> ⚠️ **表格预览** (复杂表格建议查看原文件)")
            markdown_parts.append("")
            markdown_table = df.to_markdown(index=False, tablefmt="pipe")
            markdown_parts.append(markdown_table)

            markdown_parts.append("")  # 空行分隔

        markdown_content = "\n".join(markdown_parts)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        abs_path = os.path.abspath(md_path)
        logger.info(f"成功转换 Excel 文件: {excel_path} -> {abs_path}")
        return abs_path if output_abs_path else md_path

    except Exception as e:
        logger.exception(f"excel_to_md_error, file {excel_path}, {str(e)}")
        return ""


def convert_xlsx_to_html(input_excel, output_html=None, sheet_name=None, output_abs_path: bool = False)->str:
    """
    将Excel完美转换为HTML，保留所有格式
    pip install xlsx2html
    Args:
        input_excel: 输入的Excel文件路径
        output_html: 输出的HTML文件路径（可选，默认为同目录同名.html）
        sheet_name: 工作表名称（可选，默认为第一个工作表）
        output_abs_path: 是否输出转换完成后文件的绝对路径
    """

    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if output_html is None:
        excel_file = Path(input_excel)
        output_html = excel_file.stem + ".html"
    html_path = os.path.join(OUTPUT_DIR, output_html)
    from xlsx2html import xlsx2html
    try:
        if sheet_name:
            xlsx2html(input_excel, html_path, sheet=sheet_name)
        else:
            xlsx2html(input_excel, html_path)

        logger.info(f"转换成功, 输入文件: {input_excel}, 输出文件: {html_path}")
        if output_abs_path:
            return os.path.abspath(str(html_path))
        else:
            return str(html_path)

    except Exception as e:
        logger.exception(f"❌ 转换失败: {e}")
        return ""


def convert_xlsx_all_sheet_to_html_with_navi(xlsx_file_full_path: str) -> str:
    """
    转换 Excel 中的所有工作表到一个HTML文件，同时为多个Excel表格添加导航栏
    :param xlsx_file_full_path
    """
    import pandas as pd
    import hashlib
    from xlsx2html import xlsx2html
    import datetime

    excel_file = pd.ExcelFile(xlsx_file_full_path)
    sheet_names = excel_file.sheet_names

    # 创建唯一的输出文件名
    file_md5 = hashlib.md5(Path(xlsx_file_full_path).name.encode('utf-8')).hexdigest()
    output_html = f"{file_md5}_all_sheets.html"
    html_path = os.path.join(OUTPUT_DIR, output_html)

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 为每个工作表生成HTML内容
    sheet_contents = {}
    for sheet_name in sheet_names:
        try:
            # 使用xlsx2html转换每个工作表，但不保存到文件
            from io import StringIO
            html_output = StringIO()
            xlsx2html(xlsx_file_full_path, html_output, sheet=sheet_name)
            html_content = html_output.getvalue()

            # 提取表格主体部分
            # 查找<table>标签开始的位置
            table_start = html_content.find('<table')
            if table_start != -1:
                # 找到</table>结束标签
                table_end = html_content.find('</table>', table_start)
                if table_end != -1:
                    table_content = html_content[table_start:table_end + 8]  # +8 for '</table>'
                else:
                    table_content = html_content[table_start:]
            else:
                table_content = html_content

            sheet_contents[sheet_name] = table_content
            logger.info(f"成功转换工作表: {sheet_name}")

        except Exception as e:
            logger.error(f"转换工作表失败 {xlsx_file_full_path}[{sheet_name}]: {e}")
            sheet_contents[sheet_name] = f'<div class="error-message">工作表转换失败: {str(e)}</div>'

    # 创建包含所有工作表的单一HTML文件
    nav_html = _create_single_html_page(xlsx_file_full_path, sheet_names, sheet_contents, current_time)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(nav_html)

    abs_html_path = os.path.abspath(html_path)
    logger.info(f"单一HTML文件已创建: {abs_html_path} (包含 {len(sheet_names)} 个工作表)")
    return abs_html_path


def _create_single_html_page(input_excel, sheet_names, sheet_contents, current_time):
    """
    创建包含所有工作表的单一HTML页面
    """
    from pathlib import Path

    base_name = Path(input_excel).stem

    # 生成导航菜单HTML
    nav_menu = ''.join([
        f'<li><a href="#sheet_{i + 1}" onclick="showSheet({i})">{i + 1}. {sheet_name}</a></li>'
        for i, sheet_name in enumerate(sheet_names)
    ])

    # 生成工作表内容HTML
    sheet_sections = ''.join([
        f'''
        <div id="sheet_{i + 1}" class="sheet-content" {"style='display:block'" if i == 0 else "style='display:none'"}>
            <div class="sheet-header">
                <h3><i class="fas fa-table"></i> {i + 1}. {sheet_name}</h3>
                <div class="sheet-meta">
                    <span><i class="fas fa-calendar-alt"></i> 转换时间: {current_time}</span>
                    <span><i class="fas fa-hashtag"></i> 工作表索引: {i + 1}/{len(sheet_names)}</span>
                </div>
            </div>
            <div class="table-container">
                {sheet_contents.get(sheet_name, '<div class="no-data">无数据</div>')}
            </div>
        </div>
        '''
        for i, sheet_name in enumerate(sheet_names)
    ])

    html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{base_name} - Excel 所有工作表</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}

        body {{
            background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        .container {{
            display: flex;
            flex: 1;
            position: relative;
        }}

        /* 侧边栏导航 */
        .sidebar {{
            width: 280px;
            background: white;
            border-right: 1px solid #e0e0e0;
            overflow-y: auto;
            box-shadow: 2px 0 10px rgba(0, 0, 0, 0.05);
            position: sticky;
            top: 0;
            height: 100vh;
            flex-shrink: 0;
        }}

        .sidebar-header {{
            background: linear-gradient(to right, #4b6cb7, #182848);
            color: white;
            padding: 20px;
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        .sidebar-header h1 {{
            font-size: 1.5rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}

        .file-info {{
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 12px;
            border-radius: 6px;
            margin-top: 10px;
            font-size: 0.9rem;
        }}

        .sheet-list {{
            padding: 20px;
        }}

        .sheet-list h3 {{
            color: #2c3e50;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.1rem;
        }}

        .sheet-list ul {{
            list-style: none;
        }}

        .sheet-list li {{
            margin-bottom: 8px;
        }}

        .sheet-list a {{
            display: block;
            padding: 12px 15px;
            background: #f8f9fa;
            border-radius: 8px;
            color: #2c3e50;
            text-decoration: none;
            border-left: 3px solid transparent;
            transition: all 0.3s ease;
        }}

        .sheet-list a:hover {{
            background: #e9ecef;
            transform: translateX(5px);
        }}

        .sheet-list a.active {{
            background: #e3f2fd;
            border-left: 3px solid transparent;
            color: #1976d2;
            font-weight: 500;
        }}

        /* 主内容区 */
        .main-content {{
            flex: 1;
            padding: 30px;
            overflow-y: auto;
            max-height: 100vh;
            position: relative;
        }}

        .main-header {{
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
            /* 移除 sticky，改为静态定位 */
            position: relative;
            z-index: 10;
            border: 1px solid #e0e0e0;
        }}

        .main-header h2 {{
            color: #2c3e50;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.6rem;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }}

        .current-sheet-info {{
            display: flex;
            gap: 20px;
            color: #666;
            font-size: 0.95rem;
            background: #f8f9fa;
            padding: 12px 15px;
            border-radius: 8px;
            flex-wrap: wrap;
            border: 1px solid #e0e0e0;
        }}

        .current-sheet-info span {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 0;
        }}

        /* 工作表内容 */
        .sheet-content {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 15px rgba(0, 0, 0, 0.05);
            margin-bottom: 30px;
            border: 1px solid #e0e0e0;
            /* 确保工作表内容不会被遮挡 */
            position: relative;
            z-index: 5;
        }}

        .sheet-header {{
            margin-bottom: 25px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }}

        .sheet-header h3 {{
            color: #2c3e50;
            font-size: 1.8rem;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .sheet-meta {{
            display: flex;
            gap: 25px;
            color: #666;
            font-size: 0.95rem;
            background: #f8f9fa;
            padding: 12px 15px;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            flex-wrap: wrap;
        }}

        .sheet-meta span {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .table-container {{
            overflow-x: auto;
            margin-top: 25px;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            padding: 5px;
            background: #f9f9f9;
            position: relative;
        }}

        /* 表格样式增强 */
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.08);
            background: white;
        }}

        th {{
            background: linear-gradient(to bottom, #4b6cb7, #3a5a9e);
            color: white;
            font-weight: 600;
            padding: 14px 16px;
            text-align: left;
            border: 1px solid #3a5a9e;
            position: sticky;
            top: 0;
            z-index: 20; /* 表头在表格内部固定 */
        }}

        td {{
            padding: 12px 16px;
            border: 1px solid #e0e0e0;
            background: white;
            line-height: 1.5;
        }}

        tr:nth-child(even) td {{
            background-color: #f8f9fa;
        }}

        tr:hover td {{
            background-color: #e3f2fd;
        }}

        /* 控制按钮 */
        .controls {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: flex;
            gap: 10px;
            z-index: 1000;
        }}

        .control-btn {{
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #4b6cb7;
            color: white;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            box-shadow: 0 4px 15px rgba(75, 108, 183, 0.3);
            transition: all 0.3s ease;
        }}

        .control-btn:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(75, 108, 183, 0.4);
            background: #3a5a9e;
        }}

        /* 响应式设计 */
        @media (max-width: 1024px) {{
            .container {{
                flex-direction: column;
            }}

            .sidebar {{
                width: 100%;
                height: auto;
                max-height: 300px;
                position: relative;
                border-right: none;
                border-bottom: 1px solid #e0e0e0;
            }}

            .main-content {{
                max-height: none;
                padding: 20px;
            }}

            .controls {{
                bottom: 20px;
                right: 20px;
            }}

            .main-header {{
                position: relative; /* 在移动端也保持相对定位 */
            }}
        }}

        @media (max-width: 768px) {{
            .main-content {{
                padding: 15px;
            }}

            .sheet-content {{
                padding: 20px;
            }}

            .current-sheet-info {{
                flex-direction: column;
                gap: 10px;
            }}

            .sheet-meta {{
                flex-direction: column;
                gap: 10px;
            }}

            .control-btn {{
                width: 45px;
                height: 45px;
                font-size: 1rem;
            }}

            .main-header h2 {{
                font-size: 1.4rem;
            }}

            .sheet-header h3 {{
                font-size: 1.5rem;
            }}
        }}

        /* 动画效果 */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .sheet-content {{
            animation: fadeIn 0.5s ease;
        }}

        /* 错误消息 */
        .error-message {{
            background: #ffeaea;
            color: #d32f2f;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #d32f2f;
            margin: 20px 0;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #666;
            background: #f5f5f5;
            border-radius: 8px;
            border: 1px solid #ddd;
        }}

        /* 滚动条样式 */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb {{
            background: #c1c1c1;
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: #a8a8a8;
        }}

        /* 打印样式 */
        @media print {{
            .sidebar, .controls {{
                display: none;
            }}

            .main-content {{
                padding: 0;
            }}

            .main-header {{
                position: static;
                box-shadow: none;
                border: none;
            }}

            .sheet-content {{
                page-break-inside: avoid;
                box-shadow: none;
                border: 1px solid #ddd;
                margin: 20px 0;
            }}

            .table-container {{
                border: none;
                padding: 0;
                background: none;
            }}

            .current-sheet-info, .sheet-meta {{
                background: none;
                border: none;
            }}

            th {{
                position: static; /* 打印时移除固定定位 */
            }}
        }}

        /* 增加额外的顶部间距，确保切换时不会被遮挡 */
        .sheet-content:first-child {{
            margin-top: 10px;
        }}
    </style>

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="container">
        <!-- 侧边栏导航 -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h1><i class="fas fa-file-excel"></i> Excel 预览</h1>
                <div class="file-info">
                    <i class="fas fa-file"></i> {Path(input_excel).name}
                </div>
            </div>

            <div class="sheet-list">
                <h3><i class="fas fa-th-list"></i> 工作表导航</h3>
                <ul>
                    {nav_menu}
                </ul>

                <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e0e0e0;">
                    <h4 style="color: #2c3e50; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                        <i class="fas fa-info-circle"></i> 文件信息
                    </h4>
                    <p style="margin-top: 10px; font-size: 0.9rem; color: #666; line-height: 1.6;">
                        <span style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                            <i class="fas fa-calendar-alt"></i> 生成时间: {current_time}
                        </span>
                        <span style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                            <i class="fas fa-layer-group"></i> 工作表数: {len(sheet_names)}
                        </span>
                        <span style="display: flex; align-items: center; gap: 8px;">
                            <i class="fas fa-hdd"></i> 文件: {Path(input_excel).name}
                        </span>
                    </p>
                </div>
            </div>
        </div>

        <!-- 主内容区 -->
        <div class="main-content">
            <div class="main-header">
                <h2><i class="fas fa-table"></i> Excel 工作表预览</h2>
                <div class="current-sheet-info">
                    <span><i class="fas fa-file-excel"></i> 文件: {Path(input_excel).name}</span>
                    <span><i class="fas fa-calendar-alt"></i> 生成时间: {current_time}</span>
                    <span><i class="fas fa-hashtag"></i> 总工作表数: {len(sheet_names)}</span>
                </div>
            </div>

            {sheet_sections}
        </div>
    </div>

    <!-- 控制按钮 -->
    <div class="controls">
        <button class="control-btn" onclick="scrollToTop()" title="回到顶部">
            <i class="fas fa-arrow-up"></i>
        </button>
        <button class="control-btn" onclick="printPage()" title="打印">
            <i class="fas fa-print"></i>
        </button>
        <button class="control-btn" onclick="toggleSidebar()" title="切换侧边栏">
            <i class="fas fa-bars"></i>
        </button>
    </div>

    <script>
        let currentSheetIndex = 0;
        const totalSheets = {len(sheet_names)};

        // 显示指定工作表
        function showSheet(index) {{
            // 隐藏所有工作表
            document.querySelectorAll('.sheet-content').forEach(sheet => {{
                sheet.style.display = 'none';
            }});

            // 显示选中的工作表
            const currentSheet = document.getElementById(`sheet_${{index + 1}}`);
            currentSheet.style.display = 'block';

            // 更新导航菜单激活状态
            document.querySelectorAll('.sheet-list a').forEach((link, i) => {{
                if (i === index) {{
                    link.classList.add('active');
                }} else {{
                    link.classList.remove('active');
                }}
            }});

            currentSheetIndex = index;

            // 滚动到当前工作表顶部，但给标题留出空间
            const headerHeight = document.querySelector('.main-header').offsetHeight;
            const scrollPosition = currentSheet.offsetTop - headerHeight - 20;

            window.scrollTo({{ 
                top: scrollPosition > 0 ? scrollPosition : 0, 
                behavior: 'smooth' 
            }});
        }}

        // 显示上一个工作表
        function prevSheet() {{
            if (currentSheetIndex > 0) {{
                showSheet(currentSheetIndex - 1);
            }}
        }}

        // 显示下一个工作表
        function nextSheet() {{
            if (currentSheetIndex < totalSheets - 1) {{
                showSheet(currentSheetIndex + 1);
            }}
        }}

        // 回到顶部
        function scrollToTop() {{
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        // 打印页面
        function printPage() {{
            window.print();
        }}

        // 切换侧边栏
        function toggleSidebar() {{
            const sidebar = document.querySelector('.sidebar');
            if (window.innerWidth <= 1024) {{
                // 在移动端，侧边栏默认隐藏
                if (sidebar.style.display === 'none' || !sidebar.style.display) {{
                    sidebar.style.display = 'block';
                }} else {{
                    sidebar.style.display = 'none';
                }}
            }} else {{
                // 在桌面端，调整宽度
                if (sidebar.style.width === '0px' || sidebar.style.width === '') {{
                    sidebar.style.width = '280px';
                    document.querySelector('.main-content').style.marginLeft = '0';
                }} else {{
                    sidebar.style.width = '0px';
                    document.querySelector('.main-content').style.marginLeft = '-280px';
                }}
            }}
        }}

        // 键盘快捷键
        document.addEventListener('keydown', function(e) {{
            switch(e.key) {{
                case 'ArrowLeft':
                    prevSheet();
                    break;
                case 'ArrowRight':
                    nextSheet();
                    break;
                case 'Home':
                    showSheet(0);
                    break;
                case 'End':
                    showSheet(totalSheets - 1);
                    break;
                case 'p':
                case 'P':
                    if (e.ctrlKey) {{
                        e.preventDefault();
                        printPage();
                    }}
                    break;
                case 'Escape':
                    toggleSidebar();
                    break;
            }}
        }});

        // 初始化显示第一个工作表
        document.addEventListener('DOMContentLoaded', function() {{
            showSheet(0);

            // 表格悬停效果
            document.querySelectorAll('table tr').forEach(row => {{
                row.addEventListener('mouseenter', function() {{
                    this.style.backgroundColor = '#e3f2fd';
                }});

                row.addEventListener('mouseleave', function() {{
                    if (this.rowIndex % 2 === 0) {{
                        this.style.backgroundColor = '#f8f9fa';
                    }} else {{
                        this.style.backgroundColor = 'white';
                    }}
                }});
            }});

            // 响应式调整
            function adjustLayout() {{
                const sidebar = document.querySelector('.sidebar');
                const mainContent = document.querySelector('.main-content');

                if (window.innerWidth <= 1024) {{
                    // 移动端：侧边栏默认显示，但不固定位置
                    sidebar.style.position = 'relative';
                    sidebar.style.height = 'auto';
                    mainContent.style.marginLeft = '0';
                }} else {{
                    // 桌面端：恢复固定侧边栏
                    sidebar.style.position = 'sticky';
                    sidebar.style.height = '100vh';
                }}
            }}

            window.addEventListener('resize', adjustLayout);
            adjustLayout(); // 初始化调用

            // 监听锚点点击
            document.querySelectorAll('.sheet-list a').forEach((link, index) => {{
                link.addEventListener('click', function(e) {{
                    e.preventDefault();
                    showSheet(index);
                }});
            }});
        }});
    </script>
</body>
</html>'''

    return html_template



if __name__ == "__main__":
    my_excel_file = "/home/rd/Downloads/2.xlsx"  # 替换为你的 Excel 文件路径
    md_file_path = convert_xlsx_to_md(my_excel_file, True)
    if md_file_path:
        logger.info(f"Markdown文件已保存到: {md_file_path}")

        # 可选：读取并显示部分内容
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"文件前500字符预览:\n{content[:500]}...")
    else:
        logger.info("转换失败")

    html_file_path = convert_xlsx_to_html(my_excel_file, output_abs_path=True)
    logger.info(f"html 文件已保存到: {html_file_path}")
    result = convert_xlsx_all_sheet_to_html_with_navi(my_excel_file)
    logger.info(f"html navi file已保存到: {result}")