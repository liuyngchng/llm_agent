#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
AI 应用市场
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import logging.config
import os

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template

from common.bp_auth import get_client_ip
from common.cm_utils import get_console_arg1
from common.sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False

os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours
my_cfg = init_yml_cfg()

@app.route('/')
def app_home():
    ctx = {
        "host": my_cfg['sys']['host']
    }
    ip = get_client_ip()
    logger.info(f"ctx, {ctx}, from_ip, {ip}")

    return render_template("portal_index.html", **ctx)



if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    # test_query_data()
    app.config['ENV'] = 'dev'
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
