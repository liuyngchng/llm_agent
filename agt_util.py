#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sys_init import init_yml_cfg
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from utils import rmv_think_block
import httpx
import torch
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def get_model(cfg, is_remote):
    if is_remote:
        model = ChatOpenAI(api_key=cfg['ai']['api_key'],
                           base_url=cfg['ai']['api_uri'],
                           http_client=httpx.Client(verify=False, proxy=None),
                           model=cfg['ai']['model_name']
                           )
    else:
        model = ChatOllama(model=cfg['ai']['model_name'], base_url=cfg['ai']['api_uri'])
    return model

def classify_question(classify_label: list, question: str, cfg: dict, is_remote=True) -> str:
    """
    from transformers import pipeline

    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

    def classify_query(text):
        labels = ["投诉", "缴费", "维修"]
        result = classifier(text, labels, multi_label=False)
        return result['labels'][0]

    # 示例使用
    user_input = "我家水管爆了需要处理"
    print(f"问题类型: {classify_query(user_input)}")

    """
    label_str = ';\n'.join(map(str, classify_label))
    logger.info(f"classify_question [{question}]")
    template = f"""
          根据以下问题的内容，将用户问题分为以下几类\n{label_str}\n
          问题：{question}\n输出结果直接给出分类结果，不要有其他多余文字
          """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info("submit question[{}] to llm {}, {}".format(question, cfg['ai']['api_uri'], cfg['ai']['model_name']))
    response = chain.invoke({
        "question": question
    })
    del model
    torch.cuda.empty_cache()
    return rmv_think_block(response.content)

def fill_dict(user_info: str, user_dict: dict, cfg: dict, is_remote=True) -> dict:
    """
    search user questions in knowledge base,
    submit the search result and user question to LLM, return the answer
    """
    logger.info(f"user_info [{user_info}] , user_dict {user_dict}")
    template = """
        基于用户提供的个人信息：
        {context}
        填写 JSON 体中的相应内容：{user_dict}
        (1) 上下文中没有的信息，请不要自行编造
        (2) 不要破坏 JSON 本身的结构
        (3) 直接返回填写好的纯文本的 JSON 内容，不要有任何其他额外内容，不要输出Markdown格式
        """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit user_info[{user_info}] to llm {cfg['ai']['api_uri'],}, {cfg['ai']['model_name']}")
    response = chain.invoke({
        "context": user_info,
        "user_dict": user_dict,
    })
    del model
    torch.cuda.empty_cache()
    fill_result = user_dict
    try:
        fill_result =  json.loads(rmv_think_block(response.content))
    except Exception as es:
        logger.error(f"json_loads_err_for {response.content}")
    return fill_result

def update_session_info(user_info: str, append_info: str, cfg: dict, is_remote=True) -> str:
    """
    search user questions in knowledge base,
    submit the search result and user question to LLM, return the answer
    """
    logger.info(f"user_info [{user_info}], append_info {append_info}")
    template = """
        基于已知的个人信息：{context}，以及新提供的个人信息 {append_info}, 输出更新后个人信息
        (1) 如果同类的信息有冲突，以新提供的信息为准
        (2) 直接返回填写好的纯文本内容，不要有任何其他额外内容，不要输出Markdown格式
        """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit user_info[{user_info}], append_info[{append_info}] to llm {cfg['ai']['api_uri'],}, {cfg['ai']['model_name']}")
    response = chain.invoke({
        "context": user_info,
        "append_info": append_info,
    })
    del model
    torch.cuda.empty_cache()
    fill_result = user_info
    try:
        fill_result = rmv_think_block(response.content)
    except Exception as ex:
        logger.error(f"json_loads_err_for {response.content}")
    return fill_result

def extract_session_info(chat_log: str, cfg: dict, is_remote=True) -> str:
    """
    extract_session_info from chat log
    """
    logger.info(f"chat_log [{chat_log}]")
    template = """
        基于以下文本：
        {context}
        请输出涉及到个人信息的部分文本
        (1)直接返回填写好的纯文本内容，不要有任何其他额外内容，不要输出Markdown格式
        (2)若没有个人信息，则输出空字符串
        """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit chat_log[{chat_log}] to llm {cfg['ai']['api_uri'],}, {cfg['ai']['model_name']}")
    response = chain.invoke({
        "context": chat_log
    })
    del model
    torch.cuda.empty_cache()
    final_result = chat_log
    try:
        final_result = rmv_think_block(response.content)
    except Exception as ex:
        logger.error(f"json_loads_err_for {response.content}")
    return final_result

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
     labels = ["缴费", "上门服务", "个人资料", "自我介绍", "个人信息", "身份登记", "信息查询", "其他"]
     # result = classify_question(labels, "我要缴费", my_cfg, True)
     # logger.info(f"result: {result}")
     # result = classify_question(labels, "你们能派个人来吗？", my_cfg, True)
     # logger.info(f"result: {result}")
     # result = classify_question(labels, "我家住辽宁省沈阳市", my_cfg, True)
     # logger.info(f"result: {result}")
     result = classify_question(labels, "我用户号忘了你们给查一下", my_cfg, True)
     if labels[6] in result:
        logger.info(f"classify_result:labels[6] {labels[6]}")


if __name__ == "__main__":

    # test_classify()
    test_complete_user_info()