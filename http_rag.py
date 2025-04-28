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
from config_util import auth_user, get_consts, get_user_sample_data_rd_cfg_dict
from my_enums import DataType
from semantic_search import search
from agt_util import (classify_msg, fill_dict, update_session_info,
                      extract_session_info, get_abs_of_chat)
from sys_init import init_yml_cfg
from utils import convert_list_to_html_table
from datetime import datetime
from sql_agent import get_dt_with_nl, desc_usr_dt


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
session_info = {}

# {"uid_12345":["msg1", "msg2"], "uid_2345":["msg1", "msg2"],}
# uid id is the msg receiver
human_customer_service_target_uid = "332987916"
human_being_uid = "332987919"
# mail_outbox_list = {
#     human_customer_service_target_uid:["这是一条人工客服发送的测试消息,需要发送给 332987916"],
#     human_being_uid:["这是一条用户需要转人工客服的测试消息，需要发送给人工客服"]
# }
mail_outbox_list = {
    human_customer_service_target_uid:[],
    human_being_uid:[]
}
const_dict = get_consts()

ai_service_status = {}


# TODO: to limit the size of history to the maximum token size of LLM
msg_history = []

def rcv_mail(uid: str) -> str:
    """
    :param uid: receive the oldest mail for user uid
    """
    my_msg_outbox = mail_outbox_list.get(uid)
    mail = ""
    if my_msg_outbox:
        mail = my_msg_outbox.pop(0)
    return mail

def snd_mail(to_uid: str, msg: str)-> None:
    """
    :param to_uid: mail receiver
    :param msg: the mail txt need to be sent
    """
    target_msg_outbox = mail_outbox_list.get(to_uid, [])
    target_msg_outbox.append(msg)
    logger.info(f"mail_outbox_list.get({to_uid}): {mail_outbox_list.get(to_uid)}")


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
    answer = rcv_mail(uid)
    return Response(answer, content_type=content_type, status=200)


@app.route('/usr/ask', methods=['POST'])
def submit():
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
    if uid == human_being_uid:
        logger.info(f"rcv_msg_from_human_being_need_route_to_customer_directly, "
                    f"from {uid}, to {human_customer_service_target_uid}, msg {msg}")
        snd_mail(human_customer_service_target_uid, msg)
        logger.info(f"msg_outbox_list: {mail_outbox_list}")
        answer = f"消息已经发送至用户 {human_customer_service_target_uid}， 等待用户回答"
        return Response(answer, content_type=content_type, status=200)
    else:
        refresh_msg_history(msg, "用户")
    logger.debug("msg_history:\n%s", '\n'.join(map(str, msg_history)))
    labels = json.loads(const_dict.get("classify_label"))
    classify_results = classify_msg(labels, msg, my_cfg, True)
    logger.info(f"classify_result: {classify_results}")

    s_info = extract_session_info(msg, my_cfg, True)
    if s_info:
        if uid not in session_info:
            logger.info(f"{uid} uid_not_in_session_dict {session_info}")
            session_info[uid] = s_info
        else:
            session_info[uid] = update_session_info(session_info[uid], s_info, my_cfg, True)
    answer = ""
    for classify_result in  classify_results:
        # for to door service
        if labels[1] in classify_result:
            user_dict = json.loads(const_dict.get("label1"))
            if uid in session_info and session_info[uid]:
                user_dict = fill_dict(session_info[uid], user_dict, my_cfg, True)
                logger.info(f"html_table_with_personal_info_filled_in for {labels[1]}")
            else:
                logger.info(f"{uid},current_id_not_in_person_info, {session_info}")
            refresh_msg_history(const_dict.get("label11"))
            content_type = 'text/html; charset=utf-8'
            logger.info(f"answer_for_classify {labels[1]}:\nuser_dict: {user_dict}")
            response = make_response(render_template("door_service.html", **user_dict))
            response.headers['Content-Type'] = content_type
            response.status_code = 200
            return response
         # for online pay service
        if labels[0] in classify_result:
            # answer = search(msg, my_cfg, True)
            txt = const_dict.get("label0")
            bill_addr = const_dict.get("bill_addr_svg")
            answer += f'''{txt}<div style="width: 100px; height: 100px; overflow: hidden">{bill_addr}</div>'''
            logger.info(f"answer_for_classify {labels[0]}:\n{txt}")
            refresh_msg_history(txt)
        # for submit personal information
        elif labels[2] in classify_result:
            logger.info(f"session_dict[{uid}] = {session_info[uid]} ")
            answer += const_dict.get("label2")
            logger.info(f"answer_for_classify {labels[2]}:\n{answer}")
            refresh_msg_history(answer)
        # for information retrieval
        elif labels[3] in classify_result:
            dt = get_dt_with_nl(msg,
                my_cfg,
                DataType.JSON.value,
                True,
                f"{const_dict.get("str1")} {uid}"
            )
            usr_dt_dict = json.loads(dt)
            usr_dt_desc = desc_usr_dt(msg, my_cfg, True, usr_dt_dict["raw_dt"][0])
            answer += usr_dt_desc
            # answer += const_dict.get("label3")
            logger.info(f"answer_for_classify {labels[3]}:\n{answer}")
            refresh_msg_history(answer)
        # for redirect to human talk
        elif labels[4] in classify_result:
            msg_boxing = const_dict.get("label4")
            msg_boxing += f"<br>\n{convert_list_to_html_table(msg_history)}"
            chat_abs = get_abs_of_chat(msg_history, my_cfg, True)
            msg_boxing += f"<br>{chat_abs}"
            logger.info(f"msg_boxing_for_classify_snd_to_human_being {human_being_uid}, classify {labels[4]}:\n{msg_boxing}")
            snd_mail(human_being_uid, msg_boxing)
            msg_history.clear()
            answer = const_dict.get("label41")
            logger.info(f"answer_for_classify {labels[4]}:\n{answer}")
        # for other labels
        else:
            answer += const_dict.get("label5")
            logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
            refresh_msg_history(answer)
    return Response(answer, content_type=content_type, status=200)


@app.route('/door/srv', methods=['POST'])
def door_service():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
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
    ask the LLM for some private msg not public to outside,
    let LLM retrieve the information from local vector database,
    and the output the answer.
    """
    logger.info(f"config {my_cfg}")
    my_question = "查下我的余额度？"
    logger.info(f"invoke msg: {my_question}")
    answer = search(my_question, my_cfg, True)
    logger.info(f"answer is \r\n{answer}")

def refresh_msg_history(msg: str, msg_type="机器人"):
    now = datetime.now()
    msg_history.append(
        {
            "编号": len(msg_history),
            "消息": msg,
            "发送者": msg_type,
            "时间":  now.strftime('%Y-%m-%d %H:%M:%S')
        }
    )

if __name__ == '__main__':
    # test_req()
    app.run(host='0.0.0.0', port=19000)