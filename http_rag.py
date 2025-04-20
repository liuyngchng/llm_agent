#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""

import logging.config
import os
import re

from flask import Flask, request, jsonify, render_template, Response, send_from_directory, abort

from config_util import auth_user
from semantic_search import search, classify_question, fill_table
from sys_init import init_yml_cfg
from utils import rmv_think_block

# 加载配置
logging.config.fileConfig('logging.conf', encoding="utf-8")

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
person_info = {}

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
    data = request.get_json()
    print(data)
    return jsonify({"message": "Data received successfully!", "data": data}), 200

@app.route('/static/<file_name>', methods=['GET'])
def get_img(file_name):
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
    labels = ["缴费", "上门服务", "个人资料", "自我介绍", "个人信息", "身份登记", "其他"]
    classify_result = classify_question(labels, msg, my_cfg, True)
    logger.info(f"classify_result: {classify_result}")
    content_type='text/markdown; charset=utf-8'
    if labels[0] in classify_result:
        answer = search(msg, my_cfg, True)
        answer = rmv_think_block(answer)
    elif labels[1] in classify_result:
        with open('static/service2.html', 'r', encoding='utf-8') as file:
            content = file.read()
        if uid in person_info and person_info[uid]:
            answer_html = fill_table(person_info[uid], content, my_cfg, True)
            logger.info(f"html_table_with_personal_info_filled_in {answer_html}")
        else:
            answer_html = content
        content_type = 'text/html; charset=utf-8'
        answer = f"<div>请填写以下信息，我们将安排工作人员上门为您提供服务</div> {answer_html}"
    elif any(label in classify_result for label in labels[2:6]):
        if uid not in person_info:
            person_info[uid] = msg
        else:
            person_info[uid] += ", " + msg
        logger.info(f"person_info[{uid}] = {person_info[uid]} ")
        answer = "您提供的信息我们已经记下来了，您接着说"
    else:
        answer = "目前暂无有的信息提供给您"
    logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
    return Response(answer, content_type=content_type, status=200)
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

@app.route('/door/srv', methods=['POST'])
def door_service():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "rag_index.html"
    serviceType = request.form.get("serviceType")
    customerName = request.form.get("customerName")
    contactNumber = request.form.get("contactNumber")
    address = request.form.get("address")
    preferredDate = request.form.get("preferredDate")
    preferredTime = request.form.get("preferredTime")
    problemDescription = request.form.get("problemDescription")
    content = (f"<div>[1]服务类型:{serviceType}</div><div>[2]客户姓名:{customerName}</div>"
               f"<div>[3]客户电话:{contactNumber}</div>"
               f"<div>[4]客户地址:{address}</div><div>[5]期望时间:{preferredDate} {preferredTime}</div>"
               f"<div>[6]问题描述:{problemDescription}</div>")
    logger.debug(f"request.form: {content}")
    content_type = 'text/html; charset=utf-8'
    answer = f"{content}<div>感谢您提供以上详细信息，我们将尽快安排工作人员上门为您提供服务</div>"
    return Response(answer, content_type=content_type, status=200)



if __name__ == '__main__':
    # test_req()
    app.run(host='0.0.0.0', port=19000)
