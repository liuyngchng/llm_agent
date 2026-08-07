#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置处理器 — 对标 Go 版本 internal/handler/config.go
"""
import logging
import time
from flask import request, jsonify

from apps.csm.cfg import apply_db_config
from apps.csm.store import DEFAULT_CHAT_PROMPT

logger = logging.getLogger(__name__)

# overlap 允许占 chunk_size 的最大比例（百分比），避免文本切分死循环
MAX_CHUNK_OVERLAP_RATIO = 30


class ConfigHandler:
    """系统配置 API 处理器"""

    def __init__(self, cfg: dict, store, workflow_engine=None):
        self.cfg = cfg
        self.store = store
        self.engine = workflow_engine

    def get_config(self):
        """获取所有配置 GET /api/config"""
        prompt = self._get_prompt()
        resp = {
            "sys": {
                "name": self.cfg["sys"]["name"],
                "auth": str(self.cfg["sys"].get("auth", False)).lower(),
                "api_auth": str(self.cfg["sys"].get("api_auth", True)).lower(),
                "work_mode": self.cfg["sys"].get("work_mode", 0),
                "default_workflow_id": self.cfg["sys"].get("default_workflow_id", 0),
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
        # 工作模式（始终保存）
        if "work_mode" in sys_data:
            self.store.set_config("sys.work_mode", str(sys_data["work_mode"]), "工作模式: 0=KB, 1=CSM, 2=动态工作流")
        # 动态工作流 ID
        if "default_workflow_id" in sys_data:
            self.store.set_config("sys.default_workflow_id", str(sys_data["default_workflow_id"]), "动态工作流 ID")

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
            chunk_size = self.cfg["kb"].get("chunk_size", 300)
            if kb_data.get("chunk_size"):
                chunk_size = int(kb_data["chunk_size"])
            overlap = int(kb_data["chunk_overlap"])
            # 校验：overlap 必须严格小于 chunk_size 的一定比例，否则文本切分步长为 0 会死循环
            max_overlap = chunk_size * MAX_CHUNK_OVERLAP_RATIO // 100
            if overlap >= chunk_size:
                return jsonify({"error": f"分片重叠必须小于分片大小（当前 {overlap} ≥ {chunk_size}）"}), 400
            if overlap > max_overlap:
                return jsonify({
                    "error": f"分片重叠过大，最多为分片大小的 {MAX_CHUNK_OVERLAP_RATIO}%（{max_overlap}），当前 {overlap}"
                }), 400
            self.store.set_config("kb.chunk_overlap", str(overlap), "分片重叠大小")
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

    def test_models(self):
        """测试模型 API 连接 POST /api/config/test-models（对标 Go TestModels）"""
        data = request.get_json(silent=True) or {}

        results = []

        # 1. 测试 LLM 对话模型
        llm_uri = data.get("llm_api_uri", "")
        if llm_uri:
            t0 = time.time()
            try:
                from apps.csm.chat_agent import LLMClient
                client = LLMClient(
                    llm_uri,
                    data.get("llm_api_key", ""),
                    data.get("llm_model_name", ""),
                )
                client.chat("你是一个助手，请回复 OK。", "hi")
                elapsed = int((time.time() - t0) * 1000)
                results.append({"name": "LLM 对话模型", "ok": True, "message": "连接成功", "elapsed_ms": elapsed})
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                logger.warning("model test: LLM failed: %s", e)
                results.append({"name": "LLM 对话模型", "ok": False, "message": str(e), "elapsed_ms": elapsed})
        else:
            results.append({"name": "LLM 对话模型", "ok": False, "message": "未配置 API 地址"})

        # 2. 测试 Embedding 向量模型
        emb_uri = data.get("embedding_api_uri", "")
        if emb_uri:
            t0 = time.time()
            try:
                from apps.csm.embedding_client import EmbeddingClient
                client = EmbeddingClient(
                    emb_uri,
                    data.get("embedding_api_key", ""),
                    data.get("embedding_model_name", ""),
                )
                dim = client.dimension()
                elapsed = int((time.time() - t0) * 1000)
                results.append({"name": "Embedding 向量模型", "ok": True,
                                "message": f"连接成功 (dim={dim})", "elapsed_ms": elapsed})
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                logger.warning("model test: Embedding failed: %s", e)
                results.append({"name": "Embedding 向量模型", "ok": False, "message": str(e), "elapsed_ms": elapsed})
        else:
            results.append({"name": "Embedding 向量模型", "ok": False, "message": "未配置 API 地址"})

        # 3. 测试 Rerank 重排序模型
        rerank_uri = data.get("rerank_api_uri", "")
        if rerank_uri:
            t0 = time.time()
            try:
                # 简单的 rerank API 测试（OpenAI 兼容接口可能不直接支持 rerank，跳过）
                # 对标 Go 版本，如果项目中有 rerank 模块则使用
                from apps.csm.embedding_client import EmbeddingClient
                # Rerank 通常使用专门的 API endpoint，这里做基本连通性测试
                client = EmbeddingClient(
                    rerank_uri,
                    data.get("rerank_api_key", ""),
                    data.get("rerank_model_name", ""),
                )
                # 用 embedding 接口测试连通性（rerank 接口可能类似）
                client.embed_single("connectivity test")
                elapsed = int((time.time() - t0) * 1000)
                results.append({"name": "Rerank 重排序模型", "ok": True, "message": "连接成功", "elapsed_ms": elapsed})
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                logger.warning("model test: Rerank failed: %s", e)
                results.append({"name": "Rerank 重排序模型", "ok": False, "message": str(e), "elapsed_ms": elapsed})
        else:
            results.append({"name": "Rerank 重排序模型", "ok": False, "message": "未配置 API 地址"})

        all_ok = all(r.get("ok", False) for r in results)

        return jsonify({"results": results, "all_ok": all_ok})

    def info(self):
        """返回服务信息 GET /api/info"""
        return jsonify({
            "name": self.cfg["sys"]["name"],
            "version": "1.0.0",
            "work_mode": self.cfg["sys"].get("work_mode", 0),
            "vector_backend": self.cfg.get("vector", {}).get("backend", "local"),
            "store_backend": self.cfg.get("store", {}).get("backend", "sqlite"),
            "supported_file_types": ["txt", "md", "pdf", "docx", "xlsx"],
            "api_auth_enabled": self.cfg["sys"].get("api_auth", True),
        })

    def _get_prompt(self) -> str:
        prompt = self.store.get_prompt("chat_msg")
        if prompt:
            return prompt
        return DEFAULT_CHAT_PROMPT
