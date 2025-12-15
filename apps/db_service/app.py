#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
数据服务，提供操作底层数据存储的入口
pip install gunicorn flask concurrent-log-handler pymysql
"""
import datetime
import json
import logging.config
import os

import pymysql
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, Response

from common.bp_auth import get_client_ip
from common.cm_utils import get_console_arg1
from common.const import JSON_MIME_TYPE, DB_CONN_TIMEOUT, DB_RW_TIMEOUT
from common.db_util import DbUtl
from common.sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False

os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

my_cfg = init_yml_cfg()

@app.route('/')
def app_home():
    ip = get_client_ip()
    logger.info(f"from_ip, {ip}")
    result = json.dumps({"status":200, "msg":"hello, db service"})
    return Response(result, content_type=JSON_MIME_TYPE, status=200)

@app.route('/dml/dt', methods =['POST'])
def dml_dt():
    """执行相应的 DML 语句"""
    data = request.json
    sql = data['sql']
    t = data['t']
    output_dt = mysql_output(my_cfg, sql)
    dt = json.dumps(output_dt)
    return Response(dt, content_type=JSON_MIME_TYPE, status=200)


def mysql_output(cfg: dict, sql:str) -> dict:
    """
    db_uri = mysql+pymysql://user:pswd@host/db
    """
    db_config = cfg.get('db', {})

    cif = DbUtl.build_mysql_con_dict_from_cfg(db_config)
    with pymysql.connect(
        host=cif['host'], port=cif['port'],
        user=cif['user'], password=cif['password'],
        database=cif['database'], charset=cif['charset'],
        connect_timeout=DB_CONN_TIMEOUT,
        read_timeout=DB_RW_TIMEOUT,
        write_timeout=DB_RW_TIMEOUT
    ) as my_conn:
        sql1 = sql.replace("\n", " ")
        logger.info(f"mysql_output_data, {sql1})")
        return mysql_query_tool(my_conn, sql1)


def mysql_query_tool(db_con, query: str) -> dict:
    try:
        with db_con.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            # data = cursor.fetchall()
            data = [
                tuple(
                    item.isoformat() if isinstance(item, (datetime.date, datetime.datetime)) else item
                    for item in row
                )
                for row in cursor.fetchall()
            ]
            return {"columns": columns, "data": data}
    except Exception as e:
        logger.error(f"mysql_query_err: {e}")
        raise e



if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    # test_query_data()
    app.config['ENV'] = 'dev'
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
