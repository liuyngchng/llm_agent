#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum

class DBType(Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"
    ORACLE = "oracle"

class DataType(Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"

class MsgType(Enum):
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    MSG = "msg"
    WARN = "warn"

class ActorRole(Enum):
    """
    the role of actor engaged in system
    for database config.db.user.role
    """
    HUMAN_CUSTOMER = 0      # human being customer of the system
    HUMAN_SERVICE = 1       # human being who provide customer service to consumer
    AI_MACHINE_SERVICE = 2          # an AI role in system, such as LLM, etc.


class AI_SERVICE_STATUS(Enum):
    """
    the status of AI service provided to human customers
    """
    OPEN = 1
    ClOSE = 0


if __name__ == "__main__":
    print(MsgType.ERROR.value)