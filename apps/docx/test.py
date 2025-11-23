#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config

from apps.docx.app import process_doc
from common import docx_meta_util

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)





if __name__ == '__main__':
    uid =332987902
    task_id = 1763862741113
    result = docx_meta_util.get_para_info(task_id)
    logger.info(f"测试结果: {result}")
    process_doc(uid, task_id)