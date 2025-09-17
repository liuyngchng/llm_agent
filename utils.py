#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import re
import sys

import cfg_util
from my_enums import AppType


def extract_json(dt: str) -> str:
    # start from first '{', end with last '}'
    return re.sub(r'^.*?(\{.*\}).*$', r'\1', dt, flags=re.DOTALL)

def extract_md_content(raw_md: str, language: str) -> str:
    # extract  ```sql...``` code block
    pattern = rf"```{language}(.*?)```"
    match = re.search(pattern, raw_md, re.DOTALL)  # DOTALL模式匹配换行

    if match:
        txt = match.group(1)
        return txt.strip(" \n\t")
    else:
        raw_md = rmv_think_block(raw_md)
    return raw_md

def rmv_think_block(dt:str):
    dt = re.sub(r'<think>.*?</think>', '', dt, flags=re.DOTALL)
    return dt

def convert_list_to_md_table(my_list: list):

    headers = list(my_list[0].keys()) if my_list else []
    markdown_table = f"| {' | '.join(headers)} |\n| {' | '.join(['---'] * len(headers))} |\n"
    for item in my_list:
        row = " | ".join(str(item[h]).replace('\n', '<br>') for h in headers)
        markdown_table += f"| {row} |\n"
    return markdown_table

def convert_list_to_html_table(my_list: list):
    headers = list(my_list[0].keys()) if my_list else []
    html = ("<table>\n<thead>\n<tr>" + "".join(f"<th>{h}</th>" for h in headers)
            + "</tr>\n</thead>\n<tbody>")
    for item in my_list:
        row = "".join(f"<td>{str(item[h]).replace(chr(10), '<br>')}</td>" for h in headers)
        html += f"\n<tr>{row}</tr>"
    return html + "\n</tbody>\n</table>"

def get_console_arg1() -> int:
    # 检查命令行参数
    default_port = 19000
    max_port = 65535
    if len(sys.argv) <= 1:
        print(f"no_console_arg, using default {default_port}")
        return default_port
    try:
        console_port = int(sys.argv[1])  # 转换输入的端口参数
        if console_port < 1024 or console_port > 65535:
            print(f"port_out_of_range[1024, 65535]: {sys.argv[1]}, using max_port {max_port}")
            console_port = max_port
        return console_port
    except ValueError:
        print(f"invalid_port: {sys.argv[1]}, using default {default_port}")
    return default_port


def adjust_html_table_columns(html_content: str) -> str:
    """
    保证输出的html table 的内容，第一列和第二列为地理区域（省、市、区县）和组织机构(公司、团体)名称（如果存在）
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    if not table:
        return html_content

    thead = table.find('thead')
    if not thead:
        return html_content

    header_row = thead.find('tr')
    if not header_row:
        return html_content

    headers = [th.text.strip() for th in header_row.find_all('th')]
    # 地理区域(省、市、区县)名称
    area_name_str = cfg_util.get_const('area_name_list', AppType.TXT2SQL.name.lower())
    # 组织机构(公司、团体)名称
    org_str = cfg_util.get_const('organization_name_list', AppType.TXT2SQL.name.lower())
    if not area_name_str or not org_str:
        raise RuntimeError("no area_name_list or organization_name_list in cfg file")
    try:
        area_name_list = json.loads(area_name_str)
        organization_list = json.loads(org_str)
    except Exception as e:
        raise RuntimeError(f"invalid json config for area_name_list or organization_name_list in cfg file {e}")
    # 找出所有存在的地理表头和组织机构表头
    area_indices = [i for i, h in enumerate(headers) if h in area_name_list]
    org_indices = [i for i, h in enumerate(headers) if h in organization_list]

    # 如果没有这两个列，直接返回原内容
    if not area_indices and not org_indices:
        return html_content

    # 构建新的表头顺序：先地理区域，再组织机构，最后其他列
    new_headers = []
    # 添加地理区域列
    for i in area_indices:
        new_headers.append(headers[i])
    # 添加组织机构列
    for i in org_indices:
        new_headers.append(headers[i])
    # 添加其他列
    for i, header in enumerate(headers):
        if i not in area_indices and i not in org_indices:
            new_headers.append(header)

    # 更新表头
    header_row.clear()
    for header in new_headers:
        th = soup.new_tag('th')
        th.string = header
        header_row.append(th)

    # 调整表格数据行
    tbody = table.find('tbody')
    if not tbody:
        return str(soup)

    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) != len(headers):
            continue

        # 收集需要优先显示的单元格
        priority_cells = []
        for i in area_indices:
            priority_cells.append(tds[i])
        for i in org_indices:
            priority_cells.append(tds[i])

        # 收集其他单元格
        other_cells = []
        for i, td in enumerate(tds):
            if i not in area_indices and i not in org_indices:
                other_cells.append(td)

        # 更新行内容
        tr.clear()
        for cell in priority_cells + other_cells:
            tr.append(cell)
    return str(soup)




def get_table_name_from_sql(sql:str) -> str | None:
    """
    从SQL语句中获取表名
    :param sql: SQL语句
    :return: 表名
    """
    sql = re.sub(r'\s+', ' ', sql.strip())
    patterns = [
        r'(?:FROM|JOIN)\s+(\w+)',
        r'UPDATE\s+(\w+)',
        r'INSERT\s+INTO\s+(\w+)',
        r'DELETE\s+FROM\s+(\w+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
    return None