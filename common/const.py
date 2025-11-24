#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

USER_SAMPLE_DATA_DB = "user_info.db"
AI_GEN_TAG="[_AI生成_]"

CFG_DB_FILE = "cfg.db"
CFG_DB_URI=f"sqlite:///{CFG_DB_FILE}"

DORIS_HTTP_REQ_NOT_200_ERR = "http_request_to_doris_return_status_not_200_exception"

OUTPUT_DIR = "output_doc"
SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours
UPLOAD_FOLDER = 'upload_doc'
VDB_PREFIX = "./vdb/vdb_idx_"
FILE_PROCESS_EXPIRE_MS = 7200000  # 文件处理超时毫秒数，默认2小时

DB_CONN_TIMEOUT=20      # 连接超时(秒)
DB_RW_TIMEOUT=50       # 数据读写超时(秒)

MIN_DESC_TXT_LEN = 10               # 描述性文本的最小长度
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
JSON_MIME_TYPE = 'application/json; charset=utf-8'
TASK_EXPIRE_TIME_MS = 7200 * 1000  # 任务超时时间，默认2小时
FILE_TASK_INIT_PERCENT=0.01         # 处理进度大于此值，说明基本材料已经初始化完毕

MAX_HISTORY_SIZE = 19

MAX_SECTION_LENGTH = 3000  # 3000 字符