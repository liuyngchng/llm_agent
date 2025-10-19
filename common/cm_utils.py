#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
通用公共类
"""
import json
import re
import sys

from common import cfg_util
from common.my_enums import AppType


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


def replace_spaces(text):
    """
    将文本中的多个连续空格或制表符替换为一个空格
    """
    return re.sub(r'[ \t]+', ' ', text)

def check_contain_spaces_in_every_line(text):
    """
    检查一段文本中是否每行都有一个或多个空格或制表符
    """
    lines = text.splitlines()
    for line in lines:
        if line.strip():  # 忽略空行
            parts = re.split(r'[ \t]+', line.strip())
            if len(parts) < 2:
                return False
    return True

def validate_user_prompt(refine_q_msg, sql_gen_msg) -> dict:
    """
    校验用户数据的提示词，是否含有指定的变量名称，返回是否成功，以及存在错误的信息
    :param refine_q_msg 优化提问的提示词
    :param sql_gen_msg 生成 SQL 语句的提示词
    return a dict
    """
    result = {
        "is_valid": True,
        "refine_q_msg_err": "",
        "sql_gen_msg_err": "",
    }

    # 校验 refine_q_msg 必须包含的变量
    required_refine_vars = ["{data_source_info}", "{user_short_q_desc}"]
    err = ''
    for var in required_refine_vars:
        if var not in refine_q_msg:
            result["is_valid"] = False
            err += f" {var},"
    if err:
        result["refine_q_msg_err"] = err
    # 校验 sql_gen_msg 必须包含的变量
    required_sql_vars = ["{sql_dialect}", "{schema}", "{chat_history}", "{max_record_per_page}"]
    err = ''
    for var in required_sql_vars:
        if var not in sql_gen_msg:
            result["is_valid"] = False
            err += f" {var},"
    if err:
        result["sql_gen_msg_err"] = err
    return result


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

def post_with_retry(uri: str, headers: dict, data: dict, proxies: str | None, max_retries: int = 3) -> dict:
    """
    带重试机制的LLM调用
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"第 {attempt + 1} 次 post {uri}, proxies: {proxies}, data: {data}")
            response = requests.post(uri, headers=headers, json=data, verify=False, proxies=proxies, timeout=30)
            logger.info(f"llm_response_status {response.status_code}")

            if response.status_code == 200:
                logger.debug(f"post_response {json.dumps(response.json())}")
                return response.json()
            else:
                logger.warning(f"request API 返回非200状态码: {response.status_code}, {response.json()}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避

        except requests.exceptions.Timeout:
            logger.warning(f"request_API_timeout，retry {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
        except Exception as e:
            logger.warning(f"request_API_fail: {str(e)}，retry {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避

    # 所有重试都失败
    raise RuntimeError(f"LLM API 调用失败，已重试 {max_retries} 次")

def get_with_retry(uri: str, headers: dict, params: dict, proxies: str | None, max_retries: int = 3) -> dict:
    """
    带重试机制的GET请求
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"第 {attempt + 1} 次尝试调用GET API {uri}, proxies: {proxies}, params: {params}")
            response = requests.get(uri, headers=headers, params=params, verify=False, proxies=proxies, timeout=30)
            logger.info(f"get_response_status {response.status_code}")

            if response.status_code == 200:
                logger.debug(f"get_response {json.dumps(response.json(), ensure_ascii=False)}")
                return response.json()
            else:
                logger.warning(f"GET API 返回非200状态码: {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        except requests.exceptions.Timeout:
            logger.warning(f"GET API 调用超时，尝试 {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"GET API 调用失败: {str(e)}，尝试 {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"GET API 调用失败，已重试 {max_retries} 次")

def build_curl_cmd(api, data, headers, proxies: dict | None):
    header_str = ""
    for k, v in headers.items():
        header_str += f' -H "{k}: {v}" '

    if proxies:
        curl_proxy = f"--proxy {proxies.get('http', proxies.get('https', None))}"
    else:
        curl_proxy = "--noproxy '*'"
    if 'https' in api:
        https_option = '-k --tlsv1'
    else:
        https_option = ''
    curl_log = f"curl -s {curl_proxy} -w'\\n' {https_option} -X POST {header_str} -d '{json.dumps(data, ensure_ascii=False)}' '{api}' | jq"
    return curl_log