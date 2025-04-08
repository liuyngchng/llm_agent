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
doc = "1.pdf"
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
                                         HuggingFaceEmbeddings(model_name=emb_name),
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
        embeddings = HuggingFaceEmbeddings(model_name=emb_name)
        vector_db = FAISS.from_documents(texts, embeddings)
        vector_db.save_local(idx)
        return vector_db


def search(question: str, cfg: dict, is_remote=False) -> Union[str, list[Union[str, dict]]]:
    logger.info("sim_search [{}] in doc {}".format(question, doc))
    # 搜索部分
    docs_with_scores = get_vector_db().similarity_search_with_relevance_scores(question, k=5)

    # 输出结果和相关性分数
    for related_doc, score in docs_with_scores:
        # logger.info(f"[相关度：{score:.2f}]\t{related_doc.page_content[:200]}...")
        logger.info(f"[相关度：{score:.2f}]\t{related_doc.page_content}")
    # 构建增强提示
    template = """基于以下上下文：
        {context}
        回答：{question}
        上下文中没有的信息，请不要自行编造"""

    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    if is_remote:
        model = ChatOpenAI(api_key=cfg['ai']['api_key'],
                           base_url=cfg['ai']['api_uri'],
                           http_client=httpx.Client(verify=False, proxy=None),
                           model=cfg['ai']['model_name']
                           )
    else:
        model = ChatOllama(model=cfg['ai']['model_name'], base_url=cfg['ai']['api_uri'])
    chain = prompt | model
    logger.info("submit question[{}] to llm {}, {}".format(question, cfg['ai']['api_uri'], cfg['ai']['model_name']))
    response = chain.invoke({
        "context": "\n\n".join([doc.page_content for doc, score in docs_with_scores]),
        "question": question
    })
    return response.content


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
    init_yml_cfg()
    test()
