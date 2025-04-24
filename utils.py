#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re


def extract_json(dt: str) -> str:
    # 只取从第一个 { 开始， 到最后哦一个 } 结束的部分
    return re.sub(r'^.*?(\{.*\}).*$', r'\1', dt, flags=re.DOTALL)

def extract_md_content(raw_md: str, language: str) -> str:
    # 精准匹配 ```sql...``` 代码块
    pattern = rf"```{language}(.*?)```"
    match = re.search(pattern, raw_md, re.DOTALL)  # DOTALL模式匹配换行

    if match:
        txt = match.group(1)
        # 清理首尾空白/换行（保留分号）
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
        row = ' | '.join(str(item[h]).replace('\n', '<br>') for h in headers)
        markdown_table += f"| {row} |\n"
    return markdown_table

def convert_list_to_html_table(my_list: list):
    headers = list(my_list[0].keys()) if my_list else []
    html = ('<table>\n<thead>\n<tr>' + ''.join(f'<th>{h}</th>' for h in headers)
            + '</tr>\n</thead>\n<tbody>')
    for item in my_list:
        row = ''.join(f'<td>{str(item[h]).replace("\n", "<br>")}</td>' for h in headers)
        html += f'\n<tr>{row}</tr>'
    return html + '\n</tbody>\n</table>'