#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import SecretStr

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class ChatAgent:

    def __init__(self, syc_cfg:dict , is_remote_model=True, prompt_padding=""):
        self.syc_cfg = syc_cfg
        self.llm_api_uri = syc_cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(syc_cfg['api']['llm_api_key'])
        self.llm_model_name = syc_cfg['api']['llm_model_name']
        self.is_remote_model = is_remote_model
        self.llm = self.get_llm()

    def get_llm(self):
        if self.is_remote_model:
            if "https" in self.llm_api_uri:
                model = ChatOpenAI(
                    api_key=self.llm_api_key,
                    base_url=self.llm_api_uri,
                    http_client=httpx.Client(verify=False, proxy=None),
                    model=self.llm_model_name,
                    temperature=0,
                    streaming=True,
                )
            else:
                model = ChatOllama(
                    model=self.llm_model_name,
                    base_url=self.llm_api_uri,
                    temperature=0,
                    disable_streaming= False,
                )
        else:
            model = ChatOllama(
                model=self.llm_model_name,
                base_url=self.llm_api_uri,
                temperature=0,
                disable_streaming= False,
            )
        logger.debug(f"chat_agent_model, {model}")
        return model

    def get_chain(self):
        template = self.syc_cfg.get('prompts').get('vdb_chat_msg')
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