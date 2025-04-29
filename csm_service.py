#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
a customer service module to process AI and human talk msg
"""
import json
import logging.config

from flask import render_template

from agt_util import fill_dict, extract_session_info, update_session_info
from config_util import get_consts
from datetime import datetime

from my_enums import AI_SERVICE_STATUS

# {"uid_12345":["msg1", "msg2"], "uid_2345":["msg1", "msg2"],}
# msg_from_uid id is the msg receiver
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
logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

session_info = {}
ai_service_status = {}

# TODO: to limit the size of history to the maximum token size of LLM
msg_history = []

const_dict = {}

def init_customer_service():
    global const_dict
    const_dict = get_consts()

def get_const_dict()-> dict:
    return const_dict

def get_human_being_uid() -> str:
    return human_being_uid

def get_human_customer_service_target_uid() -> str:
    return human_customer_service_target_uid

def get_ai_service_status_dict() -> dict:
    return ai_service_status

def get_msg_history_list()-> list:
    return msg_history

def get_session_info_dict()-> dict:
    return session_info

def get_mail_outbox_list() -> dict:
    return mail_outbox_list

def rcv_mail(uid: str) -> str:
    """
    :param uid: receive the oldest mail for user msg_from_uid
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

def refresh_msg_history(msg: str, msg_type="机器人"):
    """
    customer user msg should be in context any way, for be used in AI context later
    :param msg: user's msg be sent to system
    :param msg_type: which kind msg it is , like user's msg(inbound), AI generated msg(outbound)
    """
    now = datetime.now()
    get_msg_history_list().append(
        {
            "编号": len(get_msg_history_list()),
            "消息": msg,
            "发送者": msg_type,
            "时间":  now.strftime('%Y-%m-%d %H:%M:%S')
        }
    )
    logger.debug("msg_history_refreshed:\n%s", '\n'.join(map(str, get_msg_history_list())))

def process_personal_info_msg(answer: str, label: str, uid: str):
    logger.info(f"session_dict[{uid}] = {get_session_info_dict().get(uid)} ")
    answer += get_const_dict().get("label2")
    logger.info(f"answer_for_classify {label}:\n{answer}")
    refresh_msg_history(answer)
    return answer


def process_online_pay_service(answer: str, label: str):
    # answer = search(msg, my_cfg, True)
    txt = get_const_dict().get("label0")
    bill_addr = get_const_dict().get("bill_addr_svg")
    answer += f'''{txt}<div style="width: 100px; height: 100px; overflow: hidden">{bill_addr}</div>'''
    logger.info(f"answer_for_classify {label}:\n{txt}")
    refresh_msg_history(txt)
    return answer

def refresh_session_info(msg: str, msg_uid: str, cfg: dict):
    """
    extract important entity from msg, and update the global info session info
    :param msg: msg which user send to system
    :param msg_uid: the uid represent who send the msg to system
    """
    s_info = extract_session_info(msg, cfg, True)
    if s_info:
        if msg_uid not in get_session_info_dict():
            logger.info(f"{msg_uid} uid_not_in_session_dict {get_session_info_dict()}")
            get_session_info_dict()[msg_uid] = s_info
        else:
            get_session_info_dict()[msg_uid] = update_session_info(
                get_session_info_dict()[msg_uid],
                s_info,
                cfg,
                True
            )


def process_human_service_msg(msg: str, msg_from_uid: str) -> str:
    """
    for human provided customer service instead of AI
        (1) send human made msg directly to customer
        (2) when service finished , switch service provider to AI
    """
    content_type = 'text/markdown; charset=utf-8'
    if get_const_dict().get("str2") in msg.upper():
        logger.info(f"switch_service_provider_to_AI_for_uid {get_human_customer_service_target_uid()}")
        get_ai_service_status_dict()[get_human_customer_service_target_uid()] = AI_SERVICE_STATUS.OPEN
        answer =get_const_dict().get("str3")
    else:
        logger.info(f"snd_msg_to_customer_directly, "
            f"from {msg_from_uid}, to {get_human_customer_service_target_uid()}, msg {msg}")
        snd_mail(get_human_customer_service_target_uid(), f"[人工客服]{msg}")
        logger.info(f"msg_outbox_list: {get_mail_outbox_list()}")
        answer = f"消息已经发至用户[{get_human_customer_service_target_uid()}]"
    return answer


def process_door_to_door_service(uid: str, classify_label: str) -> str:
    """
    :param uid: user id of whom ask for door service
    :param classify_label: the service type label
    """
    user_dict = json.loads(get_const_dict().get("label1"))
    if uid in get_session_info_dict() and get_session_info_dict()[uid]:
        user_dict = fill_dict(get_session_info_dict()[uid], user_dict, my_cfg, True)
        logger.info(f"html_table_with_personal_info_filled_in for {classify_label}")
    else:
        logger.info(f"{uid},current_id_not_in_person_info, {get_session_info_dict()}")
    refresh_msg_history(get_const_dict().get("label11"))
    content_type = 'text/html; charset=utf-8'
    logger.info(f"answer_for_classify {classify_label}:\nuser_dict: {user_dict}")
    result = render_template("door_service.html", **user_dict)
    return result
