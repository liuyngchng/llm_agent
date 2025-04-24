#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将本地文档进行向量化，形成矢量数据库文件，用于 LLM 进行 RAG
"""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
# from langchain_community.vectorstores import SQLiteVSS
from langchain_unstructured import UnstructuredLoader
# from langchain_community.document_loaders import DirectoryLoader
from langchain_core.documents import Document

import logging.config
import os

# knowledge_dir = "../test/"
knowledge_file = "./1.txt"
# bge-large-zh-v1.5 中文分词模型，国内网络环境可以通过 https://modelscope.cn/models/BAAI/bge-large-zh-v1.5 下载
embedding_model = "../bge-large-zh-v1.5"
vector_file = "./faiss_index"

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def vectoring(file: str):


    # 加载知识库文件
    logger.info(f"load local doc {file}")
    # load word, PDF file
    # loader = UnstructuredLoader(file)
    # load txt file
    loader = TextLoader(file, encoding='utf8')
    # load a directory
    # loader = DirectoryLoader(path=knowledge_dir, recursive=True, load_hidden=False,
    #                          loader_cls=TextLoader, glob="**/*.java")
    documents = loader.load()
    logger.info("loaded {} documents, files name list as following".format(len(documents)))
    for doc in documents:
        #print(f"\t{doc.metadata['page_number']}\t{doc.page_content}")
        print(f"{doc.page_content}")

    # 将文档分割成块
    logger.info("split doc")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=10, separators=['。','\n\n'])
    texts = text_splitter.split_documents(documents)

    # 加载Embedding模型，进行自然语言处理
    logger.info(f"load embedding model: {embedding_model}")
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        cache_folder='./bge-cache',
        model_kwargs={'device': 'cpu'}
    )

    # 创建向量数据库
    logger.info("build vector db")
    db = FAISS.from_documents(texts, embeddings)
    # 在SQLite中存储向量
    # db = SQLiteVSS.from_texts(
    #     texts=texts,
    #     embedding=embeddings,
    #     table="state_union",
    #     db_file="sqlite_vss/vss.db",  # SQLite数据库文件路径
    # )

    logger.info("start save vector db to local file")

    # FAISS
    db.save_local(vector_file)
    # SQLite-VSS
    # None
    logger.info("vector db saved to local file {}".format(vector_file))


if __name__ == "__main__":
    """
    read the local document like txt, docx, pdf etc., and embedding the content 
    to a FAISS vector database.
    submit a msg about the local documents to the LLM, let LLM give a response
    that about the documents.
    """
    # os.putenv("CUDA_VISIBLE_DEVICES", "1")
    # a = os.environ.get("CUDA_VISIBLE_DEVICES")
    # print(a)

    # os.environ["CUDA_VISIBLE_DEVICES"] = 0

    vectoring(knowledge_file)
