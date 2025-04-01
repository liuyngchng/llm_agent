#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import sqlite3
import json
import pandas as pd
import logging.config

from urllib.parse import urlparse, unquote
from sys_init import init_cfg

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)


def mysql_query_tool(db_con, query: str) -> str:
    try:
        with db_con.cursor() as cursor:  # 使用with自动管理游标
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"mysql_query_tool_err: {e}")
        raise e

def sqlite_query_tool(db_con, query: str) -> str:
    try:
        cursor = db_con.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"init_cfg_error: {e}")
        return json.dumps({"error": str(e)})

def output_data(db_con, sql:str, is_html:bool) -> str:
    result =''
    if isinstance(db_con, sqlite3.Connection):
        result = sqlite_query_tool(db_con, sql)
    elif isinstance(db_con, pymysql.Connection):
        result = mysql_query_tool(db_con, sql)
    else:
        print(f"database_type_error, {__file__}")
        raise "database type error"

    data = json.loads(result)
    logger.info(f"data {data}")
    # 生成表格
    df = pd.DataFrame(data['data'], columns=data['columns'])
    if is_html:
        # dt = df.to_html()  #生成网页表格
        dt = df.to_html(
            index=False,
            border=0
        ).replace(
            '<table',
            '<table style="border:1px solid #ddd; border-collapse:collapse; width:100%"'
        ).replace(
            '<th>',
            '<th style="background:#f8f9fa; padding:8px; border-bottom:2px solid #ddd; text-align:left">'
        ).replace(
            '<td>',
            '<td style="padding:6px; border-bottom:1px solid #eee">'
        )
    else:
        dt = df.to_markdown(index=False)  # 控制台打印美观表格
    return dt


def mysql_output(db_uri: str, sql:str, is_html:bool):
    """
    db_uri = mysql+pymysql://user:pswd@host/db
    """
    parsed = urlparse(db_uri)
    logger.info(f"host[{parsed.hostname}], user[{parsed.username}], password[{parsed.password}], database[{parsed.path[1:]}]")
    my_conn = pymysql.connect(
        host=parsed.hostname,
        user=parsed.username,
        password=unquote(parsed.password),
        database=parsed.path[1:],
        charset='utf8mb4'
    )
    logger.info(f"output_data({my_conn}, {sql}, {is_html})")
    my_dt = output_data(my_conn, sql, is_html)
    return my_dt
def sqlite_output(db_uri: str, sql:str, is_html:bool):
    """
    db_uri = f"sqlite:///test1.db"
    """

    db_file = db_uri.split('/')[-1]
    my_conn = sqlite3.connect(db_file)
    logger.debug(f"connect to db {db_file}")
    my_dt = output_data(my_conn, sql, is_html)
    return my_dt

if __name__ == "__main__":
    # sql = "SELECT * FROM customer_info LIMIT 2"
    my_sql = "SELECT id, 支付金额 from order_info "
    my_cfg = init_cfg()
    logger.info(f"my_cfg {my_cfg}")
    if "sqlite" in my_cfg['db_uri']:
        dt = sqlite_output(my_cfg['db_uri'], my_sql, False)
    elif "mysql" in my_cfg['db_uri']:
        dt = mysql_output(my_cfg['db_uri'], my_sql,False)
    else:
        dt = None
        logger.error("check your config file to input right dt_uri")
    logger.info(f"dt\n {dt}\n")