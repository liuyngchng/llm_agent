#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama langchain_core langchain_community pandas tabulate pymysql
"""
import json
import logging.config
import os
import sqlite3

from flask import Flask, request, jsonify, render_template

import db_util
from sql_agent import get_dt_with_nl
from sys_init import init_yml_cfg

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)
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
    dt_idx = "nl2sql_index.html"
    logger.info(f"return page {dt_idx}")
    return render_template(dt_idx, uid = "my_uid_is_123")

@app.route('/cfg/idx', methods=['GET'])
def config_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_config_index {request.args}")
    usr=''
    try:
        tkn = request.args.get('tkn')
        if tkn != my_cfg['sys']['cfg_tkn']:
            raise "illegal_access_for_config"
        usr = request.args.get('usr')
        if not usr:
            return "user is null in config, please submit your username in config request"
    except Exception as e:
        logger.error(f"err_in_config_index, {e}, url: {request.url}", exc_info=True)
        raise "err_in_config_index"

    ctx = {
        "sys_name" : my_cfg['sys']['name'],
        "waring_info" : "",
        "usr": usr,
        "db_type":my_cfg['db']['type'],
        "db_name":my_cfg['db']['name'],
        "db_host":my_cfg['db']['host'],
        "db_usr": my_cfg['db']['user'],
        "db_psw": my_cfg['db']['password'],
    }
    my_conn = sqlite3.connect('test_config.db')
    check_sql = f"select id from user where name='{usr}' limit 1"
    check_info = db_util.sqlite_query_tool(my_conn, check_sql)
    logger.debug(f"check_info {check_info}")
    check_data = json.loads(check_info)['data']
    try:
        uid = check_data[0][0]
    except (IndexError, TypeError) as e:
        return "illegal user info in config request"

    check_sql = f"select uid, db_type, db_name, db_host, db_usr, db_psw from db_config where uid='{uid}' limit 1"
    db_config_info = db_util.sqlite_query_tool(my_conn, check_sql)
    logger.debug(f"check_info {db_config_info}")
    check_info = json.loads(db_config_info)['data']
    try:
        uid = check_info[0][0]
        ctx = {
            "sys_name": my_cfg['sys']['name'],
            "waring_info": "",
            "usr": usr,
            "db_type": check_info[0][1],
            "db_name": check_info[0][2],
            "db_host": check_info[0][3],
            "db_usr": check_info[0][4],
            "db_psw": check_info[0][5],
        }
    except (IndexError, TypeError) as e:
        logger.info(f"no db config for user {usr}")
    dt_idx = "config_index.html"
    logger.info(f"return page {dt_idx}")
    return render_template(dt_idx, **ctx)

@app.route('/cfg/idx', methods=['POST'])
def save_config():
    logger.info(f"save config info {request.form}")
    dt_idx = "config_index.html"
    my_conn = sqlite3.connect('test_config.db')
    ctx = {}
    try:
        usr = request.form.get('usr').strip()
        db_type = request.form.get('db_type').strip()
        db_host = request.form.get('db_host').strip()
        db_name = request.form.get('db_name').strip()
        db_usr = request.form.get('db_usr').strip()
        db_psw = request.form.get('db_psw').strip()

        ctx = {
            "sys_name": my_cfg['sys']['name'],
            "waring_info": "",
            "usr": usr,
            "db_type": db_type,
            "db_name": db_name,
            "db_host": db_host,
            "db_usr": db_usr,
            "db_psw": db_psw,
        }
        check_sql = f"select id from user where name='{usr}' limit 1"
        check_info = db_util.sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_info {check_info}")
        check_info=json.loads(check_info)['data']
        uid = check_info[0][0]
        insert_sql = (f"insert into db_config (uid, db_type, db_host, db_name, db_usr, db_psw) "
               f"values ('{uid}', '{db_type}', '{db_host}', '{db_name}', '{db_usr}', '{db_psw}')")
        db_util.sqlite_insert_tool(my_conn, insert_sql)
        logger.info(f"return page {dt_idx}")
        my_conn.close()
        ctx['waring_info'] = '保存成功'
        return render_template(dt_idx, **ctx)
    except Exception as e:
        my_conn.close()
        logger.error(f"err_in_config_index, {e}, url: {request.url}", exc_info=True)
        ctx['waring_info'] = '保存失败'
        return render_template(dt_idx, **ctx)


@app.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'
    :return:
    """
    data = request.get_json()
    print(data)
    return jsonify({"message": "Data received successfully!", "data": data}), 200

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
    my_conn = sqlite3.connect('test_config.db')
    sql = f"select id from user where name='{user}' and t = '{t}' limit 1"
    check_info = db_util.sqlite_query_tool(my_conn, sql)
    user_id = json.loads(check_info)['data']
    my_conn.close()
    if not user_id:
        logger.error(f"用户名或密码输入错误 {user}, {t}")
        ctx = {
            "user" : user,
            "sys_name" : my_cfg['sys']['name'],
            "waring_info" : "用户名或密码输入错误",

        }
        return render_template("login.html", **ctx)
    else:
        logger.info(f"return_page {dt_idx}")
        return render_template(dt_idx, uid=user_id[0][0], sys_name=my_cfg['sys']['name'])

@app.route('/query/data', methods=['POST'])
def query_data(catch=None):
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg').strip()
    uid = ''
    if my_cfg['sys']['auth']:
        my_conn = sqlite3.connect('test_config.db')
        try:
            uid = request.form.get('uid').strip()

            sql = f"select id from user where id='{uid}' limit 1"
            check_info = db_util.sqlite_query_tool(my_conn, sql)
            check_user_id = json.loads(check_info)['data']
            check_user_id = check_user_id[0][0]
            logger.info(f"rcv_uid {check_user_id}")
            my_conn.close()
            if not check_user_id:
                raise f"illegal_request {request}"
        except Exception as e:
            my_conn.close()
            logger.error(f"auth_err, {e}", exc_info=True)
            raise f"auth_err_for_request {request}"
    logger.info(f"rcv_msg: {msg}, from user {uid}")
    logger.info(f"ask_question({msg}, my_cfg, html, True)")
    answer = get_dt_with_nl(msg, my_cfg, 'markdown', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"

    return answer

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
