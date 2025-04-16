#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import sqlite3
import json
import pandas as pd
import logging.config


from urllib.parse import urlparse, unquote, urlencode
from sys_init import init_yml_cfg

"""
Oracle 数据库需要额外安装其客户端动态库
(1) 安装 oracle的 instant client,
    详见  https://www.oracle.com/database/technologies/instant-client/downloads.html
    
    #ubuntu
    1) libaio
    sudo apt-get install libaio1t64
    sudo apt-get install libaio-dev
    sudo find /usr -name libaio*
    sudo ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1
    
    2) libclntsh.so
    cd /usr/local/lib
    sudo mkdir oracle
    cd oracle/instantclient-basic-linux.x64-12.1.0.2.0/instantclient_12_1
    sudo cp *.so /usr/local/lib/oracle/
    sudo cp *.so.* /usr/local/lib/oracle/
    cd /usr/local/lib/oracle
    sudo ln -s libclntsh.so.11.1 libclntsh.so
    export LD_LIBRARY_PATH=/usr/local/lib/oracle:$LD_LIBRARY_PATH
(2) install pip package
    pip install pymysql cx_Oracle pycryptodome 
"""

logging.config.fileConfig('logging.conf', encoding="utf-8")
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

def sqlite_insert_tool(db_con, query: str) -> dict:
    # ///TODO 防止sql注入
    try:
        cursor = db_con.cursor()
        cursor.execute(query)
        db_con.commit()
        return {"result":True, "affected_rows": cursor.rowcount}
    except Exception as e:
        db_con.rollback()
        logger.error(f"save_data_err: {e}")
        return {"result":False, "error": "save data failed"}

def output_data(db_con, sql:str, data_format:str) -> str:
    if isinstance(db_con, sqlite3.Connection):
        result = sqlite_query_tool(db_con, sql)
    elif isinstance(db_con, pymysql.Connection):
        result = mysql_query_tool(db_con, sql)
    elif isinstance(db_con, cx_Oracle.Connection):
        result = oracle_query_tool(db_con, sql)
    else:
        logger.error(f"database_type_error, {__file__}")
        raise "database type error"

    data = json.loads(result)
    logger.info(f"data {data} for {db_con}")
    # 生成表格
    df = pd.DataFrame(data['data'], columns=data['columns'])


    if 'html' in data_format:
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
    elif 'markdown' in data_format:
        if df.empty:
            dt = ''
        else:
            dt = df.to_markdown(index=False)  # 控制台打印美观表格
    elif 'json' in data_format:
        dt = df.to_json(force_ascii=False, orient='records')
    else:
        info = f"error data format {data_format}"
        logger.error(info)
        raise info
    logger.info(f"returned dt \n{df.to_markdown(index=False)}")
    return dt


def mysql_output(cfg: dict, sql:str, data_format:str):
    """
    db_uri = mysql+pymysql://user:pswd@host/db
    """
    db_config = cfg.get('db', {})

    if all(key in db_config for key in ['name', 'host', 'user', 'password']):
        logger.info("connect db with name, host, user, password")
        my_conn = pymysql.connect(
            host=db_config['host'],
            port = db_config.get("port", 3306),
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['name'],
            charset='utf8mb4'
        )
    else:
        logger.info("connect db with db_uri")
        parsed_uri = urlparse(db_config['uri'])
        logger.info(f"host[{parsed_uri.hostname}], user[{parsed_uri.username}], "
                    f"password[{parsed_uri.password}], database[{parsed_uri.path[1:]}]")
        my_conn = pymysql.connect(
            host=unquote(parsed_uri.hostname),
            port= parsed_uri.port or 3306,
            user=unquote(parsed_uri.username),
            password=unquote(parsed_uri.password),
            database=parsed_uri.path[1:],
            charset='utf8mb4'
        )
    logger.info(f"output_data({my_conn}, \n{sql}\n, {data_format})")
    dt = output_data(my_conn, sql, data_format)
    my_conn.close()
    return dt

#################### for support oracle DB #########################
import cx_Oracle
def oracle_query_tool(db_con, query: str) -> str:
    try:
        cursor = db_con.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
    except Exception as e:
        logger.exception("oracle_query_tool_err")
        raise e

def oracle_output(cfg: dict, sql: str, data_format: str):
    """
    cfg['db']['uri'] = oracle+cx_oracle://user:password@host:port/service_name
    连接上oracle服务之后，可以通过以下方法获取 service_name
    SELECT VALUE FROM V$PARAMETER WHERE NAME = 'service_names';
    """
    db_config = cfg.get('db', {})
    logger.info(f"db_config {db_config}")
    if all(key in db_config for key in ['name', 'host', 'user', 'password']):
        dsn = cx_Oracle.makedsn(
            db_config['host'],
            db_config.get('port', 1521),
            service_name=db_config['name']
        )
        conn = cx_Oracle.connect(
            user=db_config['user'],
            password=db_config['password'],
            dsn=dsn
        )
    else:
        parsed_uri = urlparse(db_config['uri'])
        port = parsed_uri.port or 1521
        dsn = cx_Oracle.makedsn(
            unquote(parsed_uri.hostname),
            port,
            service_name=unquote(parsed_uri.path[1:])
        )
        conn = cx_Oracle.connect(
            user=unquote(parsed_uri.username),
            password=unquote(parsed_uri.password),
            dsn=dsn
        )

    dt = output_data(conn, sql, data_format)
    conn.close()
    return dt

def get_orc_db_info(cfg: dict) -> list:
    dsn = cx_Oracle.makedsn(cfg['db']['host'], cfg['db']['port'], service_name=cfg['db']['name'])
    with cx_Oracle.connect(user=cfg['db']['user'], password=cfg['db']['password'], dsn=dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT table_name FROM user_tables")
            return [row[0] for row in cursor]

#################### for support oracle DB #########################


def sqlite_output(db_uri: str, sql:str, data_format:str):
    """
    cfg["db_uri"] = "sqlite:///test1.db"
    """

    db_file = db_uri.split('/')[-1]
    my_conn = sqlite3.connect(db_file)
    logger.debug(f"connect to db {db_file}")
    my_dt = output_data(my_conn, sql, data_format)
    my_conn.close()
    return my_dt

def get_db_uri(cfg: dict) -> str:
    """
    mysql+pymysql://user:pswd@host/db
    oracle+cx_oracle://user:password@host:port/service_name
    """
    db_config = cfg.get('db', {})
    if all(key in db_config for key in ['type', 'name', 'host', 'user', 'password']):
        db_type_cfg = db_config['type'].lower()
        if 'mysql' in db_type_cfg:
            my_db_uri = (f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
                         f"@{db_config['host']}:{db_config.get('port', 3306)}/{db_config['name']}")
        elif 'oracle' in db_type_cfg:
            my_db_uri = (f"oracle+cx_oracle://{db_config['user']}:{db_config['password']}"
                         f"@{db_config['host']}:{db_config.get('port', 1521)}/?service_name={db_config['name']}")
        else:
            raise "unknown db type in config file"
    elif all(key in db_config for key in ['type', 'name']):
        db_type_cfg = db_config['type'].lower()
        if 'sqlite' in db_type_cfg:
            my_db_uri = f"sqlite:///{db_config['name']}"
        else:
            raise "one of the following key ['type', 'name'] missed in config file"
    else:
        raise "one of the following key ['type', 'name', 'host', 'user', 'password'] missed in config file"
    logger.info(f"db_uri {my_db_uri}")
    return my_db_uri

def test_db():
    # sql = "SELECT * FROM customer_info LIMIT 2"
    # my_sql = "SELECT id, 支付金额 from order_info;"
    my_sql = "SELECT * from stu"
    my_cfg = init_yml_cfg()
    logger.info(f"my_cfg {my_cfg}")
    db_uri = get_db_uri(my_cfg)
    db_uri = db_uri.lower()
    if "sqlite" in db_uri:
        my_dt = sqlite_output(db_uri, my_sql, 'json')
    elif "mysql" in db_uri:
        my_dt = mysql_output(my_cfg, my_sql, 'json')
    elif "oracle" in db_uri:
        my_dt = oracle_output(my_cfg, my_sql, 'json')
    else:
        my_dt = None
        raise "check your config file to config correct [dt_uri]"

    logger.info(f"my_dt\n {my_dt}\n")

def test_url():
    url_params = urlencode({"test":'张三'}, encoding="UTF-8")
    logger.info(f"url_encode test:\n {url_params}\n")
    params = [("name", "张三"), ("age", 20), ("gender", "男")]
    url_params = urlencode(params, encoding="UTF-8")
    logger.info(f"url_encode test:\n {url_params}\n")
    decode_params = unquote(url_params)
    logger.info(f"url_decode test:\n {decode_params}\n")

if __name__ == "__main__":
    test_db()
