#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from semantic_search import search,check_ollama

import logging.config

logging.config.fileConfig('logging.conf')
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
    answer = search(my_question)
    logger.info(f"answer is {answer}")


if __name__ == '__main__':
    check_ollama()
    test_req()
