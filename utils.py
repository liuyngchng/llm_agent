#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import re
import sys
from bs4 import BeautifulSoup


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
    保证输出的html table 的内容，第一列和第二列为省和公司名称
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    thead = table.find('thead')
    header_row = thead.find('tr')
    headers = [th.text for th in header_row.find_all('th')]
    province_idx = headers.index('客户(用户)所属省')
    company_idx = headers.index('燃气公司名称')

    # 创建新的表头顺序
    new_headers = [headers[province_idx], headers[company_idx]]
    for i, header in enumerate(headers):
        if i not in [province_idx, company_idx]:
            new_headers.append(header)
    # 清空原表头行并添加新表头
    header_row.clear()
    for header in new_headers:
        th = soup.new_tag('th')
        th.string = header
        header_row.append(th)
    # 调整表格数据
    tbody = table.find('tbody')
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        province = tds[province_idx]
        company = tds[company_idx]
        # 创建新的单元格顺序
        new_tds = [province, company]
        for i, td in enumerate(tds):
            if i not in [province_idx, company_idx]:
                new_tds.append(td)
        # 清空原行并添加新顺序
        tr.clear()
        for td in new_tds:
            tr.append(td)
    return str(soup)