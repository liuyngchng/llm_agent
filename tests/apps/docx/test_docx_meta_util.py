#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from unittest import TestCase
import logging.config

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

class Test(TestCase):
    def test_get_para_info(self):
        task_id = 12345
        result = docx_meta_util.get_para_info(task_id)
        logger.info(f"测试结果: {result}")


if __name__ == "__main__":
    import unittest

    unittest.main()
