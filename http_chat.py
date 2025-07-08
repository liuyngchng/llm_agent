#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import logging.config
import os
import time

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, redirect, url_for

from chat_agent import ChatAgent
from sys_init import init_yml_cfg
from bp_auth import auth_bp, auth_info, get_client_ip
from bp_vdb import vdb_bp
from vdb_util import search_txt


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.register_blueprint(vdb_bp)
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
        waring_info = "登录信息已失效，请重新登录后再使用本系统"
        logger.error(f"{waring_info}, {uid}")
        return waring_info
    logger.info(f"rcv_msg, {msg}, uid {uid}")
    auth_info[session_key] = time.time()
    my_vector_db_dir = f"upload_doc/faiss_oa_idx_{uid}"

    if not os.path.exists(my_vector_db_dir):  # 新增检查
        logger.info(f"vector_db_dir_not_exists_return_none, {my_vector_db_dir}")
        answer = "暂时没有相关知识提供给您，请您先上传文档，创建知识库"
        return answer
    else:
        context = search_txt(msg, my_vector_db_dir, 0.1, my_cfg['api'], 3)
        chat_agent = ChatAgent(my_cfg)
        def generate_stream():
            full_response = ""
            for chunk in chat_agent.get_chain().stream({"context": context, "question": msg}):
                full_response += chunk
                yield chunk
            logger.info(f"full_response: {full_response}")
        return app.response_class(generate_stream(), mimetype='text/event-stream')

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
