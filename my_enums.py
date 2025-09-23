#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.


from enum import Enum

class DBType(Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"
    ORACLE = "oracle"
    DORIS = "doris"

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

class AppType(Enum):
    """应用类型枚举（英文键，汉字值）"""
    CHAT = "智能问答"
    NL2SQL = "智能问数 "
    DOCX = "文档生成"
    CSM = "智能客服"
    LPG = "液化气终端智能服务助手"
    TXT2SQL = "智能问数"
    OPEN = "开放平台"

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


class WriteDocType(Enum):
    """文档类型枚举（英文键，汉字值）"""
    REPORT = "工作报告"
    STANDARD = "国家标准(GB/(GB/T))"
    PROPOSAL = "项目计划书"
    YEAR_SUMMARY = "年度工作总结"
    RESEARCH = "可行性研究报告"
    MARKETING = "营销策划方案"
    DETAILED_DESIGN_DOCUMENT = "详细设计文档"
    PRELIMINARY_DESIGN_DOCUMENT = "概要设计文档"

    @staticmethod
    def get_doc_type_desc(input_str: str) -> str:
        """根据输入字符串获取对应的文档类型"""
        input_upper = input_str.upper()  # 转换为大写匹配枚举键
        try:
            return WriteDocType[input_upper].value
        except KeyError:
            return None  # 或抛出异常


class ActorRole(Enum):
    """
    the role of actor engaged in system
    for database cfg.db.user.role
    """
    HUMAN_CUSTOMER          = 0      # human being customer of the system
    HUMAN_SERVICE_PROVIDER  = 1      # human being who provide customer service to consumer
    AI_SERVICE_PROVIDER     = 2      # an AI role in system, such as LLM, etc.


class AI_SERVICE_STATUS(Enum):
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



if __name__ == "__main__":
    print(MsgType.ERROR.value)
    dt_type = "chart_js"
    if dt_type in (YieldType.CHART_JS.value, YieldType.MSG.value):
        print("dt_type matched")