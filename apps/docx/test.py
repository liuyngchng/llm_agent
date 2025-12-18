#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import os

from apps.docx.app import process_doc
from common import docx_meta_util

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





if __name__ == '__main__':
    uid =332987902
    task_id = 1766038267296
    result = docx_meta_util.get_para_info(task_id)
    logger.info(f"测试结果: {result}")
    process_doc(uid, task_id)