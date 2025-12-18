#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

import logging.config

# 加载配置
log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# 创建 logger
logger = logging.getLogger()

# 加载知识库文件
logger.info("load doc")
loader = TextLoader("./1.txt", encoding='utf8')
documents = loader.load()

# 将文档分割成块
logger.info("split doc")
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
texts = text_splitter.split_documents(documents)

# 加载Embedding模型，进行自然语言处理
logger.info("load embedding model")
# bge-large-zh-v1.5 中文分词模型，国内环境可以通过 https://modelscope.cn/models/BAAI/bge-large-zh-v1.5 下载
embeddings = HuggingFaceEmbeddings(model_name="../bge-large-zh-v1.5", cache_folder='./bge-cache')

# 创建向量数据库
logger.info("build vector db")
db = FAISS.from_documents(texts, embeddings)
# 保存向量存储库至本地，save_local() 方法将生成的索引文件保存到本地，以便之后可以重新加载
logger.info("save vector db to local txt_file")
db.save_local("./faiss_index")
logger.info("vector db saved to local txt_file")