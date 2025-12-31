#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
向量库数据类型定义
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union, Tuple
from enum import Enum
import time


class DistanceMetric(str, Enum):
    """距离度量类型"""
    COSINE = "cosine"
    EUCLIDEAN = "l2"
    INNER_PRODUCT = "ip"


class EmbeddingModel(str, Enum):
    """嵌入模型类型"""
    OPENAI = "openai"
    LOCAL = "local"
    REMOTE_API = "remote_api"


@dataclass
class VectorDBConfig:
    """向量数据库配置"""
    path: str
    collection_name: str = "knowledge_base"
    distance_metric: DistanceMetric = DistanceMetric.COSINE
    anonymized_telemetry: bool = False

    def to_chroma_settings(self) -> Dict[str, Any]:
        """转换为ChromaDB设置"""
        return {
            "anonymized_telemetry": self.anonymized_telemetry
        }


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""
    model_name: str
    api_key: str
    api_base: str
    embedding_type: EmbeddingModel = EmbeddingModel.REMOTE_API
    timeout: int = 30
    max_retries: int = 3
    batch_size: int = 32

    @property
    def is_openai_compatible(self) -> bool:
        """是否为OpenAI兼容API"""
        return self.embedding_type in [EmbeddingModel.OPENAI, EmbeddingModel.REMOTE_API]


@dataclass
class IndexingConfig:
    """索引构建配置"""
    chunk_size: int = 300
    chunk_overlap: int = 80
    batch_size: int = 10
    max_workers: int = 4
    separators: List[str] = field(default_factory=lambda:
    ['。', '！', '？', '；', '...', '、', '，'])
    keep_separator: bool = False


@dataclass
class SearchConfig:
    """搜索配置"""
    score_threshold: float = 0.5
    top_k: int = 3
    include_metadata: bool = True
    include_distances: bool = True
    filter_conditions: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    distance: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "content": self.content,
            "score": round(self.score, 4)
        }
        if self.metadata:
            result["metadata"] = self.metadata
        if self.distance is not None:
            result["distance"] = self.distance
        return result


@dataclass
class DocumentChunk:
    """文档分块"""
    id: str
    content: str
    metadata: Dict[str, Any]
    source_file: str
    chunk_index: int

    @classmethod
    def from_langchain_document(cls, document: Any, index: int) -> "DocumentChunk":
        """从LangChain Document对象创建"""
        source = document.metadata.get('source', 'unknown')
        doc_id = f"{source}_chunk_{index}"

        return cls(
            id=doc_id,
            content=document.page_content,
            metadata=document.metadata,
            source_file=source,
            chunk_index=index
        )


@dataclass
class TaskProgress:
    """任务进度"""
    task_id: int
    text: str
    percent: float = 0.0
    timestamp: float = field(default_factory=lambda: time.time())
    status: str = "running"  # running, completed, cancelled, failed

    def update(self, text: str, percent: float = None):
        """更新进度"""
        self.text = text
        if percent is not None:
            self.percent = percent
        self.timestamp = time.time()


@dataclass
class VectorDBInfo:
    """向量库信息"""
    path: str
    collection_name: str
    total_chunks: int = 0
    sources: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: time.time())
    last_updated: float = field(default_factory=lambda: time.time())


