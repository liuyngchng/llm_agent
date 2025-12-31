#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
嵌入模型相关功能
"""
import httpx
import numpy as np
from typing import List, Optional, Any, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from openai import OpenAI
from chromadb import EmbeddingFunction

from .types import EmbeddingConfig

logger = logging.getLogger(__name__)


class RemoteChromaEmbedder(EmbeddingFunction):
    """Chroma兼容的远程嵌入适配器"""

    def __init__(self, client: OpenAI, model_name: str, **kwargs):
        self.client = client
        self.model_name = model_name
        self._batch_size = kwargs.get('batch_size', 32)

    def __call__(self, inputs: List[str]) -> List[List[float]]:
        """批量获取文本嵌入向量"""
        embeddings = []

        for i in range(0, len(inputs), self._batch_size):
            batch = inputs[i:i + self._batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=batch
                )
                batch_embeddings = [
                    np.array(item.embedding, dtype=np.float32).tolist()
                    for item in response.data
                ]
                embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"嵌入批量处理失败: {e}")
                # 为失败的批次填充空向量
                embeddings.extend([[]] * len(batch))
                raise

        return embeddings

    def name(self) -> str:
        """嵌入器名称"""
        return f"RemoteChromaEmbedder({self.model_name})"

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return {
            "model_name": self.model_name,
            "batch_size": self._batch_size
        }


class EmbeddingClient:
    """嵌入客户端封装"""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._client: Optional[OpenAI] = None
        self._embedder: Optional[RemoteChromaEmbedder] = None

    @property
    def client(self) -> OpenAI:
        """获取OpenAI客户端（懒加载）"""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @property
    def embedder(self) -> RemoteChromaEmbedder:
        """获取嵌入器（懒加载）"""
        if self._embedder is None:
            self._embedder = RemoteChromaEmbedder(
                client=self.client,
                model_name=self.config.model_name,
                batch_size=self.config.batch_size
            )
        return self._embedder

    def _create_client(self) -> OpenAI:
        """创建OpenAI兼容客户端"""
        http_client = httpx.Client(
            verify=False,  # 根据实际情况调整
            timeout=httpx.Timeout(self.config.timeout)
        )

        return OpenAI(
            base_url=self.config.api_base,
            api_key=self.config.api_key,
            http_client=http_client
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def embed_text(self, text: str) -> List[float]:
        """嵌入单个文本"""
        embeddings = self.embedder([text])
        if embeddings and embeddings[0]:
            return embeddings[0]
        raise ValueError(f"文本嵌入失败: {text[:50]}...")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文本"""
        return self.embedder(texts)

    def close(self):
        """关闭客户端"""
        if self._client:
            self._client.close()
            self._client = None
        self._embedder = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_embedding_client(config: EmbeddingConfig) -> EmbeddingClient:
    """创建嵌入客户端工厂函数"""
    return EmbeddingClient(config)