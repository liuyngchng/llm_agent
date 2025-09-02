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
my_cfg = init_yml_cfg()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    welcome = {"info":"welcome to open api", "status": 200}
    return json.dumps(welcome, ensure_ascii=False)

@app.route('/app/list')
def list_available_app():
    logger.info(f"trigger list_available_app")
    return json.dumps(AppType.get_app_list(), ensure_ascii=False)

@app.route('/data_source/list')
def list_available_db_source():
    logger.info(f"trigger list_available_db_source")
    data_source_list = [
        {"name": my_cfg.get("db")["name"], "desc": my_cfg.get("db")["desc"]}
    ]
    return json.dumps(data_source_list, ensure_ascii=False)

@app.route('/<db_source>/table/list')
def list_available_tables(db_source):
    logger.info(f"trigger list_available_tables")
    doris = Doris(my_cfg)
    table_list = doris.get_schema_info()
    return json.dumps(table_list, ensure_ascii=False)

@app.route('/<db_source>/<table_name>/schema')
def get_table_schema(db_source, table_name):
    logger.info(f"trigger get_table_schema")
    doris = Doris(my_cfg)
    table_list = doris.get_schema_info()
    return json.dumps(table_list, ensure_ascii=False)

@app.route('/exec/task', METHODS=['POST'])
def execute_sql_query():
    logger.info(f"trigger execute_sql_query")
    sql = request.json.get('sql')
    doris = Doris(my_cfg)
    result = doris.exec_sql(sql)
    return json.dumps(result, ensure_ascii=False)



if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)