#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pip install docx2txt python-docx
通过调用远程的 embedding API，将本地文档向量化，形成矢量数据库文件，用于进行向量检索
for OpenAI compatible remote API
通过将大文档分为多个批次，实时输出向量化进度，对于大批量文档的向量化比较友好
"""
import time

import httpx
import os
from langchain_community.document_loaders import (TextLoader,
    UnstructuredPDFLoader, UnstructuredWordDocumentLoader)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
import logging.config
from openai import OpenAI
from sys_init import init_yml_cfg
from tqdm import tqdm
from typing import List


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

model="bge-m3"

class RemoteEmbeddings(Embeddings):  # 适配器类
    """
    远程分词客户端
    """
    def __init__(self, client):
        self.client = client

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._get_embedding(t) for t in texts]

    def embed_query(self, text:str ):
        return self._get_embedding(text)

    def _get_embedding(self, text: str):
        resp = self.client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding


def process_doc(task_id:str, thread_lock, task_progress:dict, documents: list[Document],
    vector_db: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80, batch_size=10) -> None:
    """处理文档并构建向量数据库

    Args:
        task_id: 任务ID
        thread_lock: 线程锁
        task_progress: 任务进度字典
        documents: 待处理文档列表
        vector_db: 向量数据库存储路径
        sys_cfg: 系统配置
        chunk_size: 文本分块大小
        chunk_overlap: 分块重叠大小
        batch_size: 批量处理大小
    Returns:
        None
    """
    pbar = None
    try:
        doc_sources = [doc.metadata['source'] for doc in documents]
        logger.info(f"Loaded {len(documents)} documents:\n" + "\n".join(f"- {src}" for src in doc_sources))
        logger.info("splitting_documents...")
        separators = ['。', '！', '？', '；', '...', '、', '，']
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            keep_separator=False
        )
        doc_list = text_splitter.split_documents(documents)
        with open('chunks.txt', 'w', encoding='utf-8') as f:
            for i, chunk in enumerate(doc_list):
                f.write(f"Chunk {i}, Source: {chunk.metadata['source']}\n{chunk.page_content}\n" + "-" * 50 + "\n")
        client = build_client(sys_cfg)
        logger.info(f"init_client_with_config: {sys_cfg}")
        embeddings = RemoteEmbeddings(client)
        if not doc_list:
            logger.error("no_doc_need_process_err")
            return
        logger.info(f"开始向量化 {len(doc_list)} chunks (batch_size={batch_size})")
        vectorstore = load_vector_db(vector_db, sys_cfg)
        with tqdm(total=len(doc_list), desc="文档向量化进度", unit="chunk") as pbar:
            with thread_lock:
                task_progress[task_id] = {
                    "text": str(pbar),
                    "timestamp": time.time()
                }
            for i in range(0, len(doc_list), batch_size):
                batch = doc_list[i:i + batch_size]
                try:
                    if vectorstore is None:
                        vectorstore = FAISS.from_documents(batch, embeddings)
                    else:
                        vectorstore.merge_from(FAISS.from_documents(batch, embeddings))
                    pbar.update(len(batch))
                except Exception as e:
                    logger.error(f"处理批次 {i}-{i + batch_size} 时出错: {str(e)}")
                    continue
            logger.info(f"向量数据库构建完成，保存到 {vector_db}")
            vectorstore.save_local(vector_db)
            logger.info(f"save_vector_db_to_local_dir {vector_db}")
    except Exception as e:
        logger.error(f"处理文档时发生错误: {str(e)}", exc_info=True)
        raise
    finally:
        if pbar and not pbar.disable:
            pbar.close()

def build_client(sys_cfg: dict):
    """
    :param sys_cfg: system configuration info.
    :return: the client
    """
    return OpenAI(
        base_url= sys_cfg['llm_api_uri'],   # "https://myhost/v1",
        api_key= sys_cfg['llm_api_key'],    # "sk-xxxxx",
        http_client=httpx.Client(
            verify=False,
            timeout=httpx.Timeout(30.0)
        ),
    )

def load_vector_db(vector_db: str, sys_cfg: dict):
    """
    :param vector_db: the vector db file
    :param sys_cfg: system configuration info.
    :return: the vector db
    """
    client = build_client(sys_cfg)
    embeddings = RemoteEmbeddings(client)
    return FAISS.load_local(vector_db, embeddings, allow_dangerous_deserialization=True)

def search_similar_text(query: str, score_threshold: float, vector_db, sys_cfg: dict, top_k=3):
    """
    :param query: the query text
    :param score_threshold: the score threshold
    :param vector_db: the vector db file
    :param sys_cfg: system configuration info.
    :param top_k: the top k results
    :return: the results
    """
    db = load_vector_db(vector_db, sys_cfg)
    return db.similarity_search_with_relevance_scores(query,k= top_k, score_threshold = score_threshold)



def vector_file_in_progress(task_id:str, thread_lock, task_progress:dict, file_name: str,
    vector_db_dir: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80) -> None:
    """Process a document file and build a vector database.
    Args:
        task_id (str): Unique identifier for the task.
        thread_lock (threading.Lock): Thread lock for concurrent environments.
        task_progress (dict): Dictionary to track task progress.
        file_name (str): Path to the input document file.
        vector_db_dir (str): Directory to save the vector database.
        sys_cfg (dict): System configuration parameters.
        chunk_size (int, optional): Size of text chunks. Defaults to 300.
        chunk_overlap (int, optional): Overlap between chunks. Defaults to 80.

    Returns:
        None
    """
    try:
        with thread_lock:
            task_progress[task_id] = {
                "text": f"开始处理文档...",
                "timestamp": time.time()
            }
        logger.info(f"start_process_doc, {file_name}")
        file_type = file_name.split(".")[-1].lower()
        loader_mapping = {
            "txt": lambda f: TextLoader(f, encoding='utf8'),
            "pdf": lambda f: UnstructuredPDFLoader(f, encoding='utf8'),
            "docx": lambda f: UnstructuredWordDocumentLoader(f),
        }

        # 根据文件类型选择加载器
        if file_type in loader_mapping:
            loader = loader_mapping[file_type](file_name)
        else:
            raise ValueError(f"Unsupported_file_type: {file_type}")
        documents: List[Document] = loader.load()
        if not documents:
            logger.warning(f"no_txt_content_found_in_file: {file_name}")
            return
        logger.info(f"load_success_txt_snippet: {len(documents)}")
        # 处理文档
        process_doc(task_id, thread_lock, task_progress, documents, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)
    except Exception as e:
        logger.error(f"load_file_fail_err, {file_name}, {e}", exc_info=True)

def search_txt(txt: str, vector_db_dir: str, score_threshold: float,
        sys_cfg: dict, txt_num: int) -> str:
    """
    :param txt: the query text
    :param vector_db_dir: the directory to save the vector db
    :param score_threshold: the score threshold
    :param sys_cfg: system configuration info.
    :param txt_num: the number of txt to return
    :return: the results
    """
    search_results = search_similar_text(txt, score_threshold, vector_db_dir, sys_cfg, txt_num)
    all_txt = ""
    for s_r in search_results:
        s_r_txt = s_r[0].page_content.replace("\n", "")
        if "......................." in s_r_txt:
            continue
        # logger.info(f"s_r_txt: {s_r_txt}, score: {s_r[1]}, from_file: {s_r[0].metadata['source']}")
        all_txt += s_r_txt + "\n"
    return all_txt

if __name__ == "__main__":
    os.environ["NO_PROXY"] = "*"  # 禁用代理
    my_cfg = init_yml_cfg()
    my_vector_db_dir = "./faiss_oa_vector"
