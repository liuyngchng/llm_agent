#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import SecretStr

from common import agt_util, cfg_util

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class ChatAgent:

    def __init__(self, syc_cfg:dict , prompt_padding=""):
        self.syc_cfg = syc_cfg
        self.llm_api_uri = syc_cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(syc_cfg['api']['llm_api_key'])
        self.llm_model_name = syc_cfg['api']['llm_model_name']
        self.llm = self.get_llm()

    def get_llm(self):
        return agt_util.get_model(self.syc_cfg)

    def get_chain(self):
        template = cfg_util.get_usr_prompt_template('vdb_chat_msg', self.syc_cfg)
        logger.debug(f"template {template}")
        prompt = ChatPromptTemplate.from_template(template)
        model = self.get_llm()
        chain = (
                {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
                | prompt
                | model
                | StrOutputParser()
        )
        return chain