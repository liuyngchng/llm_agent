#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json

import logging.config
import os
import time
import httpx
import logging.config
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from common import cfg_util
from common.sys_init import init_yml_cfg
from common.cm_utils import rmv_think_block, extract_md_content

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


def get_model(cfg, temperature=1, max_tokens=32768, reasoning=False):
    if cfg['api'].get('is_remote', True):
        model = ChatOpenAI(
            api_key=cfg['api']['llm_api_key'],
            base_url=cfg['api']['llm_api_uri'],
            http_client=httpx.Client(verify=False, proxy=None),
            model=cfg['api']['llm_model_name'],
            temperature=temperature,        # 控制随机性 (0.0-2.0)
            max_tokens=max_tokens,          # 最大生成长度
            top_p=0.9,                      # 核采样参数
            frequency_penalty=0.1,          # 频率惩罚
            presence_penalty=0.1,           # 存在惩罚
            timeout=30,                     # 超时时间
            max_retries=2,                  # 重试次数
            extra_body={
                "reasoning": reasoning
            }
        )
    else:
        from langchain_ollama import ChatOllama
        model = ChatOllama(
            model=cfg['api']['llm_model_name'],
            base_url=cfg['api']['llm_api_uri'],
            temperature=temperature,
        )
    logger.debug(f"get_model,{type(model)}, {model}")
    return model


def classify_txt(labels: list, txt: str, cfg: dict) -> str | None:
    """
    classify txt, multi-label can be obtained
    """
    max_retries = 6
    backoff_times = [5, 10, 20, 40, 80, 160]
    last_exception = None
    model = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                wait_time = backoff_times[attempt - 1]
                logger.info(f"retry #{attempt} times after {wait_time}s")
                time.sleep(wait_time)

            classify_label = ';\n'.join(map(str, labels))
            # logger.debug(f"classify_txt: {txt}")
            template = cfg_util.get_usr_prompt_template('txt_cls_msg', cfg)
            prompt = ChatPromptTemplate.from_template(template)
            # logger.info(f"prompt {prompt}")

            model = get_model(cfg)
            chain = prompt | model
            arg_dict = {"txt": txt, "classify_label": classify_label}
            logger.info(f"submit_arg_dict_to_llm, [{arg_dict}], llm[{cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}]")
            response = chain.invoke(arg_dict)
            output_txt = extract_md_content(rmv_think_block(response.content), "json")
            dispose(model)
            return output_txt

        except Exception as ex:
            last_exception = ex
            logger.error(f"retry_failed_in_classify_txt, retry_time={attempt}, {str(ex)}")
            if attempt < max_retries:
                continue
            dispose(model)
            logger.error(f"all_retries_exhausted_task_classify_txt_failed, {labels}, {txt}")
            raise last_exception

def dispose(model):
    if 'model' in locals():
        del model
        import torch
        torch.cuda.empty_cache()

def classify_msg(labels: list, msg: str, cfg: dict) -> dict:
    """
    classify user's question first, multi-label can be obtained

    """

    classify_label = ';\n'.join(map(str, labels))
    logger.info(f"classify_question: {msg}")
    template = cfg_util.get_usr_prompt_template('csm_cls_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {"msg": msg, "classify_label": classify_label}
    logger.info(f"submit_arg_dict[{arg_dict}] to llm {cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    dispose(model)
    return json.loads(
        extract_md_content(
            rmv_think_block(response.content),
            "json"
        )
    )

def fill_dict(user_info: str, user_dict: dict, cfg: dict) -> dict:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
    """
    logger.info(f"user_info [{user_info}] , user_dict {user_dict}")
    template = cfg_util.get_usr_prompt_template('fill_dict_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {
        "context": user_info,
        "user_dict": json.dumps(user_dict, ensure_ascii=False),
    }
    logger.info(f"submit_arg_dict_to_llm,[{arg_dict}], {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    dispose(model)
    fill_result = user_dict
    try:
        fill_result =  json.loads(rmv_think_block(response.content))
    except Exception as es:
        logger.exception(f"json_loads_err_for {response.content}")
    return fill_result

def txt2sql(schema: str, txt: str, dialect:str, cfg: dict, max_retries=6) -> str | None:
    """
    根据提供的数据库schama, 以及用户的自然语言文本，输出SQL
    :param schema:          数据库schema
    :param txt:             自然语言文本
    :param dialect:         数据库sql方言
    :param cfg:             系统配置
    :param max_retries:     最大尝试次数， 需处于集合 [1, 7]
    """
    template = cfg_util.get_usr_prompt_template('txt_to_sql_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    backoff_times = [5, 10, 20, 40, 80, 160]
    if max_retries < 1:
        max_retries = 1
    if max_retries > len(backoff_times):
        max_retries = len(backoff_times)
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                time.sleep(backoff_times[attempt - 1])
                logger.info(f"retry #{attempt} times after wait {backoff_times[attempt - 1]}s")
            model = get_model(cfg)
            chain = prompt | model
            arg_dict = {
                "dialect": dialect,
                "schema": schema,
                "txt": txt,
                "max_record_count": 20,
            }
            logger.info(f"submit_arg_dict_to_llm {arg_dict}")
            response = chain.invoke(arg_dict)
            output_txt = rmv_think_block(response.content)
            output_txt = extract_md_content(output_txt, "sql")
            return output_txt
        except Exception as ex:
            last_exception = ex
            logger.error(f"retry_failed_in_gen_txt, retry_time={attempt}, {str(ex)}")
            if attempt < max_retries:
                continue
            logger.exception(f"all_retries_exhausted_task_txt2sql_failed, schema={schema}, dialect={dialect}, txt={txt}")
            raise last_exception

def update_session_info(user_info: str, append_info: str, cfg: dict) -> str:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
    """
    logger.info(f"user_info [{user_info}], append_info {append_info}")
    template = cfg_util.get_usr_prompt_template('pad_dict_info_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {"context": user_info, "append_info": append_info}
    logger.info(f"submit_arg_dict_to_llm {arg_dict}, {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    dispose(model)
    fill_result = user_info
    try:
        fill_result = rmv_think_block(response.content)
    except Exception as ex:
        logger.error(f"json_loads_err_for {response.content}")
    return fill_result

def extract_session_info(chat_log: str, cfg: dict) -> str:
    """
    extract_session_info from chat log
    """
    logger.info(f"chat_log [{chat_log}]")
    template = cfg_util.get_usr_prompt_template('extract_person_info_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {"context": chat_log}
    logger.info(f"submit_arg_dict_to_llm[{arg_dict}], {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    dispose(model)
    final_result = chat_log
    try:
        final_result = rmv_think_block(response.content)
    except Exception as ex:
        logger.error(f"json_loads_err_for {response.content}")
    return final_result

def extract_order_info(chat_log: str, cfg: dict) -> str:
    """
    extract ord_gen order  from chat log
    """
    logger.info(f"chat_log [{chat_log}]")
    template = cfg_util.get_usr_prompt_template('get_order_info_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    logger.info(f"submit chat_log[{chat_log}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({"context": chat_log})
    dispose(model)
    final_result = chat_log
    try:
        final_result = rmv_think_block(response.content)
    except Exception as ex:
        logger.error(f"json_loads_err_for {response.content}")
    return final_result

def get_abs_of_chat(txt: list, cfg: dict) -> str:
    """
    get abstract of a long text
    """
    logger.info(f"start_extract_abstract_of_txt [{txt}]")
    template = cfg_util.get_usr_prompt_template('get_chat_abs_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    logger.info(f"submit user_info[{txt}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({"context": txt,})
    dispose(model)
    abstract = ""
    try:
        abstract = rmv_think_block(response.content)
    except Exception as es:
        logger.exception(f"start_extract_abstract_of_txt {response.content}")
    return abstract

def test_complete_user_info():
    user_info = "我叫张三, 我的电话是 13800138000, 我家住在新疆克拉玛依下城区111123号"
    user_info1 = "我的电话是 18918918999, 我家住在湖南张家界上城区222666号"
    user_info2 = "我叫李四"
    my_cfg = init_yml_cfg()
    logger.info(f"base_user_info={user_info}")
    complete_user_info_result = update_session_info(user_info, user_info1, my_cfg, True)
    logger.info(f"complete_user_info_result1={complete_user_info_result}")
    complete_user_info_result = update_session_info(user_info1, user_info2, my_cfg, True)
    logger.info(f"complete_user_info_result2={complete_user_info_result}")