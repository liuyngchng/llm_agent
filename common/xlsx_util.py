#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

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
            return os.path.abspath(html_path)
        else:
            return html_path

    except Exception as e:
        logger.exception(f"❌ 转换失败: {e}")
        return ""


def convert_all_sheets_with_navigation(input_excel) -> str:
    """
    转换所有工作表并创建带导航的页面
    """
    import pandas as pd
    from xlsx2html import xlsx2html
    excel_file = pd.ExcelFile(input_excel)
    sheet_names = excel_file.sheet_names
    import hashlib
    file_md5 = hashlib.md5(Path(input_excel).name.encode('utf-8')).hexdigest()
    output_dir = os.path.join(OUTPUT_DIR, file_md5)
    os.makedirs(output_dir, exist_ok=True)
    # 转换每个sheet到单独的HTML
    sheet_files = {}
    for sheet_name in sheet_names:
        safe_name = f"sheet_{sheet_names.index(sheet_name) + 1}"
        html_file = f"{safe_name}.html"
        html_path = os.path.abspath(os.path.join(output_dir, html_file))

        try:
            xlsx2html(input_excel, html_path, sheet=sheet_name)
            sheet_files[sheet_name] = {
                'file': html_file,
                'path': html_path,
                'display_name': safe_name
            }
            logger.info(f"✅ 转换: {input_excel}[{sheet_name}] -> {html_path}")
        except Exception as e:
            logger.error(f"❌ 转换失败 {input_excel}[{sheet_name}]: {e}")

    # 创建导航页面
    nav_html = _create_navigation_page(input_excel, sheet_files, output_dir)
    return nav_html


def _create_navigation_page(input_excel, sheet_files, output_dir):
    """
    创建导航页面
    """
    import os
    from pathlib import Path

    base_name = Path(input_excel).stem
    nav_file = os.path.join(output_dir, "index.html")

    # 生成当前时间戳
    import datetime
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nav_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{base_name} - Excel 预览</title>
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
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        
        .container {{
            width: auto;
            min-width: 1280px;
            max-width: 1400px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        header {{
            background: linear-gradient(to right, #4b6cb7, #182848);
            color: white;
            padding: 25px 30px;
            text-align: center;
            position: relative;
        }}
        
        h1 {{
            font-size: 2.2rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }}
        
        .header-subtitle {{
            opacity: 0.9;
            font-size: 1.1rem;
            margin-bottom: 5px;
        }}
        
        .file-info {{
            background: rgba(255, 255, 255, 0.1);
            padding: 10px 15px;
            border-radius: 8px;
            margin-top: 15px;
            display: inline-block;
        }}
        
        .file-name {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 500;
        }}
        
        .main-content {{
            padding: 40px;
        }}
        
        h2 {{
            color: #2c3e50;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.8rem;
            border-bottom: 2px solid #4b6cb7;
            padding-bottom: 10px;
        }}
        
        h2 i {{
            background: #4b6cb7;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.2rem;
        }}
        
        .stats-container {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            border: 1px solid #e0e0e0;
            transition: all 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            border-color: #4b6cb7;
        }}
        
        .stat-value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #4b6cb7;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 0.95rem;
            font-weight: 500;
        }}
        
        .sheets-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .sheet-card {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
            border: 1px solid #e0e0e0;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            border-left: 4px solid #4b6cb7;
        }}
        
        .sheet-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            border-color: #4b6cb7;
        }}
        
        .sheet-header {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .sheet-number {{
            background: linear-gradient(to right, #4b6cb7, #3a5a9e);
            color: white;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.1rem;
        }}
        
        .sheet-title {{
            font-size: 1.3em;
            font-weight: 600;
            color: #2c3e50;
            flex: 1;
        }}
        
        .sheet-details {{
            color: #666;
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 20px;
        }}
        
        .sheet-actions {{
            display: flex;
            gap: 10px;
        }}
        
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            text-decoration: none;
        }}
        
        .btn-primary {{
            background: linear-gradient(to right, #4b6cb7, #3a5a9e);
            color: white;
            flex: 1;
        }}
        
        .btn-secondary {{
            background: white;
            color: #4b6cb7;
            border: 1px solid #4b6cb7;
        }}
        
        .btn:hover:not(:disabled) {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(75, 108, 183, 0.3);
        }}
        
        .btn-primary:hover:not(:disabled) {{
            background: linear-gradient(to right, #3a5a9e, #2c487e);
        }}
        
        .btn-secondary:hover {{
            background: #f0f4ff;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #eee;
            margin-top: 30px;
            background: #f8f9fa;
        }}
        
        .footer-info {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 10px;
            font-size: 0.9rem;
        }}
        
        /* 空状态样式 */
        .empty-state {{
            text-align: center;
            padding: 40px;
            color: #666;
        }}
        
        .empty-state i {{
            font-size: 3rem;
            color: #4b6cb7;
            margin-bottom: 20px;
            opacity: 0.5;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .container {{
                min-width: auto;
                width: 100%;
                border-radius: 12px;
            }}
        
            .stats-container {{
                grid-template-columns: 1fr;
                gap: 15px;
            }}
        
            .sheets-grid {{
                grid-template-columns: 1fr;
            }}
        
            .main-content {{
                padding: 25px;
            }}
        
            h1 {{
                font-size: 1.8rem;
            }}
        
            h2 {{
                font-size: 1.5rem;
            }}
        
            .sheet-actions {{
                flex-direction: column;
            }}
        
            .btn {{
                width: 100%;
            }}
        
            .footer-info {{
                flex-direction: column;
                gap: 10px;
            }}
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .sheet-card {{
            animation: fadeIn 0.5s ease;
        }}
    </style>
    
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="container">
        <header>
            <h1><i class="fas fa-file-excel"></i> Excel 文件预览</h1>
            <p class="header-subtitle">工作表导航 - {len(sheet_files)} 个工作表</p>
            <div class="file-info">
                <div class="file-name">
                    <i class="fas fa-file-excel"></i>
                    <span>{Path(input_excel).name}</span>
                </div>
            </div>
        </header>

        <div class="main-content">
            <h2><i class="fas fa-chart-bar"></i> 统计概览</h2>

            <div class="stats-container">
                <div class="stat-card">
                    <div class="stat-value">{len(sheet_files)}</div>
                    <div class="stat-label">工作表总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{sum(1 for s in sheet_files.values() if 'error' not in s)}</div>
                    <div class="stat-label">成功转换</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{sum(1 for s in sheet_files.values() if 'error' in s)}</div>
                    <div class="stat-label">转换失败</div>
                </div>
            </div>

            <h2><i class="fas fa-th-list"></i> 工作表列表</h2>

            {f'<div class="sheets-grid">' + ''.join([
        f'''
                <div class="sheet-card">
                    <div class="sheet-header">
                        <div class="sheet-number">{i}</div>
                        <div class="sheet-title">{sheet_name}</div>
                    </div>
                    <div class="sheet-details">
                        <p><i class="fas fa-file-alt"></i> 工作表索引: {i}</p>
                        <p><i class="fas fa-clock"></i> 转换时间: {current_time}</p>
                    </div>
                    <div class="sheet-actions">
                        <a href="{info['file']}" class="btn btn-primary" target="_blank">
                            <i class="fas fa-external-link-alt"></i> 查看表格
                        </a>
                    </div>
                </div>
                '''
        for i, (sheet_name, info) in enumerate(sheet_files.items(), 1)
    ]) + '</div>' if sheet_files else '''
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <h3>暂无工作表</h3>
                    <p>没有找到可用的工作表数据</p>
                </div>
            '''}

        </div>

        <div class="footer">
            <p><i class="fas fa-cogs"></i> Powered by xlsx_util.py</p>
            <div class="footer-info">
                <span><i class="fas fa-calendar-alt"></i> 生成时间: {current_time}</span>
                <span><i class="fas fa-file-excel"></i> 原始文件: {Path(input_excel).name}</span>
                <span><i class="fas fa-layer-group"></i> 总工作表数: {len(sheet_files)}</span>
            </div>
        </div>
    </div>

    <script>
        // 平滑滚动到顶部
        window.addEventListener('load', function() {{
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }});

        // 卡片悬停效果增强
        document.querySelectorAll('.sheet-card').forEach(card => {{
            card.addEventListener('mouseenter', function() {{
                this.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.15)';
            }});

            card.addEventListener('mouseleave', function() {{
                this.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.08)';
            }});
        }});

        // 点击统计卡片动画
        document.querySelectorAll('.stat-card').forEach(card => {{
            card.addEventListener('click', function() {{
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {{
                    this.style.transform = 'translateY(-3px)';
                }}, 150);
            }});
        }});

        // 添加打印功能
        document.addEventListener('keydown', function(e) {{
            if ((e.ctrlKey || e.metaKey) && e.key === 'p') {{
                e.preventDefault();
                alert('建议使用浏览器的打印功能，可以获得最佳打印效果。');
            }}
        }});
    </script>
</body>
</html>'''

    with open(nav_file, 'w', encoding='utf-8') as f:
        f.write(nav_html)

    abs_nav_file = os.path.abspath(nav_file)
    logger.info(f"导航页面已创建: {abs_nav_file}")
    return abs_nav_file


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
    result = convert_all_sheets_with_navigation(my_excel_file)
    logger.info(f"html navi file已保存到: {result}")