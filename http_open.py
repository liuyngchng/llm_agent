#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对第三方系统开放的接口
"""
import json
import logging.config

from flask import Flask, url_for, redirect

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


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)