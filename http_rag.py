#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""
import json
import logging.config
import os
import re

from flask import (Flask, request, jsonify, render_template, Response,
                   send_from_directory, abort, make_response)
from config_util import auth_user, get_user_role_by_uid
from csm_service import rcv_mail, get_human_being_uid, get_ai_service_status_dict, snd_mail, \
    get_human_customer_service_target_uid, get_const_dict, \
    refresh_msg_history, refresh_session_info, process_door_to_door_service, \
    process_online_pay_service, process_personal_info_msg, process_human_service_msg, retrieval_data, \
    init_customer_service, talk_with_human
from my_enums import ActorRole, AI_SERVICE_STATUS
from agt_util import classify_msg
from sys_init import init_yml_cfg


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)


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
    curl -s --noproxy '*' -X POST 'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "rag_index.html"
    logger.debug(f"request.form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user login: {user}, {t}")
    auth_result = auth_user(user, t, my_cfg)
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
        ctx = {
            "uid": auth_result["uid"],
            "sys_name": my_cfg['sys']['name'],
            "role": auth_result["role"],
            "t": auth_result["t"],
        }
        return render_template(dt_idx, **ctx)


@app.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' \
        -H "Content-Type: application/json" \
        -d '{"msg":"who are you?"}'
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

@app.route('/msg/box/<uid>', methods=['GET'])
def get_msg(uid):
    """
    返回 msg box 中的消息
    """
    content_type = 'text/markdown; charset=utf-8'
    if not uid:
        logger.error("illegal_uid")
        return Response("", content_type=content_type, status=502)
    # logger.info(f"rcv_mail for {uid}")
    answer = rcv_mail(uid)
    return Response(answer, content_type=content_type, status=200)


@app.route('/usr/ask', methods=['POST'])
def submit_user_question():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST 'http://127.0.0.1:19000/usr/ask' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg')
    uid = request.form.get('uid')
    logger.info(f"rcv_msg: {msg}")
    content_type = 'text/markdown; charset=utf-8'
    usr_role = get_user_role_by_uid(uid)
    # human being customer service msg should be sent to the customer directly
    # no AI interfere
    if uid == get_human_being_uid():
        answer= process_human_service_msg(msg, uid)
        return Response(answer, content_type=content_type, status=200)
    # if not in AI service mode , customer user msg should be sent to human being who provide service directly
    if usr_role == ActorRole.HUMAN_CUSTOMER.value \
        and get_ai_service_status_dict().get(uid) == AI_SERVICE_STATUS.ClOSE.value:
        snd_mail(get_human_being_uid(), f"[用户{get_human_customer_service_target_uid()}]{msg}")
        logger.info(f"snd_mail to msg_from_uid {get_human_being_uid()}, {msg}")
        return Response("", content_type=content_type, status=200)

    refresh_msg_history(msg, "用户")
    labels = json.loads(get_const_dict().get("classify_label"))

    classify_results = classify_msg(labels, msg, my_cfg, True)
    logger.info(f"classify_result: {classify_results}")

    refresh_session_info(msg, uid, my_cfg)
    answer = ""
    for classify_result in  classify_results:
        if labels[1] in classify_result:
            content_type = 'text/html; charset=utf-8'
            answer = process_door_to_door_service(uid, labels[1], my_cfg)
            response = make_response(answer)
            response.headers['Content-Type'] = content_type
            response.status_code = 200
            return response
         # for online pay service
        if labels[0] in classify_result:
            answer = process_online_pay_service(answer, labels[0])
        # for submit personal information
        elif labels[2] in classify_result:
            answer = process_personal_info_msg(answer, labels[2], uid)
        # for information retrieval
        elif labels[3] in classify_result:
            answer = retrieval_data(answer, labels[3], msg, uid, my_cfg)
        # for redirect to human talk
        elif labels[4] in classify_result:
            answer = talk_with_human(answer, labels, uid, my_cfg)
        # for other labels
        else:
            answer += get_const_dict().get("label5")
            logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
            refresh_msg_history(answer)
    return Response(answer, content_type=content_type, status=200)


if __name__ == '__main__':
    init_customer_service()
    app.run(host='0.0.0.0', port=19000)