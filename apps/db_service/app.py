#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
AI 应用市场
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import json
import logging.config
import os

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request

from common import cfg_util
from common.bp_auth import get_client_ip
from common.cm_utils import get_console_arg1
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

    return json.dumps({"status":200, "msg":"hello, db service"}), 200

@app.route('/usr/<usr_name>', methods =['GET'])
def get_uid_by_user(usr_name):
    """根据用户名称获取uid"""
    return cfg_util.get_uid_by_user(usr_name)

@app.route('/usr/<uid>', methods =['GET'])
def get_user_info_by_uid(uid):
    return cfg_util.get_user_info_by_uid(uid)

@app.route('/usr/auth', methods=['POST'])
def auth_usr():
    """
    用户登录认证
    """
    data = request.json
    user = data['user']
    t = data['t']
    return cfg_util.auth_user(user, t, my_cfg)



if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    # test_query_data()
    app.config['ENV'] = 'dev'
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
