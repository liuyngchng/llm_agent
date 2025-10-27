#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
知识库问答系统
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import logging.config
import os
import time

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, redirect, abort, url_for, send_from_directory
from chat_agent import ChatAgent
from common.my_enums import AppType
from common.sys_init import init_yml_cfg
from common.bp_auth import auth_bp, auth_info, get_client_ip
from common.bp_vdb import vdb_bp, VDB_PREFIX
from common.cm_utils import get_console_arg1
from common.vdb_meta_util import VdbMeta
from common.vdb_util import search_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
app.register_blueprint(auth_bp)
app.register_blueprint(vdb_bp)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False
# CORS(app, supports_credentials=True)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours

LLM_MODEL_DICT = {"1":"deepseek-v3", "2":"qwen2dot5-7b-chat"}

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


@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=AppType.CHAT.name.lower()))


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
    uid = request.form.get('uid')
    kb_id = request.form.get('kb_id')
    model_id = request.form.get('model_id')
    if not msg or not uid or not kb_id:
        warning_info = f"缺少用户消息、用户身份信息、知识库信息中的一个或多个参数，请您检查后再试"
        logger.error(f"{warning_info}, {msg}, {uid}, {kb_id}, {model_id}")
        return warning_info
    session_key = f"{uid}_{get_client_ip()}"
    if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
        warning_info = "用户登录信息已失效，请重新登录后再使用本系统"
        logger.error(f"{warning_info}, {uid}")
        return warning_info
    logger.info(f"rcv_msg, {msg}, uid {uid}")
    auth_info[session_key] = time.time()
    vdb_info = VdbMeta.get_vdb_info_by_id(kb_id)
    if not vdb_info:
        warning_info = f"所选择的知识库不存在，请您检查后再试"
        logger.error(f"{warning_info}, {kb_id}")
        return warning_info
    my_vector_db_dir = f"{VDB_PREFIX}{vdb_info[0]['uid']}_{kb_id}"
    if not os.path.exists(my_vector_db_dir):  # 新增检查
        answer = "暂时没有相关知识提供给您，请您先上传文档，创建知识库"
        logger.info(f"vector_db_dir_not_exists_return_none, {answer}, {my_vector_db_dir}")
        return answer
    if model_id:
        my_cfg['api']['llm_model_name'] = LLM_MODEL_DICT.get(model_id)
        logger.info(f"llm_cfg_customized_for_uid, {uid}, {my_cfg['api']['llm_model_name']}")
    context = search_txt(msg, my_vector_db_dir, 0.1, my_cfg['api'], 3)
    if not context:
        answer = "暂时没有相关内容提供给您，您可以尝试换一个问题试试"
        logger.info(f"vector_db_search_return_none, {answer}, {my_vector_db_dir}")
        return answer
    chat_agent = ChatAgent(my_cfg)
    def generate_stream():
        full_response = ""
        stream_input = {"context": context, "question": msg}
        logger.info(f"stream_input {stream_input}")
        for chunk in chat_agent.get_chain().stream(stream_input):
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
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
