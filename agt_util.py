#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sys_init import init_yml_cfg
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from utils import rmv_think_block, extract_md_content
import httpx
import torch
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def get_model(cfg, is_remote):
    if is_remote:
        model = ChatOpenAI(api_key=cfg['api']['llm_api_key'],
                           base_url=cfg['api']['llm_api_uri'],
                           http_client=httpx.Client(verify=False, proxy=None),
                           model=cfg['api']['llm_model_name']
                           )
    else:
        model = ChatOllama(model=cfg['api']['llm_model_name'], base_url=cfg['api']['llm_api_uri'])
    return model

def classify_msg(labels: list, msg: str, cfg: dict, is_remote=True) -> dict:
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
    :param is_remote: is the LLM is deployed in remote endpoint
    """

    label_str = ';\n'.join(map(str, labels))
    logger.info(f"classify_question: {msg}")
    template = f'''
          根据以下问题的内容，将用户问题分为以下几类\n{label_str}\n
          问题：{msg}\n分类结果输出为 JSONArray\n当文本涉及多个分类时，请同时输出多个分类
          '''
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit msg[{msg}] to llm {cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({
        "msg": msg
    })
    del model
    torch.cuda.empty_cache()
    return json.loads(
        extract_md_content(
            rmv_think_block(response.content),
            "json"
        )
    )

def classify_txt(labels: list, txt: str, cfg: dict, is_remote=True) -> str:
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

            label_str = ';\n'.join(map(str, labels))
            logger.info(f"classify_txt: {txt}")
            template = f'''对以下文本进行分类\n{label_str}\n文本：{txt}\n分类结果输出为单一分类标签文本，不要输出任何额外信息'''
            prompt = ChatPromptTemplate.from_template(template)
            logger.info(f"prompt {prompt}")

            model = get_model(cfg, is_remote)
            chain = prompt | model
            logger.info(f"submit_msg_to_llm, txt[{txt}], llm[{cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}]")

            response = chain.invoke({"txt": txt})
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

def fill_dict(user_info: str, user_dict: dict, cfg: dict, is_remote=True) -> dict:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
    """
    logger.info(f"user_info [{user_info}] , user_dict {user_dict}")
    template = '''
        基于用户提供的个人信息：
        {context}
        填写 JSON 体中的相应内容：{user_dict}
        (1) 上下文中没有的信息，请不要自行编造
        (2) 不要破坏 JSON 本身的结构
        (3) 直接返回填写好的纯文本的 JSON 内容，不要有任何其他额外内容，不要输出Markdown格式
        '''
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit user_info[{user_info}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
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


import time


def gen_txt(context: str, instruction: str, cfg: dict, is_remote=True, max_retries=6) -> str:
    """
    根据提供的文本的写作风格，以及文本写作要求，输出文本
    :param context: 写作风格文本
    :param instruction: 写作要求
    :param cfg: 系统配置
    :param is_remote: 是否调用远端LLM
    :param max_retries: 最大尝试次数， 需处于集合 [1, 5]
    """
    logger.info(f"user_instruction [{instruction}], context {context}")
    template = ("根据下面文本的写作风格：\n{context}\n以及具体的文本写作要求\n{instruction}\n生成大约300字的文本\n"
        "(1)直接返回纯文本内容，不要有任何其他额外内容，不要输出Markdown格式\n"
        "(2)调整输出文本的格式，需适合添加在Word文档中\n"
        "(3)移除多余的空行\n")
    prompt = ChatPromptTemplate.from_template(template)
    logger.debug(f"prompt {prompt}")
    backoff_times = [5, 10, 20, 40, 80, 160]
    if max_retries > len(backoff_times):
        max_retries = len(backoff_times)
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                time.sleep(backoff_times[attempt - 1])
                logger.info(f"retry #{attempt} times after wait {backoff_times[attempt - 1]}s")
            model = get_model(cfg, is_remote)
            chain = prompt | model
            logger.info(f"submit_instruction_and_context_to_llm, instruction[{instruction}],ctx[{context}], "
                f"{cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
            response = chain.invoke({"context": context, "instruction": instruction})
            output_txt = rmv_think_block(response.content)
            del model
            torch.cuda.empty_cache()
            return output_txt
        except Exception as ex:
            last_exception = ex
            logger.error(f"retry_failed_in_gen_txt, retry_time={attempt}, {str(ex)}")
            if attempt < max_retries:
                continue
            if 'model' in locals():
                del model
                torch.cuda.empty_cache()
            logger.error(f"all_retries_exhausted_task_gen_txt_failed, {instruction}")
            raise last_exception

def update_session_info(user_info: str, append_info: str, cfg: dict, is_remote=True) -> str:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
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
    logger.info(f"submit user_info[{user_info}], append_info[{append_info}] "
                f"to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
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
    template = '''
        基于以下文本：
        {context}
        请输出涉及到个人信息的部分文本
        (1)直接返回填写好的纯文本内容，不要有任何其他额外内容，不要输出Markdown格式
        (2)若没有个人信息，则输出空字符串
        '''
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit chat_log[{chat_log}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
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

def get_abs_of_chat(txt: list, cfg: dict, is_remote=True) -> str:
    """
    get abstract of a long text
    """
    logger.info(f"start_extract_abstract_of_txt [{txt}]")
    template = '''
        基于用户和机器人客服的对话文本
        {context}
        抽取重要内容，以便于提供给人工客服进行后续的客户服务
        '''
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit user_info[{txt}] to llm {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({
        "context": txt,
    })
    del model
    torch.cuda.empty_cache()
    abstract = ""
    try:
        abstract = rmv_think_block(response.content)
    except Exception as es:
        logger.error(f"start_extract_abstract_of_txt {response.content}")
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

    test_classify()
    # test_complete_user_info()