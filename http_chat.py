#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import json
import logging.config
import os
import time

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, redirect, jsonify, render_template, url_for

import cfg_util as cfg_utl
from sys_init import init_yml_cfg
from bp_auth import auth_bp, auth_info, get_client_ip
from bp_vdb import file_vdb
from vdb_util import search_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.register_blueprint(file_vdb)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours


@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source='chat'))


@app.route('/chat', methods=['POST'])
def chat(catch=None):
    """

    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/chat' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"msg":"who are you?"}'
    :return a string
    """
    logger.info(f"chat_request {request.form}")
    msg = request.form.get('msg', "").strip()
    uid = request.form.get('uid').strip()
    session_key = f"{uid}_{get_client_ip()}"
    if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
        waring_info = {
            "chart": {},
            "raw_dt": "登录信息已失效，请重新登录后再使用本系统", "sql": "",
            "explain_sql": "", "total_count": 0, "cur_page": 1,
            "total_page": 1
        }
        logger.error(f"{waring_info}, {uid}")
        return json.dumps(waring_info, ensure_ascii=False)
    logger.info(f"rcv_msg, {msg}, uid {uid}")
    auth_info[session_key] = time.time()
    my_vector_db_dir = f"upload_doc/faiss_oa_idx_{uid}"

    if not os.path.exists(my_vector_db_dir):  # 新增检查
        logger.info(f"vector_db_dir_not_exists_return_none, {my_vector_db_dir}")
        answer = "暂时没有相关知识提供给您，请您联系系统管理员"
    else:
        search_result = search_txt(msg, my_vector_db_dir, 0.1, my_cfg['api'], 3)
        # TODO: 以搜索到的文本内容作为RAG输入，请求大模型接口（兼容OpenAI方式）， 提供流式输出
        answer = ""

    # str_info = json.dumps(answer, ensure_ascii=False)
    logger.info(f"return {answer}")
    return answer


@app.route('/vdb/idx', methods=['GET'])
def vdb_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_vdb_index {request.args}")
    try:
        uid = request.args.get('uid').strip()
        if not uid:
            return "user is null in config, please submit your username in config request"
    except Exception as e:
        logger.error(f"err_in_vdb_index, {e}, url: {request.url}", exc_info=True)
        raise jsonify("err_in_vdb_index")
    ctx = cfg_utl.get_ds_cfg_by_uid(uid, my_cfg)
    ctx["uid"] = uid
    ctx['sys_name'] = my_cfg['sys']['name']
    ctx["waring_info"] = ""
    dt_idx = "vdb_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    logger.info(f"my_cfg {my_cfg.get('db')},\n{my_cfg.get('api')}")
    # test_query_data()
    app.config['ENV'] = 'dev'
    port = 19000
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
