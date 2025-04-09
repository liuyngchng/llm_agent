#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf')
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

def classify_question(question: str, cfg: dict, is_remote=True) -> str:
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
    logger.info(f"classify_question [{question}]")
    template = """
          根据以下问题的内容，将用户问题分为以下几类
           (1)缴费;
           (2)上门服务;
           (3)其他;
           问题： {question}\n分类结果:
           
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
    return response.content

def search(question: str, cfg: dict, is_remote=True) -> Union[str, list[Union[str, dict]]]:
    """
    search user questions in knowledge base,
    submit the search result and user question to LLM, return the answer
    """
    logger.info("sim_search [{}] in doc {}".format(question, doc))
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
        (2) 当需要提供上门服务的时候， 提供一个用户可填写的表格
        """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg, is_remote)
    chain = prompt | model
    logger.info("submit question[{}] to llm {}, {}".format(question, cfg['ai']['api_uri'], cfg['ai']['model_name']))
    response = chain.invoke({
        "context": "\n\n".join([doc.page_content for doc, score in docs_with_scores]),
        "question": question
    })
    del model
    torch.cuda.empty_cache()
    return response.content


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


if __name__ == "__main__":
    my_cfg = init_yml_cfg()
    result = classify_question("我要缴费", my_cfg, True)
    logger.info(f"result: {result}")
    result = classify_question("你们能派个人来吗？", my_cfg, True)
    logger.info(f"result: {result}")
    # test()
