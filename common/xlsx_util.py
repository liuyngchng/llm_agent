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
    output_dir = os.path.join(OUTPUT_DIR, Path(input_excel).stem)
    os.makedirs(output_dir, exist_ok=True)
    # 转换每个sheet到单独的HTML
    sheet_files = {}
    for sheet_name in sheet_names:
        safe_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        if not safe_name:
            safe_name = f"sheet_{sheet_names.index(sheet_name) + 1}"

        html_file = f"{safe_name}.html"
        html_path = os.path.join(output_dir, html_file)

        try:
            xlsx2html(input_excel, html_path, sheet=sheet_name)
            sheet_files[sheet_name] = {
                'file': html_file,
                'path': html_path,
                'display_name': sheet_name
            }
            logger.info(f"✅ 转换: {sheet_name} -> {html_file}")
        except Exception as e:
            logger.error(f"❌ 转换失败 {sheet_name}: {e}")

    # 创建导航页面
    nav_html = _create_navigation_page(input_excel, sheet_files, output_dir)
    return nav_html


def _create_navigation_page(input_excel, sheet_files, output_dir):
    """
    创建导航页面
    """
    base_name = Path(input_excel).stem
    nav_file = os.path.join(output_dir, "index.html")

    nav_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{base_name} - Excel 预览</title>
    <style>
        :root {{
            --primary-color: #4CAF50;
            --secondary-color: #2196F3;
            --background-color: #f5f5f5;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(to right, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 30px 40px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .main-content {{ padding: 40px; }}
        .sheet-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}
        .sheet-card {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            border: 1px solid #e0e0e0;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        .sheet-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            border-color: var(--primary-color);
        }}
        .sheet-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 5px;
            height: 100%;
            background: var(--primary-color);
        }}
        .sheet-number {{
            background: var(--primary-color);
            color: white;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-bottom: 15px;
        }}
        .sheet-title {{
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 10px;
            color: #333;
        }}
        .sheet-actions {{
            margin-top: 20px;
            display: flex;
            gap: 10px;
        }}
        .btn {{
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        .btn-primary {{
            background: var(--primary-color);
            color: white;
        }}
        .btn-primary:hover {{
            background: #3d8b40;
            transform: scale(1.05);
        }}
        .btn-secondary {{
            background: #f0f0f0;
            color: #333;
        }}
        .btn-secondary:hover {{
            background: #e0e0e0;
        }}
        .stats {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .stats-item {{
            text-align: center;
        }}
        .stats-value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--primary-color);
        }}
        .stats-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #eee;
        }}
        @media (max-width: 768px) {{
            .sheet-grid {{ grid-template-columns: 1fr; }}
            .stats {{ flex-direction: column; gap: 15px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {Path(input_excel).name}</h1>
            <p>Excel文件预览 - {len(sheet_files)} 个工作表</p>
        </div>

        <div class="main-content">
            <div class="stats">
                <div class="stats-item">
                    <div class="stats-value">{len(sheet_files)}</div>
                    <div class="stats-label">工作表总数</div>
                </div>
                <div class="stats-item">
                    <div class="stats-value">{sum(1 for s in sheet_files.values() if 'error' not in s)}</div>
                    <div class="stats-label">成功转换</div>
                </div>
                <div class="stats-item">
                    <div class="stats-value">{sum(1 for s in sheet_files.values() if 'error' in s)}</div>
                    <div class="stats-label">转换失败</div>
                </div>
            </div>

            <h2 style="margin-bottom: 20px;">📋 工作表列表</h2>
            <div class="sheet-grid">
'''

    for i, (sheet_name, info) in enumerate(sheet_files.items(), 1):
        nav_html += f'''
                <div class="sheet-card">
                    <div class="sheet-number">{i}</div>
                    <div class="sheet-title">{sheet_name}</div>
                    <div class="sheet-actions">
                        <a href="{info['file']}" class="btn btn-primary" target="_blank">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                                <line x1="16" y1="13" x2="8" y2="13"></line>
                                <line x1="16" y1="17" x2="8" y2="17"></line>
                                <polyline points="10 9 9 9 8 9"></polyline>
                            </svg>
                            查看表格
                        </a>
                    </div>
                </div>
'''

    nav_html += f'''
            </div>
        </div>

        <div class="footer">
            <p>时间: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>powered by paper_review</p>
        </div>
    </div>

    <script>
        // 平滑滚动
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({{
                    behavior: 'smooth'
                }});
            }});
        }});
    </script>
</body>
</html>'''

    with open(nav_file, 'w', encoding='utf-8') as f:
        f.write(nav_html)

    logger.info(f"✅ 导航页面已创建: {nav_file}")
    return nav_file


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