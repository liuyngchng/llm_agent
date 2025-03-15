#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from semantic_search import search

import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)
model_name = "deepseek-r1:7b"
api_url = "http://127.0.0.1:11434"


def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "户内拆改迁移服务该怎么做?"
    logger.info("invoke question: {}".format(my_question))
    answer = search(my_question)
    logger.info("answer is {}".format(answer))


if __name__ == '__main__':
    test_req()
