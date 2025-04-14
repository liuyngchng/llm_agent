#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import json
import logging.config
import os

from flask import Flask, request, jsonify, render_template, Response

import config_util
from sql_agent import get_dt_with_nl
from sys_init import init_yml_cfg
from audio import transcribe_webm_audio_bytes

# 加载配置
logging.config.fileConfig('logging.conf', encoding="utf-8")

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 中文直接输出，而不是转义成为\u的转义字符
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)


@app.route('/gt/dt/idx', methods=['GET'])
def query_data_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    page = "nl2sql_index.html"
    auth_result = authenticate(request)
    if not auth_result:
        page = "login.html"
    logger.info(f"return page {page}")
    return render_template(page, uid ="my_uid_is_123")

@app.route('/cfg/idx', methods=['GET'])
def config_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_config_index {request.args}")
    try:
        uid = request.args.get('uid').strip()
        if not uid:
            return "user is null in config, please submit your username in config request"
    except Exception as e:
        logger.error(f"err_in_config_index, {e}, url: {request.url}", exc_info=True)
        raise jsonify("err_in_config_index")
    ctx = config_util.get_data_source_config_by_uid(uid, my_cfg)
    ctx["uid"] = uid
    ctx['sys_name']=my_cfg['sys']['name']
    ctx["waring_info"]=""
    dt_idx = "config_index.html"
    logger.info(f"return page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@app.route('/cfg/idx', methods=['POST'])
def save_config():
    logger.info(f"save config info {request.form}")
    dt_idx = "config_index.html"
    uid = request.form.get('uid').strip()
    db_type = request.form.get('db_type').strip()
    db_host = request.form.get('db_host').strip()
    db_port = request.form.get('db_port').strip()
    db_name = request.form.get('db_name').strip()
    db_usr  = request.form.get('db_usr').strip()
    db_psw  = request.form.get('db_psw').strip()
    data_source_cfg = {
        "sys_name": my_cfg['sys']['name'],
        "waring_info": "",
        "uid": uid,
        "db_type": db_type,
        "db_name": db_name,
        "db_host": db_host,
        "db_port": db_port,
        "db_usr": db_usr,
        "db_psw": db_psw,
    }
    usr = config_util.get_user_by_uid(uid)
    if not usr:
        data_source_cfg['waring_info'] = '当前用户非法'
        return render_template(dt_idx, **data_source_cfg)
    save_cfg_result = config_util.save_data_source_config(data_source_cfg, my_cfg)
    if save_cfg_result:
        data_source_cfg['waring_info'] = '保存成功'
    else:
        data_source_cfg['waring_info'] = '保存失败'
    return render_template(dt_idx, **data_source_cfg)


@app.route('/status', methods=['GET'])
def get_status():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X GET  'http://127.0.0.1:19000/status' -H "Content-Type: application/json"
    :return:
    """
    data = {"message": "数据正常, service OK"}
    response = Response(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
        status=200
    )
    return response

@app.route('/', methods=['GET'])
def login_index():
    auth_flag = my_cfg['sys']['auth']
    if auth_flag:
        login_idx = "login.html"
        logger.info(f"return page {login_idx}")
        return render_template(login_idx, waring_info="", sys_name=my_cfg['sys']['name'])
    else:
        dt_idx = "nl2sql_index.html"
        logger.info(f"return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, uid='foo', sys_name=my_cfg['sys']['name'])

@app.route('/login', methods=['POST'])
def login():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "nl2sql_index.html"
    logger.debug(f"request.form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user login: {user}, {t}")
    auth_result = config_util.auth_user(user, t)
    logger.info(f"user login result: {user}, {t}, {auth_result}")
    if not auth_result["pass"]:
        logger.error(f"用户名或密码输入错误 {user}, {t}")
        ctx = {
            "user" : user,
            "sys_name" : my_cfg['sys']['name'],
            "waring_info" : "用户名或密码输入错误",
        }
        return render_template("login.html", **ctx)
    else:
        logger.info(f"return_page {dt_idx}")
        return render_template(dt_idx, uid=auth_result["uid"], sys_name=my_cfg['sys']['name'])

@app.route('/query/data', methods=['POST'])
def query_data(catch=None):
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg').strip()
    auth_result = authenticate(request)
    if not auth_result:
        data = {"chart":{}, "raw_dt":{}, "msg":"illegal access"}
        logger.error(f"illegal_access, {request}")
        return Response(
            json.dumps(data, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=200
        )
    logger.info(f"rcv_msg: {msg}")
    logger.info(f"ask_question({msg}, my_cfg, html, True)")
    answer = get_dt_with_nl(msg, my_cfg, 'markdown', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"

    return answer


def authenticate(req)->bool:
    if not my_cfg['sys']['auth']:
        return True
    result = False
    try:
        if config_util.get_user_by_uid(req.form.get('uid').strip()):
            result = True
        else:
            logger.error(f"illegal_request {req}")
    except Exception as e:
        logger.error(f"authenticate_err, {req}, {e}", exc_info=True)
    return result


@app.route('/gt/db/dt', methods=['POST'])
def get_db_dt():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000//gt/db/dt' -H "Content-Type: application/json"  -d '{"msg":"把数据明细给我调出来"}'
    :return:
    """
    msg = request.get_json().get('msg').strip()
    logger.info(f"rcv_msg: {msg}")
    logger.info(f"ask_question({msg}, {my_cfg}, 'json')")
    answer = get_dt_with_nl(msg, my_cfg, 'json', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer='{"msg":"没有查询到相关数据，请您尝试换个问题进行提问", "code":404}'

    return answer


@app.route('/trans/audio', methods=['POST'])
def transcribe_audio() -> tuple[Response, int] | Response:
    """
    curl -s --noproxy '*' -w '\n' -X POST -F 'audio=@static/asr_test.webm' 'http://localhost:19000/trans/audio'
    """
    if request.content_length > 10 * 1024 * 1024:
        return Response(
            json.dumps("数据长度太大，已超过10MB", ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=413
        )
    try:
        audio_file = request.files.get('audio')
        if not audio_file or not audio_file.filename.endswith('.webm'):
            return jsonify({"error": "invalid webm file"}), 400
        audio_bytes = audio_file.read()
        result = transcribe_webm_audio_bytes(audio_bytes, my_cfg)
        data = {"text": result}
    except Exception as e:
        logger.exception("语音识别接口异常")
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
    answer = get_dt_with_nl(msg, my_cfg, 'markdown', True)
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"
    logger.info(f"answer is：\n{answer}")
    return answer


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    logger.info(f"my_cfg {my_cfg}")
    # test_query_data()
    app.run(host='0.0.0.0', port=19000)
