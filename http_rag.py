#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""
import json
import logging.config
import os
import re

from flask import Flask, request, jsonify, render_template, Response, send_from_directory, abort, make_response

from config_util import auth_user, get_consts
from semantic_search import search, classify_question, fill_dict
from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
session_dict = {}
const_dict = get_consts()


@app.route('/', methods=['GET'])
def login_index():
    auth_flag = my_cfg['sys']['auth']
    if auth_flag:
        login_idx = "login.html"
        logger.info(f"return page {login_idx}")
        return render_template(login_idx, waring_info="", sys_name=my_cfg['sys']['name'])
    else:
        dt_idx = "rag_index.html"
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
    dt_idx = "rag_index.html"
    logger.debug(f"request.form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user login: {user}, {t}")
    auth_result = auth_user(user, t)
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


@app.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'
    :return:
    """
    logger.info("health_check")
    return jsonify({"status": 200}), 200
    # return Response({"status":200}, content_type=content_type, status=200)



@app.route('/static/<file_name>', methods=['GET'])
def get_file(file_name):
    """
    返回静态文件
    """
    if not re.match(r'^[\w\-\\.]+\.(png|jpg|jpeg|css|js|woff2?|ttf|ico|svg)$', file_name):  # 限制文件名格式
        logger.error(f"return_400_for_file_request {file_name}")
        abort(400)
    if not file_name or '/' in file_name:  # 防止路径遍历
        logger.error(f"return_400_for_file_request {file_name}")
        abort(400)
    static_dir = os.path.join(app.root_path, 'static')
    if not os.path.exists(os.path.join(static_dir, file_name)):
        logger.error(f"return_404_for_file_request {file_name}")
        abort(404)
    logger.info(f"return static file {file_name}")
    return send_from_directory(static_dir, file_name)


@app.route('/rag/submit', methods=['POST'])
def submit():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/rag/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg')
    uid = request.form.get('uid')
    logger.info("rcv_msg: {}".format(msg))
    labels = json.loads(const_dict.get("classify_label"))
    classify_result = classify_question(labels, msg, my_cfg, True)
    logger.info(f"classify_result: {classify_result}")
    content_type='text/markdown; charset=utf-8'
    if labels[1] in classify_result:
        user_dict = json.loads(const_dict.get("chat4"))
        if uid in session_dict and session_dict[uid]:
            user_dict = fill_dict(session_dict[uid], user_dict, my_cfg, True)
            logger.info(f"html_table_with_personal_info_filled_in for {labels[1]}")
        else:
            logger.info(f"{uid},current_id_not_in_person_info, {session_dict}")
        content_type = 'text/html; charset=utf-8'
        logger.info(f"answer_for_classify {labels[1]}:\nuser_dict: {user_dict}")
        response = make_response(render_template("door_service.html", **user_dict))
        response.headers['Content-Type'] = content_type
        response.status_code = 200
        return response
    if labels[0] in classify_result:
        # answer = search(msg, my_cfg, True)
        txt = const_dict.get("wechat_txt")
        bill_addr = const_dict.get("bill_addr_svg")
        answer = f'''{txt}<div style="width: 200px; height: 200px">{bill_addr}</div>'''
        logger.info(f"answer_for_classify {labels[0]}:\n{txt}")
    elif any(label in classify_result for label in labels[2:6]):
        if uid not in session_dict:
            logger.info(f"{uid} uid_not_in_person_info {session_dict}")
            session_dict[uid] = msg
        else:
            session_dict[uid] += ", " + msg
        logger.info(f"person_info[{uid}] = {session_dict[uid]} ")
        answer = const_dict.get("chat1")
        logger.info(f"answer_for_classify {labels[2:6]}:\n{answer}")
    else:
        answer = const_dict.get("chat2")
        logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
    return Response(answer, content_type=content_type, status=200)


@app.route('/door/srv', methods=['POST'])
def door_service():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    user_dict = request.form
    content_type = 'text/html; charset=utf-8'
    response = make_response(render_template("door_service_answer.html", **user_dict))
    response.headers['Content-Type'] = content_type
    response.status_code = 200
    return response


def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database,
    and the output the answer.
    """
    logger.info(f"config {my_cfg}")
    my_question = "我想充值缴费？"
    logger.info(f"invoke question: {my_question}")
    answer = search(my_question, my_cfg, True)
    logger.info(f"answer is \r\n{answer}")

if __name__ == '__main__':
    # test_req()
    app.run(host='0.0.0.0', port=19000)
