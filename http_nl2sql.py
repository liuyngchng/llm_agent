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
from http_auth import auth_bp, auth_info

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
    return redirect(url_for('auth.login_index', app_source='nl2sql'))

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
    logger.info(f"return_page {page}")
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
    ctx = cfg_utl.get_ds_cfg_by_uid(uid, my_cfg)
    ctx["uid"] = uid
    ctx['sys_name'] = my_cfg['sys']['name']
    ctx["waring_info"] = ""
    dt_idx = "config_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@app.route('/cfg/dt', methods=['POST'])
def save_config():
    logger.info(f"save_config_info {request.form}")
    dt_idx = "config_index.html"
    uid = request.form.get('uid').strip()
    db_type = request.form.get('db_type').strip()
    db_host = request.form.get('db_host').strip()
    db_port = request.form.get('db_port').strip()
    db_name = request.form.get('db_name').strip()
    db_usr  = request.form.get('db_usr').strip()
    db_psw  = request.form.get('db_psw').strip()
    tables = request.form.get('tables').strip()
    add_chart = request.form.get('add_chart').strip()
    is_strict = request.form.get('is_strict').strip()
    llm_ctx = request.form.get('llm_ctx').strip()
    data_source_cfg = {
        "sys_name":     my_cfg['sys']['name'],
        "waring_info":  "",
        "uid":          uid,
        "db_type":      db_type,
        "db_name":      db_name,
        "db_host":      db_host,
        "db_port":      db_port,
        "db_usr":       db_usr,
        "db_psw":       db_psw,
        "tables":       tables,
        "add_chart":    add_chart,
        "is_strict":    is_strict,
        "llm_ctx":      llm_ctx
    }
    usr = cfg_utl.get_user_name_by_uid(uid)
    if data_source_cfg["db_type"] == DBType.SQLITE.value:
        data_source_cfg['waring_info'] = '数据库类型有误'
        return render_template(dt_idx, **data_source_cfg)
    if not usr:
        data_source_cfg['waring_info'] = '非法访问，请您先登录系统'
        return render_template(dt_idx, **data_source_cfg)
    save_cfg_result = cfg_utl.save_ds_cfg(data_source_cfg, my_cfg)
    if save_cfg_result:
        data_source_cfg['waring_info'] = '保存成功'
    else:
        data_source_cfg['waring_info'] = '保存失败'
    # sql_agent = SqlAgent(cfg_utl.build_data_source_cfg_with_uid(uid, my_cfg))
    # data_source_cfg["schema"] = f"表清单: {sql_agent.get_all_tables()}\n {sql_agent.get_schema_info()}"
    return render_template(dt_idx, **data_source_cfg)


@app.route('/cfg/delete', methods=['POST'])
def delete_config():
    logger.info(f"del_cfg_info {request.data}")
    uid = json.loads(request.data).get('uid').strip()
    logger.info(f"del_cfg_info_for_uid_{uid}")
    usr = cfg_utl.get_user_name_by_uid(uid)
    waring_info = {"success": False, "msg": ""}
    if not usr:
        waring_info['msg'] = '非法访问，请先登录系统'
        return waring_info
    delete_cfg_result = cfg_utl.delete_data_source_config(uid, my_cfg)
    if delete_cfg_result:
        waring_info['msg'] = '删除成功'
        waring_info['success'] = True
    else:
        waring_info['msg'] = '删除失败'
    logger.info(f"del_cfg_info_for_uid_{uid}, return {waring_info}")
    return waring_info

@app.route('/status', methods=['GET'])
def get_status():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X GET  'http://127.0.0.1:19000/status' \
        -H "Content-Type: application/json"
    :return:
    """
    data = {"message": "数据正常, service OK"}
    response = Response(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
        status=200
    )
    return response

@app.route('/query/data', methods=['POST'])
def query_data(catch=None):
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"msg":"who are you?"}'
    :return a string
    """
    msg = request.form.get('msg', "").strip()\
        # .replace("截至", "").replace("截止", "")
    uid = request.form.get('uid').strip()
    page = request.form.get('page')
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
    logger.info(f"rcv_msg, {msg}, uid {uid}, page {page}")
    auth_info[session_key] = time.time()
    if uid and uid != 'foo':
        logger.info(f"build_ds_cfg_with_uid_{uid}")
        ds_cfg = cfg_utl.build_data_source_cfg_with_uid(uid, my_cfg)
        logger.info(f"ds_cfg_for_uid_{uid}, {ds_cfg.get('db', '')}")
    else:
        ds_cfg = my_cfg
    ds_src_cfg = cfg_utl.get_ds_cfg_by_uid(uid, my_cfg)
    sql_agent = SqlAgent(ds_cfg, prompt_padding=ds_src_cfg.get('llm_ctx', ""))
    if not msg and usr_page_dt.get(uid, None) and page and page != '':
        usr_page_dt[uid]["cur_page"] += 1
        logger.info(f"usr_page_dt_for_{uid}: {json.dumps(usr_page_dt[uid], ensure_ascii=False)}")
        answer = sql_agent.get_pg_dt(uid, usr_page_dt[uid])
    else:
        logger.info(f"get_dt_with_nl({uid}, {msg}, {DataType.MARKDOWN.value})")
        answer = sql_agent.get_dt_with_nl(uid, msg, DataType.MARKDOWN.value)
        usr_page_dt[uid] = answer.copy()
        usr_page_dt[uid].pop("chart", None)
        usr_page_dt[uid].pop("raw_dt", None)
        logger.info(f"usr_page_dt_for_{uid}: {json.dumps(usr_page_dt[uid], ensure_ascii=False)}")
        if not answer:
            answer = {
                "chart": {},
                "raw_dt": "没有查询到相关数据，请您尝试换个问题试试", "sql": "",
                "explain_sql": "", "total_count": 0, "cur_page": 1,
                "total_page": 1
            }
    return json.dumps(answer, ensure_ascii=False)


def authenticate(req)->bool:
    if not my_cfg['sys']['auth']:
        return True
    result = False
    try:
        if cfg_utl.get_user_name_by_uid(
            req.form.get('uid').strip()
        ):
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
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000//gt/db/dt' \
        -H "Content-Type: application/json" \
        -d '{"msg":"ababababa"}'
    :return:
    """
    msg = request.get_json().get('msg').strip()
    uid = request.get_json().get('uid').strip()
    logger.info(f"rcv_msg: {msg}, uid {uid}")
    auth_result = authenticate(request)
    if not auth_result:
        return json.dumps({"msg":"illegal_access_users", "code":502}, ensure_ascii=False)
    sql_agent = SqlAgent(my_cfg)
    answer = sql_agent.get_dt_with_nl(uid, msg, DataType.JSON.value)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer=json.dumps({"msg":"没有查询到相关数据，请您尝试换个问题进行提问", "code":404}, ensure_ascii=False)
    return answer


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

def get_client_ip():
    """获取客户端真实 IP"""
    if forwarded_for := request.headers.get('X-Forwarded-For'):
        return forwarded_for.split(',')[0]
    return request.headers.get('X-Real-IP', request.remote_addr)


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
