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
from flask import Flask, request, redirect, jsonify, render_template, Response, url_for

import cfg_util as cfg_utl
from my_enums import DataType, DBType
from sql_agent import SqlAgent
from sys_init import init_yml_cfg
from audio import transcribe_webm_audio_bytes
from http_auth import auth_bp, auth_info, get_client_ip
from vdb_util import search_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['JSON_AS_ASCII'] = False
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

# user's last sql, {"my_uid": {"sql":"my_sql", "curr_page":1, "total_page":1}}
# last search sql, current page and total page for the SQL
usr_page_dt = {}

# {"uid1":17234657891, "uid2":176543980}

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours

@app.before_request
def before_request():
    if app.config.get('ENV') == 'dev':
        return
    if not request.is_secure:
        url = request.url.replace('http://', 'https://', 1)
        logger.info(f"redirect_http_to_https, {url}")
        return redirect(url, code=301)

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source='chat'))


@app.route('/chat', methods=['POST'])
def chat(catch=None):
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"msg":"who are you?"}'
    :return a string
    """
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
        answer = ""

    return json.dumps(answer, ensure_ascii=False)


@app.route('/trans/audio', methods=['POST'])
def transcribe_audio() -> tuple[Response, int] | Response:
    """
    curl -s --noproxy '*' -w '\n' -X POST 'http://localhost:19000/trans/audio'
        -F 'audio=@static/asr_test.webm'
    """
    if request.content_length > 10 * 1024 * 1024:
        return Response(
            json.dumps("数据长度太大，已超过10MB", ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=413
        )
    try:
        logger.info("audio_stream_received")
        audio_file = request.files.get('audio')
        if not audio_file or not audio_file.filename.endswith('.webm'):
            return jsonify({"error": "invalid webm txt_file"}), 400
        audio_bytes = audio_file.read()
        logger.info("transcribe_webm_audio_bytes_start")
        result = transcribe_webm_audio_bytes(audio_bytes, my_cfg)
        logger.info(f"transcribe_webm_audio_bytes_return_txt, {result}")
        data = {"text": result}
    except Exception as e:
        logger.exception(f"语音识别接口异常, {e}")
        data = {"text": "语音识别异常，请检查语音识别服务是否正常"}

    response = Response(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
        status=200
    )
    try:
        origin = my_cfg["sys"]["allowed_origin"]
        response.headers.add('Access-Control-Allow-Origin', origin)
    except Exception as ex:
        logger.error(f"set_origin_err, {ex}")
    response.headers.add('Access-Control-Allow-Methods', 'POST')
    return response

def test_query_data():
    """
    for test purpose only
    """
    msg = "查询2025年的数据"
    logger.info(f"ask_question({msg}, {my_cfg}, markdown, True)")
    sql_agent = SqlAgent(my_cfg)
    answer = sql_agent.get_dt_with_nl("123", msg, DataType.MARKDOWN.value)
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"
    logger.info(f"answer_is：\n{answer}")
    return answer

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
