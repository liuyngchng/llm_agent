#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""
import json
import logging.config
import os
import re

from flask import (Flask, request, Response,
                   send_from_directory, abort, make_response, redirect, url_for)
from cfg_util import get_user_role_by_uid
from csm_service import CsmService
from bp_auth import auth_bp
from my_enums import ActorRole, AI_SERVICE_STATUS, AppType
from agt_util import classify_msg
from sys_init import init_yml_cfg
from utils import get_console_arg1

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
csm_svc = CsmService()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=AppType.CSM.name.lower()))

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
    answer = csm_svc.rcv_mail(uid)
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
    if uid == csm_svc.get_human_being_uid():
        answer= csm_svc.process_human_service_msg(msg, uid)
        return Response(answer, content_type=content_type, status=200)
    # if not in AI service mode , customer user msg should be sent to human being who provide service directly
    if usr_role == ActorRole.HUMAN_CUSTOMER.value \
        and csm_svc.get_ai_service_status_dict().get(uid) == AI_SERVICE_STATUS.ClOSE.value:
        csm_svc.snd_mail(csm_svc.get_human_being_uid(), f"[用户{csm_svc.get_human_customer_service_target_uid()}]{msg}")
        logger.info(f"snd_mail to msg_from_uid {csm_svc.get_human_being_uid()}, {msg}")
        return Response("", content_type=content_type, status=200)

    csm_svc.refresh_msg_history(msg, "用户")
    labels = json.loads(csm_svc.get_const_dict().get("classify_label"))

    classify_results = classify_msg(labels, msg, my_cfg, True)
    logger.info(f"classify_result: {classify_results}")

    csm_svc.refresh_session_info(msg, uid, my_cfg)
    answer = ""
    for classify_result in  classify_results:
        if labels[1] in classify_result:
            content_type = 'text/html; charset=utf-8'
            answer = csm_svc.process_door_to_door_service(uid, labels[1], my_cfg)
            response = make_response(answer)
            response.headers['Content-Type'] = content_type
            response.status_code = 200
            return response
         # for online pay service
        if labels[0] in classify_result:
            answer = csm_svc.process_online_pay_service(answer, labels[0])
        # for submit personal information
        elif labels[2] in classify_result:
            answer = csm_svc.process_personal_info_msg(answer, labels[2], uid)
        # for information retrieval
        elif labels[3] in classify_result:
            answer = csm_svc.retrieval_data(answer, labels[3], msg, uid, my_cfg)
        # for redirect to human talk
        elif labels[4] in classify_result:
            answer = csm_svc.talk_with_human(answer, labels, uid, my_cfg)
        # for other labels
        else:
            answer += csm_svc.get_const_dict().get("label5")
            logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
            csm_svc.refresh_msg_history(answer)
    return Response(answer, content_type=content_type, status=200)


if __name__ == '__main__':
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)