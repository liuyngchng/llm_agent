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
from flask import Flask, send_from_directory, abort, current_app, request

from common import my_enums
from common.bp_auth import get_client_ip, auth_bp
from common.cm_utils import get_console_arg1
from common.sys_init import init_yml_cfg

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)
my_cfg = init_yml_cfg()

app = Flask(__name__, static_folder=None)
app.config['CFG'] = {}
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = my_enums.AppType.PORTAL.name.lower()

app.register_blueprint(auth_bp)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False

os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

my_cfg = init_yml_cfg()


def forward_to(endpoint, **kwargs):
    """
    手动实现 forward 功能（服务器内部转发）

    Args:
        endpoint: 目标端点名称，格式如 'auth.login_index'
        **kwargs: 传递给目标视图函数的参数

    Returns:
        目标视图函数的响应对象
    """
    # 获取目标视图函数
    view_func = current_app.view_functions.get(endpoint)
    if not view_func:
        logger.error(f"forward_to endpoint not found: {endpoint}")
        abort(404)

    # 可选：记录转发信息，方便调试
    current_app.logger.debug(f"Forwarding from {request.endpoint} to {endpoint}")

    # 执行目标视图函数，保持当前请求上下文
    return view_func(**kwargs)


@app.route('/')
def app_home():
    app_base_uri = my_cfg['sys'].get('app_base_uri', '')
    ip = get_client_ip()
    if "INVALID_IP" == ip:
        return json.dumps({"status":403, "msg":"illegal access"})
    logger.info(f"redirect_auth_login_index, from_ip, {ip}")
    return forward_to('auth.login_index',
                      app_source=my_enums.AppType.PORTAL.name.lower(),
                      app_base_uri=app_base_uri)
    # return redirect(url_for('auth.login_index', app_source=my_enums.AppType.PORTAL.name.lower(),host = host))
    # ctx = {
    #     "host": host
    # }
    # return render_template("portal_index.html", **ctx)

@app.route('/static/<path:file_name>')
def get_static_file(file_name):
    static_dirs = [
        os.path.join(os.path.dirname(__file__), '../../common/static'),
        os.path.join(os.path.dirname(__file__), 'static'),
    ]

    for static_dir in static_dirs:
        if os.path.exists(os.path.join(static_dir, file_name)):
            logger.debug(f"get_static_file, {static_dir}, {file_name}")
            return send_from_directory(static_dir, file_name)
    logger.error(f"no_file_found_error, {file_name}")
    abort(404)

@app.route('/webfonts/<path:file_name>')
def get_webfonts_file(file_name):
    font_file_name = f"webfonts/{file_name}"
    return get_static_file(font_file_name)



if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    # test_query_data()
    app.config['ENV'] = 'dev'
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
