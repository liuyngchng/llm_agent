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

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)
doc = "1.pdf"
emb_name = os.path.abspath("../bge-large-zh-v1.5")
idx = "faiss_index"

model_name = "deepseek-r1:7b"
api_url = "http://127.0.0.1:11434"
api_key = "123456789"


def init_cfg(cfg_file: str):
    global api_url, api_key, model_name
    with open(cfg_file) as f:
        lines = f.readlines()
    if len(lines) < 2:
        logger.error("cfg_err_in_file_{}".format(cfg_file))
        return
    try:
        api_url = lines[0].strip()
        api_key = lines[1].strip()
        model_name = lines[2].strip()
    except Exception as e:
        logger.error("init_cfg_error: {}".format(e))


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


def get_vector_db() -> FAISS:
    if os.path.exists("{}/index.faiss".format(idx)):
        logger.info("idx existed")
        try:
            vector_db = FAISS.load_local(idx,
                                         HuggingFaceEmbeddings(model_name=emb_name),
                                         allow_dangerous_deserialization=True)
        except Exception as e:
            logger.error("load index failed: {}".format(e))
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


def search(question: str, is_remote=False) -> Union[str, list[Union[str, dict]]]:
    logger.info("sim_search [{}] in doc {}".format(question, doc))
    # 搜索部分
    docs_with_scores = get_vector_db().similarity_search_with_relevance_scores(question, k=2)

    # 输出结果和相关性分数
    # for doc, score in docs_with_scores:
    #     print(f"[相关度：{score:.2f}] {doc.page_content[:200]}...")
    # 构建增强提示
    template = """基于以下上下文：
        {context}
        
        回答：{question}"""
    prompt = ChatPromptTemplate.from_template(template)
    if is_remote:
        model = ChatOpenAI(api_key=api_key, base_url=api_url,
                           http_client=httpx.Client(verify=False), model=model_name)
    else:
        model = ChatOllama(model=model_name, base_url=api_url)
    chain = prompt | model
    logger.info("submit question to LLM: {}".format(question))
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
    answer = search(my_question)
    logger.info("answer： {}".format(answer))
    torch.cuda.empty_cache()
    logger.info("cuda released")


if __name__ == "__main__":
    test()
