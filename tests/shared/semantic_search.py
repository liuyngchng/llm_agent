#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from typing import Union
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
import logging.config
import os
import subprocess
import socket
import faiss
import torch

from common.cm_utils import extract_md_content

from common.sys_init import init_yml_cfg

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)
# doc = "1.txt"
doc = "/home/rd/Downloads/1.pdf"
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
            vector_db = FAISS.load_local(
                idx,
                HuggingFaceEmbeddings(model_name=emb_name,  model_kwargs={'device': 'cpu'}),
                allow_dangerous_deserialization=True
            )
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



def search(question: str, cfg: dict) -> Union[str, list[Union[str, dict]]]:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
    """
    logger.info(f"sim_search [{question}]")
    # 搜索部分
    docs_with_scores = get_vector_db().similarity_search_with_relevance_scores(question, k=5)

    # 输出结果和相关性分数
    for related_doc, score in docs_with_scores:
        logger.info(f"[相关度：{score:.2f}]\t{related_doc.page_content[:100]}...")
    # 构建增强提示
    template = """
        基于以下上下文：
        {context}
        回答：{msg}
        (1) 上下文中没有的信息，请不要自行编造
        """
    prompt = ChatPromptTemplate.from_template(template)
    logger.info(f"prompt {prompt}")
    model = get_model(cfg)
    chain = prompt | model
    logger.info(f"submit msg[{question}] to llm {cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}")
    response = chain.invoke({
        "context": "\n\n".join([doc.page_content for doc, score in docs_with_scores]),
        "msg": question
    })
    del model
    torch.cuda.empty_cache()
    return extract_md_content(response.content, "html")


def get_model(cfg):
    return agt_util.get_model(cfg)


def test_search():
    logger.info("gpu number {}".format(faiss.get_num_gpus()))
    # vector_dimension = 1024
    # index = faiss.index_factory(vector_dimension, 'IVF4096,Flat')
    # res = faiss.StandardGpuResources()
    # gpu_index = faiss.index_cpu_to_gpu(res, 0, index)
    # gpu_index.reset()
    # res.noTempMemory()
    start_ollama()
    my_question = "鉴定环节的频率?"
    answer = search(my_question, init_yml_cfg())
    logger.info("answer： {}".format(answer))
    torch.cuda.empty_cache()
    logger.info("cuda released")


if __name__ == "__main__":

    test_search()