#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from typing import Union
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import logging.config
import os
import subprocess
import socket
import faiss
import torch
import httpx
from utils import extract_html, extract_json, rmv_think_block

from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)
doc = "1.txt"
emb_name = os.path.abspath("../bge-large-zh-v1.5")
idx = "faiss_index"


def is_ollama_running(port=11434):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def start_ollama():
    if not is_ollama_running():
        try:
            subprocess.Popen(["ollama", "serve"])
        except subprocess.CalledProcessError as e:
            logger.error("ollama start failed: {}".format(e))
    else:
        logger.error("Ollama is running")

def check_ollama():
    if is_ollama_running():
        logger.info("Ollama is running")   
    else:
        logger.error("please start Ollama first")
        exit(-1)        


def get_vector_db() -> FAISS:
    if os.path.exists("{}/index.faiss".format(idx)):
        logger.info("idx existed")
        try:
            vector_db = FAISS.load_local(idx,
                                         HuggingFaceEmbeddings(model_name=emb_name,  model_kwargs={'device': 'cpu'}),
                                         allow_dangerous_deserialization=True)
            return vector_db
        except Exception as e:
            logger.error("load index failed: {}".format(e))
            raise e
    else:
        logger.info("create idx")
        loader = PyPDFLoader(doc)
        pages = loader.load_and_split()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        texts = text_splitter.split_documents(pages)
        embeddings = HuggingFaceEmbeddings(model_name=emb_name,  model_kwargs={'device': 'cpu'})
        vector_db = FAISS.from_documents(texts, embeddings)
        vector_db.save_local(idx)
        return vector_db

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

def search(question: str, cfg: dict, is_remote=True) -> Union[str, list[Union[str, dict]]]:
    """
    search user questions in knowledge base,
    submit the search result and user question to LLM, return the answer
    """
    logger.info(f"sim_search [{question}] in doc {doc}")
    # 搜索部分
    docs_with_scores = get_vector_db().similarity_search_with_relevance_scores(question, k=5)

    # 输出结果和相关性分数
    for related_doc, score in docs_with_scores:
        logger.info(f"[相关度：{score:.2f}]\t{related_doc.page_content[:100]}...")
    # 构建增强提示
    template = """
        基于以下上下文：
        {context}
        回答：{question}
        (1) 上下文中没有的信息，请不要自行编造
        """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info(f"submit question[{question}] to llm {cfg['ai']['api_uri']}, {cfg['ai']['model_name']}")
    response = chain.invoke({
        "context": "\n\n".join([doc.page_content for doc, score in docs_with_scores]),
        "question": question
    })
    del model
    torch.cuda.empty_cache()
    return extract_html(response.content)

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


def test():
    logger.info("gpu number {}".format(faiss.get_num_gpus()))
    # vector_dimension = 1024
    # index = faiss.index_factory(vector_dimension, 'IVF4096,Flat')
    # res = faiss.StandardGpuResources()
    # gpu_index = faiss.index_cpu_to_gpu(res, 0, index)
    # gpu_index.reset()
    # res.noTempMemory()
    start_ollama()
    my_question = "居民如何开户?"
    answer = search(my_question, init_yml_cfg())
    logger.info("answer： {}".format(answer))
    torch.cuda.empty_cache()
    logger.info("cuda released")


def test_fill_dict():
    info = "我叫张三, 我的电话是 13800138000, 我家住在新疆克拉玛依下城区111123号"
    user_dict = {"客户姓名": "", "联系电话": "", "服务地址": "", "期望上门日期": "", "问题描述": ""}
    my_cfg = init_yml_cfg()
    test_fill_result = fill_dict(info, user_dict, my_cfg, True)
    logger.info(f"{test_fill_result}")

def test_classify():
     my_cfg = init_yml_cfg()
     labels = ["缴费", "上门服务", "个人资料", "自我介绍", "个人信息", "身份登记", "其他"]
     result = classify_question(labels, "我要缴费", my_cfg, True)
     logger.info(f"result: {result}")
     result = classify_question(labels, "你们能派个人来吗？", my_cfg, True)
     logger.info(f"result: {result}")
     result = classify_question(labels, "我家住辽宁省沈阳市", my_cfg, True)
     logger.info(f"result: {result}")


if __name__ == "__main__":

    test_fill_dict()
