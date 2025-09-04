#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对第三方系统开放的接口
"""
import json
import logging.config

from flask import Flask, request

from doris import Doris
from my_enums import AppType
from sys_init import init_yml_cfg
from utils import get_console_arg1


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
db_cfg = init_yml_cfg()['db']

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    welcome = {"info":"welcome to open api", "status": 200}
    return json.dumps(welcome, ensure_ascii=False)

@app.route('/app/list')
def list_available_app():
    logger.info(f"trigger_list_available_app")
    return json.dumps(AppType.get_app_list(), ensure_ascii=False)

@app.route('/data_source/list')
def list_available_db_source():
    logger.info(f"trigger_list_available_db_source")
    data_source_list = [
        {"name": db_cfg["name"], "desc": db_cfg["desc"], "dialect":db_cfg["type"]}
    ]
    logger.info(f"list_available_db_source_return, {data_source_list}")
    return json.dumps(data_source_list, ensure_ascii=False)

@app.route('/<db_source>/table/list')
def list_available_tables(db_source):
    logger.info(f"trigger list_available_tables")
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
    doris = Doris(db_cfg)
    table_list = doris.get_schema_info()
    logger.info(f"get_table_schema_return, {table_list}")
    return json.dumps(table_list, ensure_ascii=False)

@app.route('/exec/task', methods=['POST'])
def execute_sql_query():
    logger.info(f"trigger execute_sql_query")
    sql = request.json.get('sql')
    doris = Doris(db_cfg)
    result = doris.exec_sql(sql)
    logger.info(f"execute_sql_query_return, {result}")
    return json.dumps(result, ensure_ascii=False)



if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    port = get_console_arg1()
    logger.info(f"listening_port {port}， db_cfg {db_cfg}")
    app.run(host='0.0.0.0', port=port)