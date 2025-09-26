#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install python-docx chromadb
通过调用远程的 embedding API，将本地文档向量化，形成矢量数据库(Chroma)文件，用于进行向量检索
for OpenAI compatible remote API
通过将大文档分为多个批次，实时输出向量化进度，对于大批量文档的向量化比较友好
"""
import threading
import time
import os
import httpx
import chromadb
import logging.config
import numpy as np
from typing import Any, Optional
from langchain_community.document_loaders import (
    TextLoader, UnstructuredPDFLoader, UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from openai import OpenAI
from sys_init import init_yml_cfg
from tqdm import tqdm
from chromadb import Documents, EmbeddingFunction, Embeddings
from chromadb.api.types import QueryResult

from vdb_meta_util import VdbMeta

# 配置日志
logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class RemoteChromaEmbedder(EmbeddingFunction):
    """Chroma兼容的远程嵌入适配器"""
    def __init__(self, client: OpenAI, model_name: str, *args: Any, **kwargs: Any):
        self.client = client
        self.model_name = model_name
        # super().__init__(*args, **kwargs)

    def __call__(self, doc: Documents) -> Embeddings:
        """批量获取文本嵌入向量"""
        batch_size = 32
        embeddings = []
        for i in range(0, len(doc), batch_size):
            batch = doc[i:i+batch_size]
            resp = self.client.embeddings.create(
                model=self.model_name,
                input=batch
            )
            embeddings.extend([
                np.array(item.embedding, dtype=np.float32)
                for item in resp.data
            ])
        return embeddings

    def name(self) -> str:  # 关键修改：去掉@property装饰器
        return f"RemoteChromaEmbedder({self.model_name})"

    @classmethod
    def build_from_config(cls, config: dict[str, Any]) -> "RemoteChromaEmbedder":
        return cls(client=config["client"], model_name=config["model_name"])

    def get_config(self) -> dict[str, Any]:
        return {"client": self.client, "model_name": self.model_name}


def process_doc_with_id(file_id: int, documents: list[Document], vector_db: str,
        llm_cfg: dict, chunk_size=300, chunk_overlap=80, batch_size=10, separators=None) -> None:
    """处理文档并构建向量数据库"""
    if separators is None:
        separators = ['。', '！', '？', '；', '...', '、', '，']
    pbar = None
    try:
        doc_sources = [doc.metadata['source'] for doc in documents]
        logger.info(f"load_documents_size, {len(documents)}:\n" + "\n".join(f"- {src}" for src in doc_sources))
        VdbMeta.update_vdb_file_process_info(file_id, "开始对文本进行分片")
        if not separators:
            separators = ['。', '！', '？', '；', '...', '、', '，']
        logger.info(f"splitting_documents_with_separators {separators}...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            keep_separator=False
        )
        doc_list = text_splitter.split_documents(documents)
        # 创建Chroma客户端
        chroma_client = chromadb.PersistentClient(path=vector_db)
        openai_client = build_client(llm_cfg)
        embed_model = RemoteChromaEmbedder(openai_client, llm_cfg['embedding_model_name'])

        collection = chroma_client.get_or_create_collection(
            name="knowledge_base",
            embedding_function=embed_model,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )

        # 准备文档数据
        all_doc_ids = []
        all_metadata = []
        all_documents = []

        for i, chunk in enumerate(doc_list):
            doc_id = f"{os.path.basename(chunk.metadata['source'])}_chunk_{i}"
            all_doc_ids.append(doc_id)
            all_metadata.append(chunk.metadata)
            all_documents.append(chunk.page_content)

        # 批量添加文档
        logger.info(f"开始向量化 {len(all_doc_ids)} chunks (batch_size={batch_size})")
        VdbMeta.update_vdb_file_process_info(file_id, "开始对文本片段进行向量化")
        with tqdm(total=len(all_doc_ids), desc="文档向量化进度", unit="chunk") as pbar:
            for i in range(0, len(all_doc_ids), batch_size):
                batch_ids = all_doc_ids[i:i+batch_size]
                batch_metas = all_metadata[i:i+batch_size]
                batch_texts = all_documents[i:i+batch_size]
                try:
                    collection.upsert(
                        ids=batch_ids,
                        documents=batch_texts,
                        metadatas=batch_metas
                    )
                    pbar.update(len(batch_ids))
                    percent = round(100 * i / len(all_doc_ids), 1)
                    VdbMeta.update_vdb_file_process_info(
                        file_id,
                        f"已处理 {min(i+batch_size, len(all_doc_ids))}/{len(all_doc_ids)} 个分块",
                        percent
                    )
                except Exception as e:
                    info = f"处理批次 {i}-{i+batch_size} 时出错: {str(e)}"
                    VdbMeta.update_vdb_file_process_info(file_id, info)
                    logger.error(info)
                    continue

        logger.info(f"向量数据库构建完成，保存到 {vector_db}")
        VdbMeta.update_vdb_file_process_info(file_id, "向量化已完成，保存至个人知识空间")
    except Exception as e:
        info = f"处理文档时发生错误: {str(e)}"
        VdbMeta.update_vdb_file_process_info(file_id, info)
        logger.error(info, exc_info=True)
        raise
    finally:
        if pbar and not pbar.disable:
            pbar.close()

def build_client(llm_cfg: dict) -> OpenAI:
    """创建OpenAI兼容客户端"""
    return OpenAI(
        base_url=llm_cfg['llm_api_uri'],
        api_key=llm_cfg['llm_api_key'],
        http_client=httpx.Client(
            verify=False,
            timeout=httpx.Timeout(30.0)
        ),
    )

def vector_file_with_id(file_id: int, file_name: str, vector_db: str, llm_cfg: dict, chunk_size=300, chunk_overlap=80,
        batch_size=10, separators = None) -> None:
    """
    处理单个文档文件并添加到向量数据库
    :param file_id: 待处理文档在数据库中的唯一标识
    :param file_name: 文档的绝对路径
    :param vector_db: 向量数据库的绝对路径
    :param llm_cfg: 语言模型配置
    :param chunk_size: 文本分割的最大长度
    :param chunk_overlap: 文本分割的重叠长度
    :param batch_size: 批量处理的文档数量
    :param separators: 文本分割的分隔符
    """
    abs_path = os.path.abspath(file_name)
    if not os.path.exists(abs_path):
        info = f"文件在文件系统中不存在"
        VdbMeta.update_vdb_file_process_info(file_id, info)
        return
    try:
        logger.info(f"start_process_doc, {abs_path}")
        VdbMeta.update_vdb_file_process_info(file_id, "开始处理文档")
        file_type = os.path.splitext(abs_path)[-1].lower().lstrip('.')
        loader_mapping = {
            "txt": lambda f: TextLoader(f, encoding='utf8'),
            "pdf": lambda f: UnstructuredPDFLoader(f, encoding='utf8'),
            "docx": lambda f: UnstructuredWordDocumentLoader(f),
        }
        if file_type not in loader_mapping:
            logger.error(f"Unsupported_file_type: {file_type}")
            VdbMeta.update_vdb_file_process_info(file_id, "该文档的文件类型暂不支持")
            return
        loader = loader_mapping[file_type](abs_path)
        documents: list[Document] = loader.load()
        if not documents:
            logger.warning(f"no_txt_content_found_in_file: {abs_path}")
            VdbMeta.update_vdb_file_process_info(file_id, "该文档中未发现有效的文本内容")
            return
        # 确保有source元数据
        for doc in documents:
            if 'source' not in doc.metadata:
                doc.metadata['source'] = abs_path
        logger.info(f"load_success_txt_snippet: {len(documents)}")
        VdbMeta.update_vdb_file_process_info(file_id, f"已经检测到 {len(documents)} 个文本片段")
        process_doc_with_id(file_id, documents, vector_db, llm_cfg, chunk_size, chunk_overlap, batch_size, separators)

    except Exception as e:
        logger.error(f"load_file_fail_err, {abs_path}, {e}", exc_info=True)


def del_doc(file_path: str, vector_db: str) -> bool:
    """
    删除指定文档的所有向量片段
    :param file_path: 文档的绝对路径
    :param vector_db: 向量数据库的绝对路径
    """
    # 获取绝对路径用于匹配
    abs_path = os.path.abspath(file_path)
    try:
        chroma_client = chromadb.PersistentClient(path=vector_db)
        collection = chroma_client.get_collection("knowledge_base")
        # 先查询匹配文档
        results = collection.get(where={"source": abs_path})

        if not results['ids']:
            logger.warning(f"no_documents_found_for_source: {abs_path}")
            return False
        # 删除所有匹配项
        collection.delete(ids=results['ids'])
        logger.info(f"deleted_chunks_for_document, {abs_path}, collection_size {len(results['ids'])}")
        return True
    except Exception as e:
        logger.error(f"delete_doc_err: {str(e)}, {abs_path}", exc_info=True)
        return False

def update_doc(task_id: int, thread_lock, task_progress: dict, prev_file_path: str, cur_file_path: str,
               vector_db: str, llm_cfg: dict) -> None:
    """更新文档：先删除旧内容再添加新内容"""
    # 先删除旧内容
    with thread_lock:
        task_progress[task_id] = {"text": "开始删除旧版本文档", "timestamp": time.time()}
    if del_doc(prev_file_path, vector_db):
        with thread_lock:
            task_progress[task_id] = {"text": "已删除旧版本文档", "timestamp": time.time()}
    # 再重新添加文档
    vector_file_with_id(task_id, cur_file_path, vector_db, llm_cfg)


def load_vdb(vector_db: str, llm_cfg: dict) -> Optional[chromadb.Collection]:
    """加载Chroma矢量数据库集合"""
    if not os.path.exists(vector_db):
        logger.info(f"vector_db_dir_not_exists_return_none, {vector_db}")
        return None

    try:
        chroma_client = chromadb.PersistentClient(path=vector_db)
        openai_client = build_client(llm_cfg)
        embed_model = RemoteChromaEmbedder(openai_client, llm_cfg['embedding_model_name'])

        return chroma_client.get_collection(
            name="knowledge_base",
            embedding_function=embed_model
        )
    except Exception as e:
        logger.error(f"加载向量数据库失败: {str(e)}", exc_info=True)
        return None


def search(query: str, score_threshold: float, vector_db: str,llm_cfg: dict, top_k=3) -> list[dict]:
    """相似度搜索并返回格式化结果"""
    collection = load_vdb(vector_db, llm_cfg)
    if not collection:
        logger.info(f"vdb_collection_null_return_empty_list_for_q, {query}")
        return []

    # 使用远程embedding获取查询向量
    openai_client = build_client(llm_cfg)
    embedder = RemoteChromaEmbedder(openai_client, llm_cfg['embedding_model_name'])
    query_embedding = embedder([query])[0]

    # 执行查询
    results: QueryResult = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    # 处理结果并计算相似度分数
    formatted_results = []
    for i in range(len(results['ids'][0])):
        doc_id = results['ids'][0][i]
        content = results['documents'][0][i]
        metadata = results['metadatas'][0][i]
        distance = results['distances'][0][i]

        # 将距离转换为相似度分数 (1-距离)
        similarity_score = max(0.0, min(1.0, 1.0 - distance))

        if similarity_score >= score_threshold:
            formatted_results.append({
                "id": doc_id,
                "content": content,
                "metadata": metadata,
                "score": similarity_score
            })
    # 按分数降序排序
    return sorted(formatted_results, key=lambda x: x["score"], reverse=True)

def search_txt(txt: str, vector_db_dir: str, score_threshold: float,
        llm_cfg: dict, txt_num: int) -> str:
    """
    :param txt: the query text
    :param vector_db_dir: the directory to save the vector db
    :param score_threshold: the score threshold
    :param llm_cfg: llm configuration info in system config.
    :param txt_num: the number of txt to return
    :return: the results
    """
    search_results = search(txt, score_threshold, vector_db_dir, llm_cfg, txt_num)
    all_txt = ""
    for s_r in search_results:
        s_r_txt = s_r.get("content", "").replace("\n", "")
        if "......................." in s_r_txt:
            continue
        # logger.info(f"s_r_txt: {s_r_txt}, score: {s_r[1]}, from_file: {s_r[0].metadata['source']}")
        all_txt += s_r_txt + "\n"
    return all_txt

def test_search_txt():
    keywords = '安检率怎么样？'
    vector_db_dir="./vdb/332987902_q_desc_vdb"
    score_threshold = 0.1
    sys_cfg = init_yml_cfg()
    txt_num = 1
    result = search_txt(keywords, vector_db_dir, score_threshold, sys_cfg['api'], txt_num)
    logger.info(f"search_result: {result}")

def test_vector_file():
    os.environ["NO_PROXY"] = "*"  # 禁用代理
    my_cfg = init_yml_cfg()
    thread_lock = threading.Lock()
    task_id =int(time.time())
    task_progress = {}
    # file = "./llm.txt"
    file = "./hack/332987902_q_desc.txt"
    VdbMeta.save_vdb_file_info(file, file, 123, 223, task_id, 'balabalayidadui')
    vdb = "./vdb/332987902_q_desc_vdb"
    llm_cfg = my_cfg['api']
    logger.info(f"vector_file({task_id}, {thread_lock}, {task_progress}, {file}, {vdb}, {llm_cfg})")
    vector_file_with_id(task_id, file, vdb, llm_cfg, 80, 10, 10,["\n"])

def test_del_doc():
    test_search_txt()
    file = "./1_pure.txt"
    vdb = "./vdb/test_db"
    logger.info(f"start del_doc {file}")
    del_doc(file, vdb)
    logger.info(f"finish del_doc {file}")
    test_search_txt()

def test_update_doc():
    thread_lock = threading.Lock()
    task_id = int(time.time())
    task_progress = {}
    # file = "./llm.txt"
    file = "./1_pure.txt"
    vdb = "./vdb/test_db"
    my_cfg = init_yml_cfg()
    llm_cfg = my_cfg['api']
    update_doc(task_id, thread_lock, task_progress, file, vdb, llm_cfg)

if __name__ == "__main__":
    test_vector_file()
    test_search_txt()
    # test_del_doc()
    # # test_update_doc()
    # test_search_txt()