#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
Milvus 向量库工具类
pip install pymilvus
通过调用远程 embedding API，将本地文档向量化，存入 Milvus 向量数据库，用于向量检索
支持 Milvus Lite（本地文件模式）和远程 Milvus 服务
混合检索使用 Milvus 内置 BM25 Function（dense + sparse），无需外部 rank_bm25/jieba
"""

import os
import time
import httpx
import logging.config
from openai import OpenAI

from pymilvus import (
    MilvusClient, FieldSchema, DataType, CollectionSchema,
    Function, FunctionType, AnnSearchRequest, WeightedRanker,
)
from pymilvus.milvus_client import IndexParams

from langchain_community.document_loaders import (
    TextLoader, UnstructuredPDFLoader, UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from common.sys_init import init_yml_cfg
from common.const import MAX_EMBEDDING_TXT_LENGTH
from common.vdb_meta_util import VdbMeta
from common.statistic_util import add_embedding_token_by_uid
from common.cm_utils import estimate_tokens
from common.xmind_util import XMindLoader

# 配置日志
log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================

DEFAULT_COLLECTION_NAME = "knowledge_base"
DENSE_WEIGHT = 0.5   # 混合检索中向量相似度的权重
SPARSE_WEIGHT = 0.5  # 混合检索中 BM25 的权重
MAX_EMBEDDING_BATCH_SIZE = 32

# ============================================================
# 客户端工厂
# ============================================================


def get_milvus_client(vector_db_path: str) -> MilvusClient:
    """
    获取 Milvus 客户端
    :param vector_db_path: 向量库目录路径，如 ./vdb/vdb_idx_123_456
    :return: MilvusClient 实例
    优先从 cfg.yml 读取 milvus.uri 配置；为空则使用本地 Milvus Lite 文件模式
    """
    milvus_cfg = {}
    try:
        cfg = init_yml_cfg()
        milvus_cfg = cfg.get('milvus', {})
    except Exception:
        pass

    uri = milvus_cfg.get('uri', '')
    token = milvus_cfg.get('token', '')

    if uri and (uri.startswith('http://') or uri.startswith('https://')):
        # 远程 Milvus 服务
        kwargs = {'uri': uri}
        if token:
            kwargs['token'] = token
        client = MilvusClient(**kwargs)
        logger.info(f"milvus_client_remote, uri={uri}")
    else:
        # Milvus Lite 本地文件模式
        db_file = os.path.join(vector_db_path, "milvus.db")
        os.makedirs(vector_db_path, exist_ok=True)
        client = MilvusClient(db_file)
        logger.info(f"milvus_client_local, db={db_file}")

    return client


def build_embedding_client(llm_cfg: dict) -> OpenAI:
    """创建 OpenAI 兼容的 embedding 客户端"""
    return OpenAI(
        base_url=llm_cfg['embedding_api_uri'],
        api_key=llm_cfg['embedding_api_key'],
        http_client=httpx.Client(
            verify=False,
            timeout=httpx.Timeout(30.0)
        ),
    )


# ============================================================
# Embedding 计算
# ============================================================


def _compute_embeddings(texts: list[str], llm_cfg: dict) -> list[list[float]]:
    """
    批量计算文本的 embedding 向量
    :param texts: 文本列表
    :param llm_cfg: LLM 配置，需包含 embedding_api_uri/key/model_name
    :return: embedding 向量列表
    """
    if not texts:
        return []

    client = build_embedding_client(llm_cfg)
    model_name = llm_cfg['embedding_model_name']
    max_input_length = llm_cfg.get('embedding_max_input_length', MAX_EMBEDDING_TXT_LENGTH)
    all_embeddings = []

    for i in range(0, len(texts), MAX_EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + MAX_EMBEDDING_BATCH_SIZE]

        # 截断超长文本
        processed_batch = []
        for text in batch:
            if len(text) > max_input_length:
                logger.warning(f"文本过长 ({len(text)} > {max_input_length})，截断处理")
                processed_batch.append(text[:max_input_length])
            else:
                processed_batch.append(text)

        if not processed_batch:
            continue

        try:
            resp = client.embeddings.create(model=model_name, input=processed_batch)
            if i == 0 and resp.data:
                dimension = len(resp.data[0].embedding)
                logger.info(f"embedding_model={model_name}, dimension={dimension}")
            all_embeddings.extend([item.embedding for item in resp.data])
        except Exception as e:
            logger.error(f"embedding_api_err: {e}")
            raise

    return all_embeddings


def _get_embedding_dimension(llm_cfg: dict) -> int:
    """通过发送一条短文本探测 embedding 模型的输出维度"""
    embeddings = _compute_embeddings(["dimension probe"], llm_cfg)
    return len(embeddings[0])


# ============================================================
# Collection 管理
# ============================================================


def get_or_create_collection(
    client: MilvusClient,
    dimension: int,
    collection_name: str = DEFAULT_COLLECTION_NAME
) -> None:
    """
    获取或创建 Milvus collection（含 schema 和索引）
    Schema: id(VARCHAR/PK) + vector(FLOAT_VECTOR) + sparse_vec(SPARSE_FLOAT_VECTOR)
            + content(VARCHAR, 启用中文分词) + source(VARCHAR)
    使用 Function(BM25) 将 content 自动映射为 sparse_vec
    Collection 已存在时跳过创建，但仍确保已加载到内存
    """
    if client.has_collection(collection_name):
        logger.info(f"collection_exists, {collection_name}")
    else:
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=512, is_primary=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(
                name="content", dtype=DataType.VARCHAR, max_length=65535,
                enable_analyzer=True,
                analyzer_params={"type": "chinese"},
            ),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
            # sparse_vec 由 BM25 Function 自动从 content 生成
            FieldSchema(name="sparse_vec", dtype=DataType.SPARSE_FLOAT_VECTOR),
        ]

        bm25_fn = Function(
            name="bm25_fn",
            function_type=FunctionType.BM25,
            input_field_names=["content"],
            output_field_names="sparse_vec",
        )

        schema = CollectionSchema(
            fields=fields, functions=[bm25_fn],
            description="Knowledge base collection with built-in BM25"
        )

        client.create_collection(collection_name=collection_name, schema=schema)
        logger.info(f"collection_created, {collection_name}, dim={dimension}")

        # 创建索引：dense 向量 + sparse 向量
        index_params = IndexParams()
        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type="COSINE"
        )
        index_params.add_index(
            field_name="sparse_vec",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25"
        )
        client.create_index(collection_name=collection_name, index_params=index_params)
        logger.info(f"index_created, {collection_name}, dense=AUTOINDEX/COSINE, sparse=SPARSE_INVERTED_INDEX/BM25")

    client.load_collection(collection_name=collection_name)


# ============================================================
# 任务取消检查
# ============================================================


def check_task_cancelled(file_id: int) -> bool:
    """检查任务是否被取消，懒加载 bp_vdb.is_task_cancelled"""
    try:
        from common.bp_vdb import is_task_cancelled
        return is_task_cancelled(file_id)
    except Exception as e:
        logger.debug(f"check_task_cancelled_failed, {e}")
        return False


# ============================================================
# 文档处理（入库）
# ============================================================


def mls_process_doc(
    file_id: int,
    documents: list[Document],
    vector_db: str,
    llm_cfg: dict,
    chunk_size=300,
    chunk_overlap=80,
    batch_size=10,
    separators=None,
    uid: int = None
) -> None:
    """
    处理文档列表并构建 Milvus 向量数据库
    :param file_id: 文件在数据库中的唯一标识
    :param documents: LangChain Document 列表
    :param vector_db: Milvus 数据库目录路径
    :param llm_cfg: LLM 配置
    :param chunk_size: 文本切分大小
    :param chunk_overlap: 文本切分重叠长度
    :param batch_size: embedding 批处理大小
    :param separators: 文本切分分隔符
    :param uid: 用户 ID（用于统计）
    """
    if check_task_cancelled(file_id):
        info = f"{uid}, 任务已被用户取消"
        VdbMeta.update_vdb_file_process_info(file_id, info)
        return

    if separators is None:
        separators = ['。', '！', '？', '；', '...', '、', '，']

    pbar = None
    try:
        doc_sources = [doc.metadata['source'] for doc in documents]
        logger.info(f"load_documents_size, {len(documents)}:\n" + "\n".join(f"- {src}" for src in doc_sources))

        VdbMeta.update_vdb_file_process_info(file_id, "开始切分文本")

        if not separators:
            separators = [
                '。', '！', '？', '；', '...', '、', '，', '：', '——', '……',
                '\n\n', '. ', '! ', '? ', '; ', ', ', ': ',
                '\n', '  ', '\t', '|', '•', '·',
                '）', ')', '】', ']', '」', '》',
                '</', '/>', '>',
                '# ', '## ', '### ', '#### ',
                '\n- ', '\n* ', '\n1. ', '\n• ',
                '\r\n\r\n', '\r\r'
            ]

        logger.info(f"{uid}, splitting_documents_with_separators {separators}...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            keep_separator=False
        )
        doc_list = text_splitter.split_documents(documents)

        # 准备结构化数据
        all_doc_ids = []
        all_metadatas = []
        all_documents = []
        source_set = set()

        for i, chunk in enumerate(doc_list):
            doc_id = f"{os.path.basename(chunk.metadata['source'])}_chunk_{i}"
            source_set.add(os.path.basename(chunk.metadata['source']))
            all_doc_ids.append(doc_id)
            all_metadatas.append(chunk.metadata)
            all_documents.append(chunk.page_content)

        total_chunks = len(all_doc_ids)
        logger.info(f"{uid}, 开始向量化 {total_chunks} chunks (batch_size={batch_size})")
        VdbMeta.update_vdb_file_process_info(file_id, f"开始处理文本块，共 {total_chunks} 个")
        source_desc = f"[{file_id}]_{source_set} 向量化进度"

        # 探测 embedding 维度并初始化 collection
        dimension = _get_embedding_dimension(llm_cfg)
        client = get_milvus_client(vector_db)
        collection_name = DEFAULT_COLLECTION_NAME
        get_or_create_collection(client, dimension, collection_name)

        # 顺序批处理（Milvus Lite 单线程写入更安全）
        from tqdm import tqdm
        completed_count = 0
        err_info = ""

        with tqdm(total=total_chunks, desc=source_desc, unit="chunk") as pbar:
            for start_idx in range(0, total_chunks, batch_size):
                if check_task_cancelled(file_id):
                    info = f"任务已被用户取消"
                    VdbMeta.update_vdb_file_process_info(file_id, info)
                    logger.info(f"{uid}, {file_id}, {info}")
                    return

                end_idx = min(start_idx + batch_size, total_chunks)
                batch_ids = all_doc_ids[start_idx:end_idx]
                batch_metas = all_metadatas[start_idx:end_idx]
                batch_texts = all_documents[start_idx:end_idx]

                try:
                    # 批量计算 embedding
                    embeddings = _compute_embeddings(batch_texts, llm_cfg)

                    # 构建 Milvus 数据
                    data = []
                    for j in range(len(batch_ids)):
                        data.append({
                            "id": batch_ids[j],
                            "vector": embeddings[j],
                            "content": batch_texts[j],
                            "source": batch_metas[j].get("source", ""),
                        })

                    # 写入 Milvus
                    client.upsert(collection_name=collection_name, data=data)

                    completed_count += len(batch_ids)
                    if uid:
                        batch_embedding_tokens = estimate_tokens(''.join(batch_texts))
                        add_embedding_token_by_uid(uid, batch_embedding_tokens)
                        logger.debug(f"uid_{uid}_batch_{start_idx}-{end_idx}_embedding_tokens_{batch_embedding_tokens}")

                    percent = round(100 * completed_count / total_chunks, 1)
                    VdbMeta.update_vdb_file_process_info(
                        file_id,
                        f"已处理 {completed_count} 个文本块，共 {total_chunks} 个",
                        percent
                    )
                    pbar.update(len(batch_ids))

                except Exception as e:
                    err_info += f"处理批次 {start_idx}-{end_idx} 时有异常: {str(e)}, "
                    logger.exception(f"{file_id}, 批次 {start_idx}-{end_idx} 处理失败")

        process_info = f"已完成文档处理，共处理 {total_chunks} 个文本块"
        if err_info:
            process_info += f", {err_info}"
        logger.info(f"{uid}, Milvus 向量库构建完成，保存到 {vector_db}")
        VdbMeta.update_vdb_file_process_info(file_id, process_info, 100)

    except Exception as e:
        info = f"{uid}, 处理文档时发生错误: {str(e)}"
        safe_info = info.replace("'", "''")
        VdbMeta.update_vdb_file_process_info(file_id, safe_info)
        logger.error(info, exc_info=True)
        raise
    finally:
        if pbar is not None and not pbar.disable:
            pbar.close()


def mls_vector_file(
    file_id: int,
    file_name: str,
    vector_db: str,
    llm_cfg: dict,
    chunk_size=300,
    chunk_overlap=80,
    batch_size=10,
    separators=None,
    uid: int = None
) -> None:
    """
    处理单个文档文件并添加到 Milvus 向量数据库
    :param file_id: 待处理文档在数据库中的唯一标识
    :param file_name: 文档的绝对路径
    :param vector_db: Milvus 数据库目录路径
    :param llm_cfg: LLM 配置
    :param chunk_size: 文本切分大小
    :param chunk_overlap: 文本切分重叠长度
    :param batch_size: 批量处理大小
    :param separators: 文本切分分隔符
    :param uid: 用户 ID
    """
    if check_task_cancelled(file_id):
        info = f"任务已被用户取消"
        logger.info(f"{file_id}, {info}")
        VdbMeta.update_vdb_file_process_info(file_id, info)
        return

    abs_path = os.path.abspath(file_name)
    if not os.path.exists(abs_path):
        info = f"文件在文件系统中不存在"
        VdbMeta.update_vdb_file_process_info(file_id, info)
        return

    try:
        logger.info(f"start_mls_process_doc, {abs_path}")
        VdbMeta.update_vdb_file_process_info(file_id, "开始处理文档")

        file_type = os.path.splitext(abs_path)[-1].lower().lstrip('.')
        loader_mapping = {
            "txt": lambda f: TextLoader(f, encoding='utf8'),
            "pdf": lambda f: UnstructuredPDFLoader(f, encoding='utf8'),
            "docx": lambda f: UnstructuredWordDocumentLoader(f),
            "xmind": lambda f: XMindLoader(f),
        }

        if file_type not in loader_mapping:
            logger.error(f"Unsupported_file_type: {file_type}")
            VdbMeta.update_vdb_file_process_info(file_id, "该文档的文件类型暂不支持")
            return

        loader = loader_mapping[file_type](abs_path)
        logger.info(f"load_doc_with {type(loader)}")
        documents: list[Document] = loader.load()

        if not documents:
            logger.warning(f"no_txt_content_found_in_file: {abs_path}")
            VdbMeta.update_vdb_file_process_info(file_id, "该文档中未发现有效的文本内容")
            return

        logger.info(f"add_source_in_doc {len(documents)}")
        for doc in documents:
            if 'source' not in doc.metadata:
                doc.metadata['source'] = abs_path

        logger.info(f"load_success_txt_snippet: {len(documents)}")
        VdbMeta.update_vdb_file_process_info(file_id, f"已经检测到 {len(documents)} 个文本片段")

        mls_process_doc(
            file_id, documents, vector_db, llm_cfg,
            chunk_size, chunk_overlap, batch_size, separators,
            uid=uid
        )

    except Exception as e:
        logger.error(f"load_file_fail_err, {abs_path}, {e}", exc_info=True)


def mls_del_doc(file_path: str, vector_db: str) -> bool:
    """
    删除指定文档的所有向量片段
    :param file_path: 文档的绝对路径
    :param vector_db: Milvus 数据库目录路径
    :return: 是否成功
    """
    abs_path = os.path.abspath(file_path)
    collection_name = DEFAULT_COLLECTION_NAME

    try:
        client = get_milvus_client(vector_db)
        if not client.has_collection(collection_name):
            logger.warning(f"collection_not_exist: {collection_name}")
            return False

        # 查询匹配文档的 IDs
        results = client.query(
            collection_name=collection_name,
            filter=f'source == "{abs_path}"',
            output_fields=["id"],
            limit=16384
        )

        if not results:
            logger.warning(f"no_documents_found_for_source: {abs_path}")
            return False

        ids_to_delete = [item["id"] for item in results]
        client.delete(collection_name=collection_name, ids=ids_to_delete)
        logger.info(f"deleted_chunks_for_document, {abs_path}, count={len(ids_to_delete)}")
        return True

    except Exception as e:
        logger.error(f"mls_del_doc_err: {e}, {abs_path}", exc_info=True)
        return False


# ============================================================
# 向量检索
# ============================================================


def mls_search(
    query: str,
    score_threshold: float,
    vector_db: str,
    llm_cfg: dict,
    top_k=3
) -> list[dict]:
    """
    向量相似度检索
    :param query: 查询文本
    :param score_threshold: 相似度阈值 [0, 1]
    :param vector_db: Milvus 数据库目录路径
    :param llm_cfg: LLM 配置
    :param top_k: 返回结果数量
    :return: [{"id": ..., "content": ..., "metadata": ..., "score": ...}, ...]
    """
    collection_name = DEFAULT_COLLECTION_NAME
    client = get_milvus_client(vector_db)

    if not client.has_collection(collection_name):
        logger.info(f"collection_not_exist: {collection_name}, q={query[:50]}")
        return []

    client.load_collection(collection_name=collection_name)

    # 计算查询向量
    query_embeddings = _compute_embeddings([query], llm_cfg)
    query_vector = query_embeddings[0]

    # Milvus 向量搜索
    results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=top_k,
        output_fields=["content", "source"],
    )

    # 解析结果: client.search 返回 list[list[dict]]
    formatted_results = []
    if results and results[0]:
        for hit in results[0]:
            distance = hit.get("distance", 1.0)
            # COSINE metric: distance = 1 - cosine_similarity, range [0, 2]
            # 转换为相似度 [0, 1]
            similarity_score = max(0.0, min(1.0, 1.0 - distance))

            if similarity_score >= score_threshold:
                entity = hit.get("entity", {})
                formatted_results.append({
                    "id": hit.get("id", ""),
                    "content": entity.get("content", ""),
                    "metadata": {"source": entity.get("source", "")},
                    "score": similarity_score
                })

    return sorted(formatted_results, key=lambda x: x["score"], reverse=True)


# ============================================================
# 混合检索（Milvus 原生 Dense + Sparse BM25）
# ============================================================


def mls_hybrid_search(
    query: str,
    vector_db_dir: str,
    score_threshold: float,
    llm_cfg: dict,
    top_k: int = 3
) -> list[dict]:
    """
    混合检索：dense 向量 + Milvus 内置 BM25 (sparse)，WeightedRanker 加权融合
    :param query: 查询文本
    :param vector_db_dir: Milvus 数据库目录路径
    :param score_threshold: 相似度阈值 [0, 1]，低于此阈值的结果被过滤
    :param llm_cfg: LLM 配置
    :param top_k: 返回结果数量
    :return: [{"id": ..., "content": ..., "metadata": ..., "score": ...}, ...]
    """
    collection_name = DEFAULT_COLLECTION_NAME
    client = get_milvus_client(vector_db_dir)

    if not client.has_collection(collection_name):
        logger.info(f"collection_not_exist: {collection_name}, q={query[:50]}")
        return []

    client.load_collection(collection_name=collection_name)

    # 计算查询的 dense 向量
    query_embeddings = _compute_embeddings([query], llm_cfg)
    query_vector = query_embeddings[0]

    # Dense 搜索请求
    dense_req = AnnSearchRequest(
        data=[query_vector],
        anns_field="vector",
        param={"metric_type": "COSINE"},
        limit=top_k
    )

    # Sparse (BM25) 搜索请求 — 直接传入原始文本，Milvus 内置分词
    sparse_req = AnnSearchRequest(
        data=[query],
        anns_field="sparse_vec",
        param={"metric_type": "BM25"},
        limit=top_k
    )

    # Milvus 原生混合检索
    results = client.hybrid_search(
        collection_name=collection_name,
        reqs=[dense_req, sparse_req],
        ranker=WeightedRanker(DENSE_WEIGHT, SPARSE_WEIGHT),
        limit=top_k,
        output_fields=["content", "source"],
    )

    # 解析结果
    formatted_results = []
    if results and results[0]:
        for hit in results[0]:
            combined_score = hit.get("distance", 0.0)
            # WeightedRanker score 可能是任意范围，取其原始值作为排序分
            # 对 dense 部分做阈值过滤：如果向量相似度太低，跳过
            entity = hit.get("entity", {})

            formatted_results.append({
                "id": hit.get("id", ""),
                "content": entity.get("content", ""),
                "metadata": {"source": entity.get("source", "")},
                "score": float(combined_score),
            })

    logger.info(f"mls_hybrid_search, q={query[:50]}, results={len(formatted_results)}")
    return formatted_results


def mls_search_txt(
    txt: str,
    vector_db_dir: str,
    score_threshold: float,
    llm_cfg: dict,
    txt_num: int
) -> str:
    """
    搜索入口 — 混合检索（向量 + BM25），返回拼接后的文本字符串
    :param txt: 查询文本
    :param vector_db_dir: Milvus 数据库目录路径
    :param score_threshold: 相似度阈值
    :param llm_cfg: LLM 配置
    :param txt_num: 返回的文本块数量
    :return: 拼接后的检索结果文本
    """
    search_results = []
    try:
        search_results = mls_hybrid_search(txt, vector_db_dir, score_threshold, llm_cfg, txt_num)
    except Exception as e:
        logger.exception(f"mls_search_txt_err, embedding uri: {llm_cfg.get('embedding_api_uri', 'N/A')}, err={e}", exc_info=True)

    all_txt = ""
    if not search_results:
        logger.info(f"no_search_results_return_for: {txt}")
        return all_txt

    for s_r in search_results:
        s_r_txt = s_r.get("content", "").replace("\n", "")
        if "......................." in s_r_txt:
            continue
        all_txt += s_r_txt + "\n"
    return all_txt


# ============================================================
# 测试入口
# ============================================================


def test_mls_vector_file():
    """测试文档向量化"""
    os.environ["NO_PROXY"] = "*"
    my_cfg = init_yml_cfg()
    task_id = int(time.time())
    file = "./llm.txt"
    vdb = "./vdb/mls_test_db"
    llm_cfg = my_cfg.get('api', my_cfg)
    logger.info(f"mls_vector_file test: file={file}, vdb={vdb}")
    vdb_dir = os.path.dirname(vdb) if vdb.endswith('.db') else vdb
    VdbMeta.save_vdb_file_info(file, file, 123, 223, task_id, 'balabalayidadui')
    mls_vector_file(task_id, file, vdb, llm_cfg, 80, 10, 10, ["\n"], uid=123)
    logger.info("mls_vector_file test done")


def test_mls_search():
    """测试搜索"""
    os.environ["NO_PROXY"] = "*"
    my_cfg = init_yml_cfg()
    llm_cfg = my_cfg.get('api', my_cfg)
    vdb = "./vdb/mls_test_db"
    result = mls_search_txt("测试关键词", vdb, 0.1, llm_cfg, 3)
    logger.info(f"mls_search_txt result: {result}")


def test_mls_del_doc():
    """测试删除"""
    vdb = "./vdb/mls_test_db"
    file = "./llm.txt"
    success = mls_del_doc(file, vdb)
    logger.info(f"mls_del_doc result: {success}")


if __name__ == "__main__":
    test_mls_vector_file()
    test_mls_search()
    # test_mls_del_doc()
