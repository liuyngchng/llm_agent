#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import functools
import os
import sqlite3
import logging.config
from typing import Any

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

USER_SAMPLE_DATA_DB = "user_info.db"
AI_GEN_TAG="[_AI生成_]"

 # 这里可以根据实际部署情况进行数据库文件绝对路径的配置
CFG_DB_FILE = "cfg.db"
CFG_DB_URI=f"sqlite:///{CFG_DB_FILE}"

DORIS_HTTP_REQ_NOT_200_ERR = "http_request_to_doris_return_status_not_200_exception"

# 输出文件的目录
OUTPUT_DIR = "output_doc"

#session 过期时间，default 2 hours
SESSION_TIMEOUT = 72000

# 通过页面用户上传的文件存储的目录
UPLOAD_FOLDER = 'upload_doc'

# 用户级向量数据库目录前缀
VDB_PREFIX = "./vdb/vdb_idx_"

# 文件处理超时毫秒数，默认2小时
FILE_PROCESS_EXPIRE_MS = 7200000

# 数据库连接超时(秒)
DB_CONN_TIMEOUT=20

# 数据库读写超时(秒)
DB_RW_TIMEOUT=50

# 大模型判断为描述性文本的最小长度
MIN_DESC_TXT_LEN = 10

# Word docx 文档的 MIME 类型
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# Excel xlsx 文档的 MIME 类型
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# PPT pptx 文档的  MIME 类型
PPTX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
# JSON MIME 类型
JSON_MIME_TYPE = 'application/json; charset=utf-8'

# 文件处理任务超时时间
TASK_EXPIRE_TIME_MS = 7200 * 1000  # 任务超时时间，默认2小时

# 文件处理初始化进度百分比节点
FILE_TASK_INIT_PERCENT=0.01         # 处理进度大于此值，说明基本材料已经初始化完毕

# 聊天最大历史消息数量
MAX_HISTORY_SIZE = 19

# 单次提交给大语言模型的最大字数
MAX_SECTION_LENGTH = 5000  # 字符数量

import json


@functools.lru_cache(maxsize=128)
def get_const(key: str, app: str) -> Any:
    value = None
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            sql = f"select value from const where key='{key}' and app='{app}' limit 1"
            check_info = query_sqlite(my_conn, sql)
            value_dt = check_info['data']
            value = value_dt[0][0]
        except Exception as e:
            logger.error(f"no_value_info_found_for_key, {key}")

    if not value:
        return key

    try:
        return json.loads(value.strip())
    except (json.JSONDecodeError, AttributeError, TypeError):
        return value


def query_sqlite(db_con, query: str) -> dict:
    try:
        cursor = db_con.cursor()
        query = query.replace('\n', ' ')
        # logger.debug(f"execute_query, {query}")
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        return {"columns": columns, "data": data}
    except Exception as e:
        logger.exception(f"sqlite_query_err, pls_check_your_sqlite_file_{db_con}_and_sql_is_correct, {query}")
        # raise Exception
        exit(-1)