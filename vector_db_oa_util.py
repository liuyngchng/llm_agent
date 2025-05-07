#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通过调用远程的embedding API，将本地文档向量化，形成矢量数据库文件，用于进行向量检索
for OpenAI compatible remote API
"""
import httpx
import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
import logging.config
from openai import OpenAI
from sys_init import init_yml_cfg


vector_db_dir = "./faiss_oa_vector"

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class RemoteEmbeddings(Embeddings):  # 适配器类
    def __init__(self, client):
        self.client = client

    def embed_documents(self, texts):
        return [self._get_embedding(t) for t in texts]

    def embed_query(self, text):
        return self._get_embedding(text)

    def _get_embedding(self, text):
        resp = self.client.embeddings.create(model="bge-m3", input=text)
        return resp.data[0].embedding


def process_doc(documents: list[Document], vector_db: str, sys_cfg:dict,
                chunk_size=15, chunk_overlap=2) -> None:
    logger.info(f"loaded {len(documents)} documents, files_name_list_as_following")
    logger.info("split_doc")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=['\n', '。', '！', '？', '；', '...']
    )
    texts = text_splitter.split_documents(documents)
    logger.info(f"split_doc_finished, {texts}")
    client = build_client(sys_cfg)
    logger.info(f"init_client_with_config: {sys_cfg}")
    embeddings = RemoteEmbeddings(client)
    vectorstore = FAISS.from_documents(texts, embeddings)
    vectorstore.save_local(vector_db)
    logger.info(f"save_vector_to_local {vector_db}")

def build_client(sys_cfg: dict):
    return OpenAI(
        base_url= sys_cfg['api_uri'],   # "https://myhost/v1",
        api_key= sys_cfg['api_key'],    # "sk-xxxxx",
        http_client=httpx.Client(verify=False),
    )

def load_vector_db(vector_db: str, sys_cfg: dict):
    client = build_client(sys_cfg)
    embeddings = RemoteEmbeddings(client)
    return FAISS.load_local(vector_db, embeddings, allow_dangerous_deserialization=True)

def search_similar_text(query: str, vector_db, sys_cfg: dict, top_k=3):
    db = load_vector_db(vector_db, sys_cfg)
    return db.similarity_search_with_relevance_scores(query, k=top_k)


def vector_txt(txt_file: str, sys_cfg:dict):
    logger.info(f"load_local_doc {txt_file}")
    loader = TextLoader(txt_file, encoding='utf8')
    docs = loader.load()
    process_doc(docs, vector_db_dir, sys_cfg)


if __name__ == "__main__":
    os.environ["NO_PROXY"] = "*"  # 禁用代理
    my_cfg = init_yml_cfg()
    vector_txt("./1.txt", my_cfg['ai'])

    results = search_similar_text("奇怪的句子", vector_db_dir, my_cfg['ai'])
    for result in results:
        logger.info(f"search_result: {result[0].page_content}, score {result[1]}")
