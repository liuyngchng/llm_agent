#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
订单自动生成
pip install flask

"""
import json
import logging.config
import os

from flask import (Flask, request, Response, make_response, redirect, url_for)
from common.cfg_util import get_user_role_by_uid
from common.bp_auth import auth_bp
from common.my_enums import ActorRole, AiServiceStatus, AppType
from common.agt_util import classify_msg
from common.sys_init import init_yml_cfg
from common.cm_utils import get_console_arg1
from ord_service import OrderService

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
ord_svc = OrderService()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=AppType.ORD_GEN.name.lower()))


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
    answer = ord_svc.rcv_mail(uid)
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
    uid = int(request.form.get('uid'))
    logger.info(f"rcv_msg: {msg}")
    content_type = 'text/html; charset=utf-8'
    usr_role = get_user_role_by_uid(uid)
    # human being customer service msg should be sent to the customer directly
    # no AI interfere
    if uid == ord_svc.get_human_being_uid():
        answer= ord_svc.process_human_service_msg(msg, uid)
        return Response(answer, content_type=content_type, status=200)
    # if not in AI service mode , customer user msg should be sent to human being who provide service directly
    if usr_role == ActorRole.HUMAN_CUSTOMER.value \
        and ord_svc.get_ai_service_status_dict().get(uid) == AiServiceStatus.ClOSE.value:
        ord_svc.snd_mail(ord_svc.get_human_being_uid(), f"[用户{ord_svc.get_human_customer_service_target_uid()}]{msg}")
        logger.info(f"snd_mail to msg_from_uid {ord_svc.get_human_being_uid()}, {msg}")
        return Response("", content_type=content_type, status=200)

    ord_svc.refresh_msg_history(msg, "用户")

    labels = json.loads(ord_svc.get_const_dict().get("classify_label"))

    classify_results = classify_msg(labels, msg, my_cfg)
    logger.info(f"classify_result: {classify_results}")

    ord_svc.refresh_lpg_order_info(msg, uid, my_cfg)
    answer = ""
    for classify_result in  classify_results:
        if labels[1] in str(classify_result):
            logger.info("a_door_to_door_service_info")
            content_type = 'text/html; charset=utf-8'
            answer = ord_svc.process_door_to_door_service(uid, labels[1], my_cfg)
            response = make_response(answer)
            response.headers['Content-Type'] = content_type
            response.status_code = 200
            return response
         # for online pay service
        if labels[0] in str(classify_result):
            logger.info("a_online_pay_info")
            ord_svc.process_online_pay_service(answer, labels[0])
            answer = ord_svc.auto_fill_lpg_order_info(uid, labels[0], my_cfg)
            response = make_response(answer)
            logger.info(f"answer_for_online_pay_info :\n{answer}")
            response.headers['Content-Type'] = content_type
            response.status_code = 200
            return response
        # for information retrieval
        elif labels[2] in str(classify_result):
            logger.info("a_retrieval_data_info")
            answer = ord_svc.retrieval_data(answer, labels[3], msg, uid, my_cfg)
        # for redirect to human talk
        elif labels[3] in str(classify_result):
            logger.info("a_talk_to_human_info")
            answer = ord_svc.talk_with_human(answer, labels, uid, my_cfg)
        # for other labels
        else:
            answer += ord_svc.get_const_dict().get("label5")
            logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
            ord_svc.refresh_msg_history(answer)
    return Response(answer, content_type=content_type, status=200)


if __name__ == '__main__':
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)