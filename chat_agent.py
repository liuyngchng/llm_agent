#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

    def __init__(self, cfg:dict , is_remote_model=True, prompt_padding=""):
        self.cfg = cfg
        self.llm_api_uri = cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(cfg['api']['llm_api_key'])
        self.llm_model_name = cfg['api']['llm_model_name']
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
                model = ChatOllama(model=self.llm_model_name, base_url=self.llm_api_uri, temperature=0, disable_streaming= False,)
        else:
            model = ChatOllama(model=self.llm_model_name, base_url=self.llm_api_uri, temperature=0, disable_streaming= False,)
        logger.debug(f"model, {model}")
        return model

    def get_chain(self):
        template = """你是一个专业的燃气运营支持助手，请根据以下上下文信息回答问题：
            {context}
            
            问题：{question}
            """
        prompt = ChatPromptTemplate.from_template(template)
        model = self.get_llm()
        chain = (
                {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
                | prompt
                | model
                | StrOutputParser()
        )
        return chain