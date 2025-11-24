#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
通用枚举类
"""
from enum import Enum

class DBType(Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"
    ORACLE = "oracle"
    DORIS = "doris"
    DM8 = "dm"

class YieldType(Enum):
    TXT = "txt"
    HTML = "html"
    CHART_JS = "chart_js"
    # {"data_type": "msg", "data": {"cur_page":1, "total_page":1}}
    MSG = "msg"

class DataType(Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"

class MsgType(Enum):
    """
    消息类型枚举
    """
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    MSG = "msg"
    WARN = "warn"

class WriteDocType(Enum):
    """文档类型枚举（英文键，汉字值）"""
    MEETING_REPORT = "会议纪要"
    REVIEW_REPORT = "评审报告"
    STANDARD = "国家标准(GB/(GB/T))"
    PROPOSAL = "项目计划书"
    YEAR_SUMMARY = "年度工作总结"
    RESEARCH = "可行性研究报告"
    MARKETING = "营销策划方案"
    DETAILED_DESIGN_DOCUMENT = "详细设计文档"
    PRELIMINARY_DESIGN_DOCUMENT = "概要设计文档"
    SOFTWARE_COPYRIGHT_REG = "软件著作权申报"

    @staticmethod
    def get_doc_type_desc(input_str: str) -> str:
        """根据输入字符串获取对应的文档类型"""
        input_upper = input_str.upper()  # 转换为大写匹配枚举键
        try:
            return WriteDocType[input_upper].value
        except KeyError:
            return None  # 或抛出异常


class AppType(Enum):
    """应用类型枚举（英文键，汉字值）"""
    CHAT = "智能问答"
    NL2SQL = "智能问数 "
    DOCX = "文档生成"
    PPTX = "PPT 校对"
    CSM = "智能客服"
    ORD_GEN = "订单生成"
    CHAT2DB = "智能问数"
    OPEN = "开放平台"
    MT_REPORT = "会议纪要整理"
    EVAL_EXPERT = "AI 评审数字专家"
    PAPER_REVIEW = "AI 数字评委"
    TEAM_BUILDING = "AI 党建"

    @staticmethod
    def get_app_list() -> list:
        """获取应用类型列表"""
        return [{"name":app_type.name, "value":app_type.value} for app_type in AppType]

    @staticmethod
    def get_app_type(app_str: str) -> str:
        """根据输入字符串获取对应的应用类型"""
        app_upper = app_str.upper()  # 转换为大写匹配枚举键
        try:
            return AppType[app_upper].value
        except KeyError:
            return "AI 应用"  # 或抛出异常

class ActorRole(Enum):
    """
    the role of actor engaged in system
    for database cfg.db.user.role
    """
    HUMAN_CUSTOMER          = 0      # human being customer of the system
    HUMAN_SERVICE_PROVIDER  = 1      # human being who provide customer service to consumer
    AI_SERVICE_PROVIDER     = 2      # an AI role in system, such as LLM, etc.


class AiServiceStatus(Enum):
    """
    the status of AI service provided to human customers
    """
    OPEN    = 1
    ClOSE   = 0

class Const(Enum):
    """
    the status of AI service provided to human customers
    """
    BILL_ADDR_SVG   = "bill_addr_svg"
    CSM_SERVICE     = "csm_service"

class FileType(Enum):
    DOCX = 0
    XLSX = 1
    MARKDOWN = 2



if __name__ == "__main__":
    a = FileType.DOCX.value
    print(f"a = {a}")

    print(MsgType.ERROR.value)
    dt_type = "chart_js"
    if dt_type in (YieldType.CHART_JS.value, YieldType.MSG.value):
        print("dt_type matched")