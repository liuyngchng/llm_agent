#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config

from common import docx_meta_util

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)





if __name__ == '__main__':
    task_id = 1763719317286
    result = docx_meta_util.get_para_info(task_id)
    logger.info(f"测试结果: {result}")