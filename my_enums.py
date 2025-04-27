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

if __name__ == "__main__":
    print(MsgType.ERROR.value)