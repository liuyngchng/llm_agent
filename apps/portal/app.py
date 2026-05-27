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
import time

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, send_from_directory, abort, request, render_template, redirect, url_for

from common import my_enums, statistic_util, cm_utils
from common.bp_auth import get_client_ip, auth_bp, auth_info
from common.cm_utils import get_console_arg1
from common.i18n._hooks import register_i18n
from common.sys_init import init_yml_cfg
from common.const import get_const

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
register_i18n(app, scope="portal")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False

os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

my_cfg = init_yml_cfg()


@app.route('/')
def app_home():
    app_source = my_enums.AppType.PORTAL.name.lower()
    app_base_uri = my_cfg['sys'].get('app_base_uri', '')
    ip = get_client_ip()
    if "INVALID_IP" == ip:
        return json.dumps({"status":403, "msg":"illegal access"})

    t = request.args.get("t")
    if t:
        session_info = cm_utils.decode_token(t, my_cfg['sys']['cypher_key'])
        if session_info:
            uid = session_info['uid']
            usr = ''
            try:
                auth_api = my_cfg['api'].get('auth_api', '')
                resp = requests.get(f"{auth_api}/auth/user/{uid}", timeout=5,verify=False)
                if resp.status_code == 200:
                    usr = resp.json().get('name', '')
            except Exception as e:
                logger.warning(f"get_user_name_from_auth_service_failed, uid={uid}, err={e}")
            hack_admin = "1" if session_info['role'] == 2 else "0"

            greeting = get_const("greeting", app_source)
            arg1 = get_const("arg1", app_source)
            arg2 = get_const("arg2", app_source)
            arg3 = get_const("arg3", app_source)
            sys_name = my_enums.AppType.get_app_type(app_source)

            ctx = {
                "uid": uid,
                "usr": usr,
                "role": session_info['role'],
                "t": t,
                "sys_name": sys_name,
                "app_base_uri": app_base_uri,
                "greeting": greeting,
                "app_source": app_source,
                "hack_admin": hack_admin,
                "arg1": arg1,
                "arg2": arg2,
                "arg3": arg3,
            }

            session_key = f"{uid}_{ip}"
            auth_info[session_key] = time.time()
            statistic_util.add_access_count_by_uid(uid, 1, app_source)
            logger.info(f"return_page_portal_index, uid={uid}")
            return render_template("portal_index.html", **ctx)

    logger.info(f"no_valid_token_redirect_auth_login_index, from_ip {ip}")
    return redirect(url_for('auth.login_index', app_source=app_source, app_base_uri=app_base_uri))

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
