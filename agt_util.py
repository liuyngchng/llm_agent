#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json

import utils
from sys_init import init_yml_cfg
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from utils import rmv_think_block, extract_md_content
import httpx
import torch
import logging.config
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

__temperature = 0.7
__max_tokens=32768
__reasoning=False

def get_model(cfg):
    if cfg['api']['is_remote']:
        model = ChatOpenAI(
            api_key=cfg['api']['llm_api_key'],
            base_url=cfg['api']['llm_api_uri'],
            http_client=httpx.Client(verify=False, proxy=None),
            model=cfg['api']['llm_model_name'],
            # 常用参数配置
            temperature=__temperature,        # 控制随机性 (0.0-2.0)
            max_tokens=__max_tokens,        # 最大生成长度
            top_p=0.9,              # 核采样参数
            frequency_penalty=0.1,  # 频率惩罚
            presence_penalty=0.1,   # 存在惩罚
            timeout=30,             # 超时时间
            max_retries=2,          # 重试次数
            extra_body={
                "reasoning": __reasoning
            }
        )
    else:
        model = ChatOllama(
            model=cfg['api']['llm_model_name'],
            base_url=cfg['api']['llm_api_uri'],
            temperature=__temperature,
        )
    logger.info(f"get_model,{type(model)}, {model}")
    return model

def classify_msg(labels: list, msg: str, cfg: dict) -> dict:
    """
    classify user's question first, multi-label can be obtained
    from transformers import pipeline
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    def classify_query(text):
        labels = ["投诉", "缴费", "维修"]
        result = classifier(text, labels, multi_label=False)
        return result['labels'][0]
    # 示例使用
    user_input = "我家水管爆了需要处理"
    print(f"问题类型: {classify_query(user_input)}")
    :param labels: the label list collection which AI can produce label within it
    :param msg: the msg need to be classified by AI
    :param cfg: the configuration information of system
    """

    classify_label = ';\n'.join(map(str, labels))
    logger.info(f"classify_question: {msg}")
    template = cfg['prompts']['csm_cls_msg']
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {"msg": msg, "classify_label": classify_label}
    logger.info(f"submit_arg_dict[{arg_dict}] to llm {cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    del model
    torch.cuda.empty_cache()
    return json.loads(
        extract_md_content(
            rmv_think_block(response.content),
            "json"
        )
    )

def classify_txt(labels: list, txt: str, cfg: dict) -> str | None:
    """
    classify txt, multi-label can be obtained
    """
    max_retries = 6
    backoff_times = [5, 10, 20, 40, 80, 160]
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                wait_time = backoff_times[attempt - 1]
                logger.info(f"retry #{attempt} times after {wait_time}s")
                time.sleep(wait_time)

            classify_label = ';\n'.join(map(str, labels))
            # logger.debug(f"classify_txt: {txt}")
            template = cfg['prompts']['txt_cls_msg']
            prompt = ChatPromptTemplate.from_template(template)
            # logger.info(f"prompt {prompt}")

            model = get_model(cfg)
            chain = prompt | model
            arg_dict = {"txt": txt, "classify_label": classify_label}
            logger.info(f"submit_arg_dict_to_llm, [{arg_dict}], llm[{cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}]")
            response = chain.invoke(arg_dict)
            output_txt = extract_md_content(rmv_think_block(response.content), "json")
            del model
            torch.cuda.empty_cache()
            return output_txt

        except Exception as ex:
            last_exception = ex
            logger.error(f"retry_failed_in_classify_txt, retry_time={attempt}, {str(ex)}")
            if attempt < max_retries:
                continue
            if 'model' in locals():
                del model
                torch.cuda.empty_cache()
            logger.error(f"all_retries_exhausted_task_classify_txt_failed, {labels}, {txt}")
            raise last_exception

def fill_dict(user_info: str, user_dict: dict, cfg: dict) -> dict:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
    """
    logger.info(f"user_info [{user_info}] , user_dict {user_dict}")
    template = cfg['prompts']['fill_dict_msg']
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
    del model
    torch.cuda.empty_cache()
    fill_result = user_dict
    try:
        fill_result =  json.loads(rmv_think_block(response.content))
    except Exception as es:
        logger.exception(f"json_loads_err_for {response.content}")
    return fill_result

def gen_docx_outline_stream(doc_type: str, doc_title: str, keywords: str, cfg: dict):
    """
    流式生成docx文档目录
    :doc_type: docx 文档的内容类型，详见:class:`my_enums`WriteDocType
    :doc_title: 文档标题
    :keywords: 文档写作的其他要求关键词
    :cfg: 系统配置
    :is_remote: 是否调用远端LLM
    """
    logger.info(f"doc_type[{doc_type}] , doc_title[{doc_title}], cfg['api']=[{cfg.get('api', None)}]")
    template = cfg['prompts']['gen_docx_outline_msg']
    prompt = ChatPromptTemplate.from_template(utils.replace_spaces(template))
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    logger.info(f"submit_to_llm, {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}, prompt {prompt}")
    try:
        # 流式调用模型
        for chunk in model.stream(prompt.format(doc_type=doc_type, doc_title=doc_title, keywords=keywords)):
            if hasattr(chunk, 'content'):
                yield utils.rmv_think_block(chunk.content)
            elif hasattr(chunk, 'text'):
                yield utils.rmv_think_block(chunk.text())

    finally:
        # 清理资源
        logger.info("gen_outline_finish, dispose resources")
        del model
        torch.cuda.empty_cache()


def gen_txt(write_context: str, references: str, paragraph_prompt: str, user_comment: str, catalogue: str,
            current_sub_title: str, cfg: dict, max_retries=6) -> str | None:
    """
    根据提供的三级目录、参考资料，以及每个章节的具体文本写作要求，输出文本
    :param write_context:       整体的写作背景
    :param references:          可供参考的样例子文本
    :param paragraph_prompt:    局部章节文本的写作要求
    :param user_comment:        用户添加的批注文本
    :param catalogue:           整个文档的三级目录
    :param current_sub_title:   当前写作章节的目录标题
    :param cfg:                 系统配置
    :param max_retries:         最大尝试次数， 需处于集合 [1, 7]
    """
    # logger.info(
    #     f"catalogue[{catalogue}], "
    #     f"user_instruction[{paragraph_prompt}], "
    #     f"demo_txt[{demo_txt}], "
    #     f"current_sub_title[{current_sub_title}]"
    # )
    template = cfg['prompts']['gen_txt_msg']
    prompt = ChatPromptTemplate.from_template(template)
    # logger.debug(f"prompt {prompt}")
    backoff_times = [5, 10, 20, 40, 80, 160]
    if max_retries < 1:
        max_retries = 1
    if max_retries > len(backoff_times):
        max_retries = len(backoff_times)
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                time.sleep(backoff_times[attempt - 1])
                logger.info(f"retry #{attempt} times after wait {backoff_times[attempt - 1]}s")
            model = get_model(cfg)
            chain = prompt | model
            arg_dict = {
                "write_context": write_context,
                "catalogue": catalogue,
                "current_sub_title": current_sub_title,
                "references": references,
                "paragraph_prompt": paragraph_prompt,
                "user_comment": user_comment,
            }
            logger.info(f"gen_txt_arg, {arg_dict}, {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
            response = chain.invoke(arg_dict)
            output_txt = rmv_think_block(response.content)
            del model
            torch.cuda.empty_cache()
            output_txt = output_txt.replace(current_sub_title, "").strip()
            return output_txt
        except Exception as ex:
            last_exception = ex
            logger.exception(f"retry_failed_in_gen_txt, retry_time={attempt}, {str(ex)}")
            if attempt < max_retries:
                continue
            if 'model' in locals():
                del model
                torch.cuda.empty_cache()
            logger.exception(f"all_retries_exhausted_task_gen_txt_failed, {paragraph_prompt}")
            raise last_exception
    return None


def txt2sql(schema: str, txt: str, dialect:str, cfg: dict, max_retries=6) -> str | None:
    """
    根据提供的数据库schama, 以及用户的自然语言文本，输出SQL
    :param schema:          数据库schema
    :param txt:             自然语言文本
    :param dialect:         数据库sql方言
    :param cfg:             系统配置
    :param max_retries:     最大尝试次数， 需处于集合 [1, 7]
    """
    template = cfg['prompts']['txt_to_sql_msg']
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
    template = cfg['prompts']['pad_dict_info_msg']
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {"context": user_info, "append_info": append_info}
    logger.info(f"submit_arg_dict_to_llm {arg_dict}, {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    del model
    torch.cuda.empty_cache()
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
    template = cfg['prompts']['extract_person_info_msg']
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    arg_dict = {"context": chat_log}
    logger.info(f"submit_arg_dict_to_llm[{arg_dict}], {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke(arg_dict)
    del model
    torch.cuda.empty_cache()
    final_result = chat_log
    try:
        final_result = rmv_think_block(response.content)
    except Exception as ex:
        logger.error(f"json_loads_err_for {response.content}")
    return final_result

def extract_lpg_order_info(chat_log: str, cfg: dict) -> str:
    """
    extract lpg order  from chat log
    """
    logger.info(f"chat_log [{chat_log}]")
    template = cfg['prompts']['get_lpg_order_info_msg']
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    logger.info(f"submit chat_log[{chat_log}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({"context": chat_log})
    del model
    torch.cuda.empty_cache()
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
    template = cfg['prompts']['get_chat_abs_msg']
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    logger.info(f"submit user_info[{txt}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({"context": txt,})
    del model
    torch.cuda.empty_cache()
    abstract = ""
    try:
        abstract = rmv_think_block(response.content)
    except Exception as es:
        logger.exception(f"start_extract_abstract_of_txt {response.content}")
    return abstract

def test_fill_dict():
    info = "我叫张三, 我的电话是 13800138000, 我家住在新疆克拉玛依下城区111123号"
    user_dict = {"客户姓名": "", "联系电话": "", "服务地址": "", "期望上门日期": "", "问题描述": ""}
    my_cfg = init_yml_cfg()
    test_fill_result = fill_dict(info, user_dict, my_cfg, True)
    logger.info(f"{test_fill_result}")

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



def test_classify():
     my_cfg = init_yml_cfg()
     labels = ["缴费", "上门服务", "个人信息", "信息查询", "转接人工客服", "其他"]
     # result = classify_question(labels, "我要缴费", my_cfg, True)
     # logger.info(f"result: {result}")
     # result = classify_question(labels, "你们能派个人来吗？", my_cfg, True)
     # logger.info(f"result: {result}")
     result = classify_msg(labels, "我叫张三，我家住辽宁省沈阳市皇姑屯xxx街道xxx小区，我家燃气不好使了，能派人来给看吗?", my_cfg, True)
     logger.info(f"result: {result}")
     # result = classify_question(labels, "我用户号忘了你们给查一下", my_cfg, True)
     # if labels[6] in result:
     #    logger.info(f"classify_result:labels[6] {labels[6]}")


if __name__ == "__main__":

    # test_classify()
    test_complete_user_info()