#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
包含一定业务逻辑的客服系统
pip install flask

"""
import json
import logging.config
import os
import re
from datetime import datetime

from flask import (Flask, request, Response,
                   send_from_directory, abort, make_response, redirect, url_for, jsonify)
from common.cfg_util import get_user_role_by_uid
from apps.csm.csm_service import CsmService
from common.bp_auth import auth_bp
from common.my_enums import ActorRole, AiServiceStatus, AppType
from common.agt_util import classify_msg
from common.sys_init import init_yml_cfg
from common.cm_utils import get_console_arg1

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

my_cfg = init_yml_cfg()
app = Flask(__name__, static_folder=None)
app.register_blueprint(auth_bp)
app.config['JSON_AS_ASCII'] = False
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = AppType.CSM.name.lower()

os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
csm_svc = CsmService()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=AppType.CSM.name.lower()))

@app.route('/static/<path:file_name>')
def get_static_file(file_name):
    static_dirs = [
        os.path.join(os.path.dirname(__file__), '../../common/static'),
        os.path.join(os.path.dirname(__file__), 'static'),
    ]

    for static_dir in static_dirs:
        if os.path.exists(os.path.join(static_dir, file_name)):
            # logger.debug(f"get_static_file, {static_dir}, {file_name}")
            return send_from_directory(static_dir, file_name)
    logger.error(f"no_file_found_error, {file_name}")
    abort(404)

@app.route('/webfonts/<path:file_name>')
def get_webfonts_file(file_name):
    font_file_name = f"webfonts/{file_name}"
    return get_static_file(font_file_name)

@app.route('/msg/box/<uid>', methods=['GET'])
def get_msg(uid):
    """
    返回 msg box 中的消息
    """
    content_type = 'text/markdown; charset=utf-8'
    if not uid:
        logger.error("illegal_uid")
        return Response("", content_type=content_type, status=502)

    try:
        uid_int = int(uid)
    except (ValueError, TypeError):
        logger.error(f"非法uid格式: {uid}")
        return Response("", content_type=content_type, status=400)

    answer = csm_svc.rcv_mail(uid_int)
    # logger.info(f"rcv_mail for {uid_int}, {answer}")
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
    try:
        uid = int(request.form.get('uid'))
    except (ValueError, TypeError):
        logger.error(f"非法uid格式: {request.form.get('uid')}")
        return Response("用户ID格式错误", content_type='text/markdown; charset=utf-8', status=400)
    logger.info(f"rcv_msg from uid {uid} (type: {type(uid)}): {msg}")
    content_type = 'text/markdown; charset=utf-8'
    usr_role = get_user_role_by_uid(uid)
    # human being customer service msg should be sent to the customer directly
    # no AI interfere
    if uid == csm_svc.get_human_being_uid():
        answer= csm_svc.process_human_service_msg(msg, uid)
        return Response(answer, content_type=content_type, status=200)
    # if not in AI service mode , customer user msg should be sent to human being who provide service directly
    if usr_role == ActorRole.HUMAN_CUSTOMER.value \
        and csm_svc.get_ai_service_status_dict().get(uid) == AiServiceStatus.ClOSE.value:
        csm_svc.snd_mail(csm_svc.get_human_being_uid(), f"[用户{csm_svc.get_human_customer_service_target_uid()}]{msg}")
        logger.info(f"snd_mail to msg_from_uid {csm_svc.get_human_being_uid()}, {msg}")
        return Response("", content_type=content_type, status=200)

    csm_svc.refresh_msg_history(msg, "用户")
    labels = json.loads(csm_svc.get_const_dict().get("classify_label"))

    classify_results = classify_msg(labels, msg, my_cfg)
    logger.info(f"classify_result: {classify_results}")

    csm_svc.refresh_session_info(msg, uid, my_cfg)
    answer = ""
    for classify_result in  classify_results:
        if labels[1] in classify_result:
            logger.info("process_door_to_door_service")
            content_type = 'text/html; charset=utf-8'
            answer = csm_svc.process_door_to_door_service(uid, labels[1], my_cfg)
            response = make_response(answer)
            response.headers['Content-Type'] = content_type
            response.status_code = 200
            return response
         # for online pay service
        if labels[0] in classify_result:
            logger.info("process_online_pay_service")
            answer = csm_svc.process_online_pay_service(answer, labels[0])
        # for submit personal information
        elif labels[2] in classify_result:
            logger.info("process_personal_info_msg")
            answer = csm_svc.process_personal_info_msg(answer, labels[2], uid)
        # for information retrieval
        elif labels[3] in classify_result:
            logger.info("retrieval_data")
            answer = csm_svc.retrieval_data(answer, labels[3], msg, uid, my_cfg)
        # for redirect to human talk
        elif labels[4] in classify_result:
            logger.info("talk_with_human")
            answer = csm_svc.talk_with_human(answer, labels, uid, my_cfg)
        # for other labels
        else:
            answer += csm_svc.get_const_dict().get("label5")
            logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
            csm_svc.refresh_msg_history(answer)
    return Response(answer, content_type=content_type, status=200)


@app.route('/door/srv', methods=['POST'])
def submit_door_service():
    """
    处理上门服务预约表单提交
    """
    try:
        # 获取表单数据
        data = request.get_json() if request.is_json else request.form
        logger.info(f"收到上门服务预约请求: {data}")

        # 提取字段
        service_type = data.get('serviceType', '').strip()
        customer_name = data.get('customerName', '').strip()
        contact_number = data.get('contactNumber', '').strip()
        address = data.get('address', '').strip()
        preferred_date = data.get('preferredDate', '').strip()
        preferred_time = data.get('preferredTime', '').strip()
        problem_description = data.get('problemDescription', '').strip()
        customer_type = data.get('customerType', '居民客户').strip()
        additional_notes = data.get('additionalNotes', '').strip()

        # 验证必填字段
        if not all([service_type, customer_name, contact_number, address, preferred_date, problem_description]):
            return jsonify({
                'success': False,
                'message': '请填写所有必填字段'
            }), 400

        # 验证电话号码格式
        if not re.match(r'^1[3-9]\d{9}$', contact_number):
            return jsonify({
                'success': False,
                'message': '请输入正确的手机号码'
            }), 400

        # 验证日期格式
        try:
            preferred_date_obj = datetime.strptime(preferred_date, '%Y-%m-%d')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if preferred_date_obj < today:
                return jsonify({
                    'success': False,
                    'message': '预约日期不能是过去的时间'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'message': '日期格式不正确'
            }), 400

        # 获取用户ID（如果有的话）
        uid = data.get('uid')
        if uid:
            try:
                uid = int(uid)
            except (ValueError, TypeError):
                uid = None

        # 调用CSM服务处理预约
        result = csm_svc.process_door_service_appointment(
            uid=uid,
            service_type=service_type,
            customer_name=customer_name,
            contact_number=contact_number,
            address=address,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            problem_description=problem_description,
            customer_type=customer_type,
            additional_notes=additional_notes
        )

        if result.get('success'):
            # 如果用户在线，可以发送确认消息
            if uid:
                confirm_msg = f"您的上门服务预约已提交成功！\n\n预约信息：\n- 服务类型：{service_type}\n- 预约时间：{preferred_date} {preferred_time if preferred_time else '任意时间'}\n- 服务地址：{address}\n\n我们将尽快安排工作人员与您联系。"
                csm_svc.snd_mail(uid, confirm_msg)

            return jsonify({
                'success': True,
                'message': '预约成功，我们将尽快为您安排服务',
                'appointment_id': result.get('appointment_id')
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', '预约失败，请稍后重试')
            }), 500

    except Exception as e:
        logger.error(f"上门服务预约处理失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': '系统错误，请稍后重试'
        }), 500

if __name__ == '__main__':
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)