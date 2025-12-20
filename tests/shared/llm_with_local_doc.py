#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.


from semantic_search import search,check_ollama
import logging.config
from sys_init import init_yml_cfg

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


def test_req():
    """
    ask the LLM for some private msg not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "我家燃气不通了，是不欠费了，我该怎么办?"
    # my_question = "户内拆改迁移服务该怎么做?"
    logger.info("invoke msg: {}".format(my_question))
    answer = search(my_question, init_yml_cfg(), True)
    logger.info(f"answer is\r\n {answer}")


if __name__ == '__main__':
    # check_ollama()
    test_req()
