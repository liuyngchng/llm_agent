#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding 客户端 — 对标 Go 版本 internal/embedding/client.go
OpenAI 兼容接口，支持批量 embedding 和维度探测。
"""
import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 32


class EmbeddingClient:
    """Embedding 客户端"""

    def __init__(self, api_uri: str, api_key: str, model_name: str):
        self.base_url = api_uri.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })
        # 连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=100,
            max_retries=2,
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转为向量"""
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i:i + MAX_BATCH_SIZE]
            embeddings = self._embed_batch(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def embed_single(self, text: str) -> list[float]:
        """将单个文本转为向量"""
        results = self.embed([text])
        if not results:
            raise ValueError("embedding 返回空结果")
        return results[0]

    def dimension(self) -> int:
        """探测 embedding 模型的输出维度"""
        vec = self.embed_single("dimension probe")
        dim = len(vec)
        logger.info("embedding 模型探测成功: model=%s, dim=%d", self.model_name, dim)
        return dim

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self.base_url:
            raise ValueError("Embedding API 地址未配置")

        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model_name,
            "input": texts,
        }

        resp = self._session.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            logger.error("embedding API 返回错误: status=%d, body=%s", resp.status_code, resp.text)
            raise ValueError(f"embedding API 返回错误 {resp.status_code}: {resp.text}")

        data = resp.json()
        return [item["embedding"] for item in data["data"]]