#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from semantic_search import search,check_ollama

import logging.config

from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "我家燃气不通了，是不欠费了，我该怎么办?"
    # my_question = "户内拆改迁移服务该怎么做?"
    logger.info("invoke question: {}".format(my_question))
    answer = search(my_question, init_yml_cfg(), True)
    logger.info(f"answer is\r\n {answer}")


if __name__ == '__main__':
    # check_ollama()
    test_req()
