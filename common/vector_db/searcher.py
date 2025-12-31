#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
向量检索功能
"""
import threading
from typing import List, Dict, Any, Optional, Union
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

import chromadb

from .types import (
    VectorDBConfig, EmbeddingConfig, SearchConfig,
    SearchResult, DistanceMetric
)
from .embedder import EmbeddingClient
from .utils import ensure_directory

logger = logging.getLogger(__name__)


class VectorSearcher:
    """向量检索器"""

    def __init__(
            self,
            vector_db_config: VectorDBConfig,
            embedding_config: EmbeddingConfig
    ):
        self.vector_db_config = vector_db_config
        self.embedding_config = embedding_config

        # 确保目录存在
        ensure_directory(vector_db_config.path)

        # 客户端
        self._embedding_client: Optional[EmbeddingClient] = None
        self._chroma_client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None

        # 线程安全
        self._lock = threading.Lock()

        # 缓存
        self._query_cache = {}

        logger.info(f"向量检索器初始化: {vector_db_config.path}")

    @property
    def embedding_client(self) -> EmbeddingClient:
        """获取嵌入客户端"""
        if self._embedding_client is None:
            with self._lock:
                if self._embedding_client is None:
                    from .embedder import create_embedding_client
                    self._embedding_client = create_embedding_client(self.embedding_config)
        return self._embedding_client

    @property
    def chroma_client(self) -> chromadb.PersistentClient:
        """获取Chroma客户端"""
        if self._chroma_client is None:
            with self._lock:
                if self._chroma_client is None:
                    self._chroma_client = chromadb.PersistentClient(
                        path=self.vector_db_config.path,
                        settings=chromadb.Settings(
                            **self.vector_db_config.to_chroma_settings()
                        )
                    )
        return self._chroma_client

    @property
    def collection(self) -> chromadb.Collection:
        """获取向量集合"""
        if self._collection is None:
            with self._lock:
                if self._collection is None:
                    try:
                        self._collection = self.chroma_client.get_collection(
                            name=self.vector_db_config.collection_name,
                            embedding_function=self.embedding_client.embedder
                        )
                    except Exception as e:
                        logger.error(f"获取集合失败: {e}")
                        raise ValueError(f"向量集合不存在: {self.vector_db_config.collection_name}")
        return self._collection

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _get_query_embedding(self, query: str) -> List[float]:
        """获取查询向量"""
        try:
            # 检查缓存
            cache_key = hash(query)
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]

            # 获取嵌入向量
            embedding = self.embedding_client.embed_text(query)

            # 缓存结果
            self._query_cache[cache_key] = embedding
            return embedding

        except Exception as e:
            logger.error(f"获取查询向量失败: '{query[:50]}...', 错误: {e}")
            raise

    def search(
            self,
            query: str,
            search_config: Optional[SearchConfig] = None
    ) -> List[SearchResult]:
        """
        执行向量检索

        Args:
            query: 查询文本
            search_config: 搜索配置

        Returns:
            检索结果列表
        """
        # 参数验证
        if not query or not isinstance(query, str) or not query.strip():
            logger.warning("收到空查询")
            return []

        # 使用默认配置或提供的配置
        config = search_config or SearchConfig()

        # 验证阈值
        if config.score_threshold < 0 or config.score_threshold > 1:
            logger.warning(f"阈值 {config.score_threshold} 无效，使用默认值 0.5")
            config.score_threshold = 0.5

        try:
            # 获取查询向量
            query_embedding = self._get_query_embedding(query)

            # 构建查询参数
            include_fields = ["documents", "distances", "ids"]
            if config.include_metadata:
                include_fields.append("metadatas")

            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": min(config.top_k, 100),  # 限制最大返回数
                "include": include_fields
            }

            # 添加过滤条件
            if config.filter_conditions:
                query_params["where"] = config.filter_conditions

            # 执行查询
            results = self.collection.query(**query_params)

            # 处理结果
            search_results = []
            if results.get('ids') and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    # 计算相似度分数
                    distance = results['distances'][0][i]
                    similarity_score = self._distance_to_score(distance)

                    # 应用阈值过滤
                    if similarity_score >= config.score_threshold:
                        result = SearchResult(
                            id=results['ids'][0][i],
                            content=results['documents'][0][i],
                            score=similarity_score,
                            distance=distance if config.include_distances else None
                        )

                        # 添加元数据
                        if config.include_metadata and results.get('metadatas'):
                            result.metadata = results['metadatas'][0][i]

                        search_results.append(result)

            # 按分数排序
            search_results.sort(key=lambda x: x.score, reverse=True)

            logger.debug(
                f"检索完成: '{query[:30]}...', "
                f"阈值: {config.score_threshold}, "
                f"结果数: {len(search_results)}"
            )

            return search_results

        except Exception as e:
            logger.error(f"检索失败: '{query[:30]}...', 错误: {e}")
            return []

    def search_with_text(
            self,
            query: str,
            score_threshold: float = 0.5,
            top_k: int = 3,
            filter_patterns: Optional[List[str]] = None
    ) -> str:
        """
        检索并返回拼接的文本

        Args:
            query: 查询文本
            score_threshold: 相似度阈值
            top_k: 返回数量
            filter_patterns: 过滤模式列表

        Returns:
            拼接的文本结果
        """
        # 构建搜索配置
        search_config = SearchConfig(
            score_threshold=score_threshold,
            top_k=top_k,
            include_metadata=False
        )

        # 执行搜索
        results = self.search(query, search_config)

        if not results:
            return ""

        # 过滤和拼接文本
        texts = []
        filter_patterns = filter_patterns or ["......................."]

        for result in results:
            content = result.content.replace("\n", " ").strip()

            # 应用过滤规则
            if any(pattern in content for pattern in filter_patterns):
                continue

            texts.append(content)

        return "\n".join(texts)

    def batch_search(
            self,
            queries: List[str],
            search_config: Optional[SearchConfig] = None
    ) -> List[List[SearchResult]]:
        """
        批量检索

        Args:
            queries: 查询文本列表
            search_config: 搜索配置

        Returns:
            每个查询的检索结果列表
        """
        all_results = []

        for query in queries:
            results = self.search(query, search_config)
            all_results.append(results)

        return all_results

    def search_by_embedding(
            self,
            query_embedding: List[float],
            search_config: Optional[SearchConfig] = None
    ) -> List[SearchResult]:
        """
        使用现有嵌入向量进行搜索

        Args:
            query_embedding: 查询向量
            search_config: 搜索配置

        Returns:
            检索结果列表
        """
        config = search_config or SearchConfig()

        try:
            include_fields = ["documents", "distances", "ids"]
            if config.include_metadata:
                include_fields.append("metadatas")

            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": min(config.top_k, 100),
                "include": include_fields
            }

            if config.filter_conditions:
                query_params["where"] = config.filter_conditions

            results = self.collection.query(**query_params)

            search_results = []
            if results.get('ids') and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    distance = results['distances'][0][i]
                    similarity_score = self._distance_to_score(distance)

                    if similarity_score >= config.score_threshold:
                        result = SearchResult(
                            id=results['ids'][0][i],
                            content=results['documents'][0][i],
                            score=similarity_score,
                            distance=distance if config.include_distances else None
                        )

                        if config.include_metadata and results.get('metadatas'):
                            result.metadata = results['metadatas'][0][i]

                        search_results.append(result)

            search_results.sort(key=lambda x: x.score, reverse=True)
            return search_results

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []

    @staticmethod
    def _distance_to_score(distance: float) -> float:
        """距离转相似度分数"""
        # Chroma 默认使用余弦距离: distance = 1 - cosine_similarity
        # 所以 similarity_score = 1 - distance
        score = 1.0 - distance

        # 确保分数在 [0, 1] 范围内
        return max(0.0, min(1.0, score))

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            collection = self.collection
            count = collection.count()

            return {
                "name": self.vector_db_config.collection_name,
                "total_chunks": count,
                "path": self.vector_db_config.path,
                "distance_metric": self.vector_db_config.distance_metric.value
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}

    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._query_cache.clear()

    def close(self):
        """关闭资源"""
        with self._lock:
            if self._embedding_client:
                self._embedding_client.close()
                self._embedding_client = None

            self._chroma_client = None
            self._collection = None
            self._query_cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()