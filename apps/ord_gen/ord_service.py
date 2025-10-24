#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
a customer service module to process AI and human talk msg
"""
import json
import logging.config

from flask import render_template

from common.agt_util import update_session_info, get_abs_of_chat, extract_lpg_order_info, fill_dict
from common.cfg_util import get_consts
from datetime import datetime

from common.my_enums import AiServiceStatus
from common.cm_utils import convert_list_to_html_table

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

MAX_HISTORY_SIZE = 19

class OrderService:
    """
    A customer service
    """
    def __init__(self):
        self.human_customer_service_target_uid = "332987902"
        self.human_being_uid = "332987905"
        self.mail_outbox_list = {
            self.human_customer_service_target_uid: [],
            self.human_being_uid: []
        }
        self.session_info = {}
        self.ai_service_status = {}

        # TODO: to limit the size of history to the maximum token size of LLM
        # limit msg_history size to MAX_MSG_COUNT
        self.msg_history = []
        self.const_dict = get_consts('ord_gen')
        logger.info(f"const: {self.const_dict}")


    def get_const_dict(self) -> dict:
        return self.const_dict


    def get_human_being_uid(self) -> str:
        return self.human_being_uid


    def get_human_customer_service_target_uid(self) -> str:
        return self.human_customer_service_target_uid


    def get_ai_service_status_dict(self) -> dict:
        return self.ai_service_status


    def get_msg_history_list(self) -> list:
        return self.msg_history


    def get_session_info_dict(self) -> dict:
        return self.session_info


    def get_mail_outbox_list(self) -> dict:
        return self.mail_outbox_list


    def rcv_mail(self, uid: str) -> str:
        """
        :param uid: receive the oldest mail for user msg_from_uid
        """
        my_msg_outbox = self.mail_outbox_list.get(uid)
        mail = ""
        if my_msg_outbox:
            mail = my_msg_outbox.pop(0)
        return mail


    def snd_mail(self, to_uid: str, msg: str) -> None:
        """
        :param to_uid: mail receiver
        :param msg: the mail txt need to be sent
        """
        target_msg_outbox = self.mail_outbox_list.get(to_uid, [])
        target_msg_outbox.append(msg)
        logger.info(f"mail_outbox_list.get({to_uid}): {self.mail_outbox_list.get(to_uid)}")


    def refresh_msg_history(self , msg: str, msg_type="机器人"):
        """
        customer user msg should be in context any way, for be used in AI context later
        :param msg: user's msg be sent to system
        :param msg_type: which kind msg it is , like user's msg(inbound), AI generated msg(outbound)
        """
        now = datetime.now()
        usr_msg_list = self.get_msg_history_list()
        no =len(usr_msg_list)
        if no > MAX_HISTORY_SIZE:
            first_msg = usr_msg_list.pop(0)
            no += first_msg.get("编号")
        usr_msg_list.append(
            {
                "编号": no,
                "消息": msg,
                "发送者": msg_type,
                "时间": now.strftime('%Y-%m-%d %H:%M:%S')
            }
        )
        logger.debug("msg_history_refreshed:\n%s", '\n'.join(map(str, usr_msg_list)))


    def process_personal_info_msg(self, answer: str, label: str, uid: str):
        logger.info(f"session_dict[{uid}] = {self.get_session_info_dict().get(uid)} ")
        answer += self.get_const_dict().get("label2")
        logger.info(f"answer_for_classify {label}:\n{answer}")
        self.refresh_msg_history(answer)
        return answer


    def process_online_pay_service(self, answer: str, label: str):
        # answer = search(msg, my_cfg, True)
        txt = self.get_const_dict().get("label0")
        bill_addr = self.get_const_dict().get("bill_addr_svg")
        answer += f'''{txt}<div style="width: 100px; height: 100px; overflow: hidden">{bill_addr}</div>'''
        logger.info(f"answer_for_classify {label}:\n{txt}")
        self.refresh_msg_history(txt)
        return answer


    def refresh_lpg_order_info(self, msg: str, msg_uid: str, sys_cfg: dict):
        """
        extract important entity from msg, and update the global info session info
        :param msg: msg which user send to system
        :param msg_uid: the uid represent who send the msg to system
        :param sys_cfg: the system config information
        """
        s_info = extract_lpg_order_info(msg, sys_cfg)
        if not s_info:
            return
        if msg_uid not in self.get_session_info_dict():
            logger.info(f"{msg_uid} uid_not_in_session_dict {self.get_session_info_dict()}")
            self.get_session_info_dict()[msg_uid] = s_info
        else:
            self.get_session_info_dict()[msg_uid] = update_session_info(
                self.get_session_info_dict()[msg_uid],
                s_info,
                sys_cfg
            )


    def process_human_service_msg(self, msg: str, msg_from_uid: int) -> str:
        """
        for human provided customer service instead of AI
            (1) send human made msg directly to customer
            (2) when service finished , switch service provider to AI
        :param msg: the msg sent by human customer service provider, which would be sent to customer
        :param msg_from_uid: the uid from which the msg sent
        """
        if self.get_const_dict().get("str2") in msg.upper():
            logger.info(f"switch_service_provider_to_AI_for_uid {self.get_human_customer_service_target_uid()}")
            self.get_ai_service_status_dict()[self.get_human_customer_service_target_uid()] = AiServiceStatus.OPEN
            answer = self.get_const_dict().get("str3")
        else:
            logger.info(f"snd_msg_to_customer_directly, "
                        f"from {msg_from_uid}, to {self.get_human_customer_service_target_uid()}, msg {msg}")
            self.snd_mail(self.get_human_customer_service_target_uid(), f"[人工客服]{msg}")
            logger.info(f"msg_outbox_list: {self.get_mail_outbox_list()}")
            answer = f"消息已经发至用户[{self.get_human_customer_service_target_uid()}]"
        return answer

    def auto_fill_lpg_order_info(self, uid: str, classify_label: str, sys_cfg: dict) -> str:
        """
        :param uid: user id of whom ask for door service
        :param classify_label: the service type label
        :param sys_cfg: the system configuration dict
        """
        user_dict = json.loads(self.get_const_dict().get("label1"))
        # mock get user info from user info in db
        user_dict["uid"] = uid
        user_dict["客户姓名"] = "张三"
        user_dict["联系电话"] = "13022345678"
        user_dict["客户类型"] = "非居民用户"

        if uid in self.get_session_info_dict() and self.get_session_info_dict()[uid]:
            user_dict = fill_dict(self.get_session_info_dict()[uid], user_dict, sys_cfg)
            logger.info(f"order_info_auto_filled_in for {classify_label}")
            if not user_dict["配送地址"]:
                user_dict["配送地址"] = "广西南宁市青秀区民族大道100号右转100米xxxx大院3号楼底商xxxx大排档"
            if not user_dict["期望送达时间"]:
                user_dict["期望送达时间"] = "2小时内"
        else:
            logger.info(f"{uid},current_id_not_in_person_info, {self.get_session_info_dict()}")
        self.refresh_msg_history(self.get_const_dict().get("label11"))
        logger.info(f"answer_for_classify {classify_label}:\nuser_dict: {user_dict}")
        result = render_template("order_info.html", **user_dict)
        return result


    def process_door_to_door_service(self, uid: str, classify_label: str, sys_cfg: dict) -> str:
        """
        :param uid: user id of whom ask for door service
        :param classify_label: the service type label
        :param sys_cfg: the system configuration dict
        """
        user_dict = json.loads(self.get_const_dict().get("label1"))
        if uid in self.get_session_info_dict() and self.get_session_info_dict()[uid]:
            user_dict = fill_dict(self.get_session_info_dict()[uid], user_dict, sys_cfg)
            logger.info(f"html_table_with_personal_info_filled_in for {classify_label}")
        else:
            logger.info(f"{uid},current_id_not_in_person_info, {self.get_session_info_dict()}")
        self.refresh_msg_history(self.get_const_dict().get("label11"))
        content_type = 'text/html; charset=utf-8'
        logger.info(f"answer_for_classify {classify_label}:\nuser_dict: {user_dict}")
        result = render_template("door_service.html", **user_dict)
        return result


    def retrieval_data(self, answer: str, label: str, msg: str, uid: str, sys_cfg: dict) -> str:
        """
        :param answer: the answer to user's question
        :param label: classify label for current question
        :param msg: user's question , or called msg.
        :param uid: the user which msg send from
        :param sys_cfg: the system config information
        """
        # sql_agent = SqlAgent(sys_cfg, uid,True, f"{self.get_const_dict().get('str1')} {uid}")
        # dt = sql_agent.get_dt_with_nl(
        #     uid,
        #     msg,
        #     DataType.JSON.value,
        # )
        # usr_dt_dict = dt
        # # usr_dt_desc = sql_agent.desc_usr_dt(msg, usr_dt_dict["raw_dt"][0])
        # answer += usr_dt_desc
        # # answer += const_dict.get("label3")
        # logger.info(f"answer_for_classify {label}:\n{answer}")
        # self.refresh_msg_history(answer)
        # return answer
        return ""


    def talk_with_human(self, answer: str, label: str, uid: str, sys_cfg: dict) -> str:
        """
        user asked for talking with human directly, send the user msg to human being in back end directly
        :param answer: the msg response to user's request
        :param label: classify label to user's question
        :param uid: the uid who sumit the question
        :param sys_cfg: system configuration
        """
        msg_boxing = self.get_const_dict().get("label4")
        msg_boxing += f"<br>\n{convert_list_to_html_table(self.get_msg_history_list())}"
        chat_abs = get_abs_of_chat(self.get_msg_history_list(), sys_cfg)
        msg_boxing += f"<br>{chat_abs}"
        logger.info(f"msg_boxing_for_classify_snd_to_human_being "
                    f"{self.get_human_being_uid()}, classify {label}:\n{msg_boxing}")
        self.snd_mail(self.get_human_being_uid(), msg_boxing)
        self.get_msg_history_list().clear()
        answer += self.get_const_dict().get("label41")
        self.get_ai_service_status_dict()[uid] = AiServiceStatus.ClOSE.value  # transform AI service to human service
        logger.info(f"answer_for_classify {label}:\n{answer}")
        return answer
