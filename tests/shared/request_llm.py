#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
from langchain_ollama import OllamaLLM

import getpass
import os

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

def _set_env(key: str):
    if key not in os.environ:
        os.environ[key] = getpass.getpass(f"{key}:")


def req_ollama(question):
    """
    请求大模型 API，获取返回的信息
    :param question:
    :return:
    """
    # llm_model_name = "llama3.2:3b"
    # llm_url = "http://127.0.0.1:11434"

    model_name = "deepseek-r1"
    llm_url = "https://aiproxy.petrotech.cnpc/v1"


    llm = OllamaLLM(model=model_name, base_url=llm_url)
    logger.info("invoke msg: {}".format(question))
    answer = llm.invoke(question)
    logger.info("answer is: {}".format(answer))

if __name__ == "__main__":
    """
    A hello LLM demo for request LLM.
    """
    #_set_env("OPENAI_API_KEY")
    # req_ollama("hi")
