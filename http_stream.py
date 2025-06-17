#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import logging.config
import time

import cfg_util as cfg_utl

from flask import Flask, render_template, Response, request

from my_enums import DataType
from sql_yield import SqlYield
from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False
my_cfg = init_yml_cfg()

auth_info = {}

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours

@app.route('/', methods=['GET'])
def login_index():
    auth_flag = my_cfg['sys']['auth']
    if auth_flag:
        login_idx = "login.html"
        logger.info(f"return page {login_idx}")
        return render_template(login_idx, waring_info="", sys_name=my_cfg['sys']['name'])
    else:
        dt_idx = "nl2sql_index.html"
        ctx = {
            "uid": "foo",
            "sys_name": my_cfg['sys']['name']
        }
        logger.info(f"return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, **ctx)

@app.route('/login', methods=['POST'])
def login():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "stream_index.html"
    logger.debug(f"request_form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user_login: {user}, {t}")
    auth_result = cfg_utl.auth_user(user, t, my_cfg)
    logger.info(f"user_login_result: {user}, {t}, {auth_result}")
    if not auth_result["pass"]:
        logger.error(f"用户名或密码输入错误 {user}, {t}")
        ctx = {
            "user" : user,
            "sys_name" : my_cfg['sys']['name'],
            "waring_info" : "用户名或密码输入错误",
        }
        return render_template("login.html", **ctx)

    logger.info(f"return_page {dt_idx}")
    ctx = {
        "uid": auth_result["uid"],
        "t": auth_result["t"],
        "sys_name": my_cfg['sys']['name'],
        "greeting": cfg_utl.get_const("greeting")
    }
    session_key = f"{auth_result['uid']}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    return render_template(dt_idx, **ctx)



@app.route('/stream', methods=['POST', 'GET'])
def stream():
    logger.info(f"request.args {request.args}")
    t = int(request.args.get('t', 0))
    q = request.args.get('q', '')
    uid = request.args.get('uid', '')
    session_key = f"{uid}_{get_client_ip()}"
    if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
        return Response(
            illegal_access(uid),
            mimetype='text/event-stream; charset=utf-8'
        )
    logger.info(f"rcv_stream_req, t={t}, q={q}")
    sql_yield = SqlYield(my_cfg)
    return Response(
        sql_yield.yield_dt_with_nl(uid, q, DataType.HTML.value),
        mimetype='text/event-stream; charset=utf-8'
    )
    # return Response(generate_data(), mimetype='text/event-stream')

def illegal_access(uid):
    waring_info = "登录信息已失效，请重新登录后再使用本系统"
    logger.error(f"{waring_info}, {uid}")
    yield SqlYield.build_yield_dt(waring_info)

def generate_data():
    messages = ["大模型思考中...", "用户问题优化中...","优化后的问题是：***",
                "用户问题转换为SQL中...","SQL语句为：***","数据查询中...",
                "查询到的数据:****","正在绘图...","绘图结果为：\ndata_chart", "本次查询已完成"]
    for msg in messages:
        time.sleep(1)  # 模拟处理延迟
        yield f"data: {msg}\n\n"


def get_client_ip():
    """获取客户端真实 IP"""
    if forwarded_for := request.headers.get('X-Forwarded-For'):
        return forwarded_for.split(',')[0]
    return request.headers.get('X-Real-IP', request.remote_addr)

if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    app.run(host='0.0.0.0', port=19000)
