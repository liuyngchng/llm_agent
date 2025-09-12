#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
对第三方系统开放的接口
"""
import json
import logging.config

from flask import Flask, request, g

import agt_util
from doris import Doris
from my_enums import AppType
from sql_agent import SqlAgent
from sys_init import init_yml_cfg
from utils import get_console_arg1


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

def get_db_cfg():
    if 'db_cfg' not in g:
        g.db_cfg = init_yml_cfg()['db']  # 首次请求时加载并缓存
        logger.info(f"g_db_cfg_inited, {g.db_cfg}")
    return g.db_cfg

@app.teardown_appcontext
def teardown_db_cfg(exception):
    g.pop('db_cfg', None)

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    welcome = {"info":"welcome to open api", "status": 200}
    return json.dumps(welcome, ensure_ascii=False)

@app.route('/app/list')
def list_available_app():
    logger.info(f"trigger_list_available_app")
    return json.dumps(AppType.get_app_list(), ensure_ascii=False)

@app.route('/ds/list')
def list_available_db_source():
    logger.info(f"trigger_list_available_db_source")
    db_cfg = get_db_cfg()
    data_source_list = [
        {"name": db_cfg.get('name', db_cfg.get('data_source')), "desc": db_cfg["desc"], "dialect":db_cfg["type"]}
    ]
    logger.info(f"list_available_db_source_return, {data_source_list}")
    return json.dumps(data_source_list, ensure_ascii=False)

@app.route('/<db_source>/table/list')
def list_available_tables(db_source):
    logger.info(f"trigger list_available_tables")
    db_cfg = get_db_cfg()
    doris = Doris(db_cfg)
    table_list = doris.get_schema_info()
    table_desc_list = []
    for item in table_list:
        table_desc_list.append({"name": item["name"], "desc": item['schema'].split('COMMENT=')[1].replace("'", "")})
    logger.info(f"list_available_tables_return, {table_desc_list}")
    return json.dumps(table_desc_list, ensure_ascii=False)

@app.route('/<db_source>/<table_name>/schema')
def get_table_schema(db_source, table_name):
    logger.info(f"trigger get_table_schema")
    db_cfg = get_db_cfg()
    doris = Doris(db_cfg)
    create_table_sql = doris.get_table_schema(db_source, table_name)
    table_schema = {"db_name":db_source, "table_name": table_name, "schema": create_table_sql}
    logger.info(f"get_table_schema_return, {table_schema}")
    return json.dumps(table_schema, ensure_ascii=False)

@app.route('/exec/task', methods=['POST'])
def execute_sql_query():
    sql = request.json.get('sql')
    logger.info(f"trigger_execute_sql_query, {sql}")
    db_cfg = get_db_cfg()
    doris = Doris(db_cfg)
    result = doris.exec_sql(sql)
    logger.info(f"execute_sql_query_return, {result}")
    return json.dumps(result, ensure_ascii=False)

@app.route('/txt/to/sql', methods=['POST', 'GET'])
def get_sql_from_txt_and_schema():
    if request.method == 'GET':
        return json.dumps({"status": 502, "sql": "GET method not support, you should post with json data with key schema, dialect, sql"})
    json_dt = request.json
    if not json_dt:
        return json.dumps({"status": 400, "sql": "json data is empty"})
    logger.info(f"trigger_txt_to_sql, {json_dt}")
    schema = json_dt.get('schema')
    txt = json_dt.get('txt')
    dialect = json_dt.get('dialect')
    if not schema or not txt or not dialect:
        return json.dumps({"status": 401, "sql": "key schema, txt, dialect is required in your json data"})
    my_cfg = init_yml_cfg()
    sql = agt_util.txt2sql(schema, txt, dialect, my_cfg)
    logger.info(f"txt_to_sql_return, {sql}")
    dt = {"status":200, "sql":sql}
    return json.dumps(dt, ensure_ascii=False)

if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)