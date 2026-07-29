#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 客户端 — 对标 Go 版本 internal/llm/client.go
直接调用 OpenAI 兼容 API，去掉 LangChain 依赖。
支持流式（SSE）和非流式调用。
"""
import json
import logging
import re
import requests
from typing import Optional, Generator

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端，OpenAI 兼容接口"""

    def __init__(self, api_uri: str, api_key: str, model_name: str,
                 temperature: float = 0.7, top_p: float = 0.9, max_tokens: int = 2048):
        self.base_url = api_uri.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=100,
            max_retries=2,
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def chat_stream(self, system_prompt: str, user_message: str) -> Generator[str, None, None]:
        """流式聊天，返回文本片段生成器"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

        url = f"{self.base_url}/chat/completions"
        resp = self._session.post(url, json=payload, stream=True, timeout=120)

        if resp.status_code != 200:
            error_body = resp.text
            logger.error("LLM API 返回错误: status=%d, body=%s", resp.status_code, error_body)
            raise ValueError(f"LLM API 返回错误 {resp.status_code}: {error_body}")

        # 读取 SSE 流
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data: "):
                continue

            data = line[6:]  # 去掉 "data: "
            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)
                choices = chunk.get("choices", [])
                if choices and choices[0].get("delta", {}).get("content"):
                    yield choices[0]["delta"]["content"]
            except json.JSONDecodeError:
                continue

    def chat(self, system_prompt: str, user_message: str) -> str:
        """非流式聊天"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

        url = f"{self.base_url}/chat/completions"
        resp = self._session.post(url, json=payload, timeout=120)

        if resp.status_code != 200:
            raise ValueError(f"LLM API 返回错误 {resp.status_code}: {resp.text}")

        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0]["message"]["content"]
        return ""