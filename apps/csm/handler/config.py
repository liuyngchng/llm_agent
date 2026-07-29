#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置处理器 — 对标 Go 版本 internal/handler/config.go
"""
import logging
from flask import request, jsonify

from apps.csm.cfg import apply_db_config
from apps.csm.store import DEFAULT_CHAT_PROMPT

logger = logging.getLogger(__name__)


class ConfigHandler:
    """系统配置 API 处理器"""

    def __init__(self, cfg: dict, store):
        self.cfg = cfg
        self.store = store

    def get_config(self):
        """获取所有配置 GET /api/config"""
        prompt = self._get_prompt()
        resp = {
            "sys": {
                "name": self.cfg["sys"]["name"],
                "auth": str(self.cfg["sys"].get("auth", False)).lower(),
                "api_auth": str(self.cfg["sys"].get("api_auth", True)).lower(),
            },
            "api": {
                "llm_api_uri": self.cfg["api"].get("llm_api_uri", ""),
                "llm_api_key": self.cfg["api"].get("llm_api_key", ""),
                "llm_model_name": self.cfg["api"].get("llm_model_name", ""),
                "embedding_api_uri": self.cfg["api"].get("embedding_api_uri", ""),
                "embedding_api_key": self.cfg["api"].get("embedding_api_key", ""),
                "embedding_model_name": self.cfg["api"].get("embedding_model_name", ""),
                "rerank_api_uri": self.cfg["api"].get("rerank_api_uri", ""),
                "rerank_api_key": self.cfg["api"].get("rerank_api_key", ""),
                "rerank_model_name": self.cfg["api"].get("rerank_model_name", ""),
            },
            "prompt": {
                "chat_msg": prompt,
            },
            "kb": {
                "chunk_size": self.cfg["kb"].get("chunk_size", 300),
                "chunk_overlap": self.cfg["kb"].get("chunk_overlap", 80),
                "top_k": self.cfg["kb"].get("top_k", 3),
                "score_threshold": self.cfg["kb"].get("score_threshold", 0.1),
                "rerank_enabled": self.cfg["kb"].get("rerank_enabled", False),
                "rerank_retrieve_n": self.cfg["kb"].get("rerank_retrieve_n", 15),
            },
            "llm": {
                "temperature": self.cfg.get("llm", {}).get("temperature", 0.7),
                "top_p": self.cfg.get("llm", {}).get("top_p", 0.9),
                "max_tokens": self.cfg.get("llm", {}).get("max_tokens", 2048),
            },
            "faq": {
                "match_threshold": self.cfg.get("faq", {}).get("match_threshold", 0.85),
            },
        }
        return jsonify({"data": resp})

    def update_config(self):
        """更新配置 PUT /api/config"""
        data = request.get_json(silent=True) or {}

        # 更新系统配置
        sys_data = data.get("sys", {})
        if sys_data.get("name"):
            self.store.set_config("sys.name", sys_data["name"], "系统名称")
        # sys.auth 只从 cfg.yml 读取，不允许在页面上修改（对标 Go）
        if sys_data.get("api_auth"):
            self.store.set_config("sys.api_auth", sys_data["api_auth"], "是否启用接口认证")

        # 更新 API 配置
        api_data = data.get("api", {})
        api_mappings = {
            "llm_api_uri": "api.llm_api_uri",
            "llm_api_key": "api.llm_api_key",
            "llm_model_name": "api.llm_model_name",
            "embedding_api_uri": "api.embedding_api_uri",
            "embedding_api_key": "api.embedding_api_key",
            "embedding_model_name": "api.embedding_model_name",
            "rerank_api_uri": "api.rerank_api_uri",
            "rerank_api_key": "api.rerank_api_key",
            "rerank_model_name": "api.rerank_model_name",
        }
        for json_key, db_key in api_mappings.items():
            if api_data.get(json_key):
                self.store.set_config(db_key, api_data[json_key], "")

        # 更新提示词
        prompt_data = data.get("prompt", {})
        if prompt_data.get("chat_msg"):
            self.store.upsert_prompt("chat_msg", prompt_data["chat_msg"], 0)

        # 更新 KB 参数
        kb_data = data.get("kb", {})
        if kb_data.get("chunk_size"):
            self.store.set_config("kb.chunk_size", str(kb_data["chunk_size"]), "文本分片大小")
        if kb_data.get("chunk_overlap"):
            self.store.set_config("kb.chunk_overlap", str(kb_data["chunk_overlap"]), "分片重叠大小")
        if kb_data.get("top_k"):
            self.store.set_config("kb.top_k", str(kb_data["top_k"]), "检索返回条数")
        if kb_data.get("score_threshold"):
            self.store.set_config("kb.score_threshold", str(kb_data["score_threshold"]), "相似度阈值")
        if "rerank_enabled" in kb_data:
            self.store.set_config("kb.rerank_enabled", str(kb_data["rerank_enabled"]).lower(), "是否启用 Rerank")
        if kb_data.get("rerank_retrieve_n"):
            self.store.set_config("kb.rerank_retrieve_n", str(kb_data["rerank_retrieve_n"]), "Rerank 预检索条数")

        # 更新 LLM 参数
        llm_data = data.get("llm", {})
        if llm_data.get("temperature"):
            self.store.set_config("llm.temperature", str(llm_data["temperature"]), "LLM 温度")
        if llm_data.get("top_p"):
            self.store.set_config("llm.top_p", str(llm_data["top_p"]), "LLM Top-P")
        if llm_data.get("max_tokens"):
            self.store.set_config("llm.max_tokens", str(llm_data["max_tokens"]), "LLM 最大 Token 数")

        # 更新 FAQ 参数
        faq_data = data.get("faq", {})
        if faq_data.get("match_threshold"):
            self.store.set_config("faq.match_threshold", str(faq_data["match_threshold"]), "FAQ 匹配阈值")

        # 重新加载配置到内存
        db_configs = self.store.get_all_configs()
        apply_db_config(self.cfg, db_configs)

        return jsonify({"status": "ok"})

    def _get_prompt(self) -> str:
        prompt = self.store.get_prompt("chat_msg")
        if prompt:
            return prompt
        return DEFAULT_CHAT_PROMPT