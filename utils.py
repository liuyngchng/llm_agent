#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re


def extract_json(dt: str) -> str:
    # 只取从第一个 { 开始， 到最后哦一个 } 结束的部分
    return re.sub(r'^.*?(\{.*\}).*$', r'\1', dt, flags=re.DOTALL)

def extract_sql(raw_sql: str) -> str:
    # 精准匹配 ```sql...``` 代码块
    pattern = r"```sql(.*?)```"
    match = re.search(pattern, raw_sql, re.DOTALL)  # DOTALL模式匹配换行

    if match:
        clean_sql = match.group(1)
        # 清理首尾空白/换行（保留分号）
        return clean_sql.strip(" \n\t")
    else:
        raw_sql = rmv_think_block(raw_sql)
    return raw_sql

def rmv_think_block(dt:str):
    dt = re.sub(r'<think>.*?</think>', '', dt, flags=re.DOTALL)
    return dt