#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
向量数据库模块
"""

from .types import (
    VectorDBConfig,
    EmbeddingConfig,
    IndexingConfig,
    SearchConfig,
    SearchResult,
    DocumentChunk,
    TaskProgress,
    VectorDBInfo,
    DistanceMetric,
    EmbeddingModel
)

from .embedder import (
    RemoteChromaEmbedder,
    EmbeddingClient,
    create_embedding_client
)

from .indexer import (
    DocumentLoader,
    DocumentIndexer
)

from .searcher import (
    VectorSearcher
)

from .manager import (
    VectorDBManager
)

from .utils import (
    validate_file_path,
    ensure_directory,
    get_file_hash,
    ProgressTracker
)

# 版本信息
__version__ = "1.0.0"
__author__ = "liuyngchng@hotmail.com"
__description__ = "向量数据库工具模块"


# 导出主要的工厂函数和工具函数
def create_vector_db_manager(
        vector_db_path: str,
        embedding_model: str,
        api_key: str,
        api_base: str,
        collection_name: str = "knowledge_base"
) -> VectorDBManager:
    """
    创建向量数据库管理器

    Args:
        vector_db_path: 向量数据库路径
        embedding_model: 嵌入模型名称
        api_key: API密钥
        api_base: API基础URL
        collection_name: 集合名称

    Returns:
        向量数据库管理器实例
    """
    vector_db_config = VectorDBConfig(
        path=vector_db_path,
        collection_name=collection_name
    )

    embedding_config = EmbeddingConfig(
        model_name=embedding_model,
        api_key=api_key,
        api_base=api_base
    )

    return VectorDBManager(vector_db_config, embedding_config)


def search(
        query: str,
        vector_db_path: str,
        embedding_model: str,
        api_key: str,
        api_base: str,
        score_threshold: float = 0.5,
        top_k: int = 3
) -> list[dict]:
    """
    快速搜索函数（向后兼容）

    Args:
        query: 查询文本
        vector_db_path: 向量数据库路径
        embedding_model: 嵌入模型名称
        api_key: API密钥
        api_base: API基础URL
        score_threshold: 相似度阈值
        top_k: 返回数量

    Returns:
        搜索结果列表
    """
    manager = create_vector_db_manager(
        vector_db_path=vector_db_path,
        embedding_model=embedding_model,
        api_key=api_key,
        api_base=api_base
    )

    return manager.search(query, score_threshold, top_k)


def search_txt(
        txt: str,
        vector_db_path: str,
        embedding_model: str,
        api_key: str,
        api_base: str,
        score_threshold: float = 0.5,
        txt_num: int = 3
) -> str:
    """
    快速文本搜索函数（向后兼容）

    Args:
        txt: 查询文本
        vector_db_path: 向量数据库路径
        embedding_model: 嵌入模型名称
        api_key: API密钥
        api_base: API基础URL
        score_threshold: 相似度阈值
        txt_num: 返回文本数量

    Returns:
        拼接的文本结果
    """
    manager = create_vector_db_manager(
        vector_db_path=vector_db_path,
        embedding_model=embedding_model,
        api_key=api_key,
        api_base=api_base
    )

    return manager.search_text(txt, score_threshold, txt_num)


__all__ = [
    # 配置类
    "VectorDBConfig",
    "EmbeddingConfig",
    "IndexingConfig",
    "SearchConfig",

    # 数据类型
    "SearchResult",
    "DocumentChunk",
    "TaskProgress",
    "VectorDBInfo",
    "DistanceMetric",
    "EmbeddingModel",

    # 组件类
    "RemoteChromaEmbedder",
    "EmbeddingClient",
    "DocumentLoader",
    "DocumentIndexer",
    "VectorSearcher",
    "VectorDBManager",

    # 工具函数
    "validate_file_path",
    "ensure_directory",
    "get_file_hash",
    "ProgressTracker",
    "create_embedding_client",

    # 工厂函数
    "create_vector_db_manager",

    # 快捷函数
    "search",
    "search_txt",
]