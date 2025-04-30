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
from langchain_community.document_loaders import DirectoryLoader
from langchain_core.documents import Document

import logging.config
import os

# knowledge_dir = "../test/"
my_txt_file = "./1.txt"
embedding_model = "../bge-large-zh-v1.5"
vector_db = "./faiss_index"

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def vector_txt(txt_file: str):
    """
    vector a txt file.
    """
    logger.info(f"load_local_doc {txt_file}")
    loader = TextLoader(txt_file, encoding='utf8')
    documents = loader.load()
    logger.info(f"loaded {len(documents)} documents, files_name_list_as_following")
    for doc in documents:
        print(f"{doc.page_content}")
    logger.info("split doc")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=10, separators=['。','\n\n'])
    texts = text_splitter.split_documents(documents)
    logger.info(f"load_embedding_model: {embedding_model}")
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model, cache_folder='./bge-cache', model_kwargs={'device': 'cpu'}
    )
    logger.info("build_vector_db")
    db = FAISS.from_documents(texts, embeddings)
    logger.info("localize_vector_db")
    db.save_local(vector_db)
    logger.info(f"localized_vector_db_file {vector_db}")

def vector_pdf(pdf_file: str):
    """
    vector_pdf_file
    """
    logger.info(f"load_local_file_from {pdf_file}")
    loader = UnstructuredLoader(pdf_file)
    documents = loader.load()
    logger.info(f"loaded {len(documents)} documents, files name list as following")
    for doc in documents:
        #print(f"\t{doc.metadata['page_number']}\t{doc.page_content}")
        print(f"{doc.page_content}")
    logger.info("split_doc")
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
    logger.info("start save vector db to local txt_file")

    db.save_local(vector_db)

    logger.info("vector db saved to local txt_file {}".format(vector_db))

def vector_pdf_dir(pdf_dir: str):

    # 加载知识库文件
    logger.info(f"load local file from {pdf_dir}")
    loader = UnstructuredLoader(pdf_dir)
    # load txt txt_file
    loader = TextLoader(txt_file, encoding='utf8')
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
    logger.info("start save vector db to local txt_file")

    db.save_local(vector_db)

    logger.info("vector db saved to local txt_file {}".format(vector_db))

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

    vector_txt(my_txt_file)
