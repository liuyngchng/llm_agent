#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载模块 — 从 YAML 加载基础配置，从 SQLite 加载运行时配置。
对标 Go 版本 internal/config/config.go
"""
import os
import yaml
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 默认配置值
DEFAULT_CONFIG = {
    "server": {"port": 19007, "debug": True},
    "sys": {"name": "对话机器人", "auth": False, "api_auth": False, "work_mode": 0, "default_workflow_id": 0},
    "api": {
        "llm_api_uri": "",
        "llm_api_key": "",
        "llm_model_name": "",
        "embedding_api_uri": "",
        "embedding_api_key": "",
        "embedding_model_name": "",
        "rerank_api_uri": "",
        "rerank_api_key": "",
        "rerank_model_name": "",
    },
    "kb": {
        "chunk_size": 300,
        "chunk_overlap": 80,
        "top_k": 3,
        "score_threshold": 0.1,
        "rerank_enabled": False,
        "rerank_retrieve_n": 15,
    },
    "llm": {
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 2048,
    },
    "faq": {
        "match_threshold": 0.85,
    },
    "store": {"backend": "sqlite"},
    "vector": {"backend": "local"},
    "mysql": {"dsn": ""},
    "milvus": {"uri": "", "token": ""},
    "qdrant": {"host": "localhost", "port": 6334, "api_key": "", "use_tls": False},
}


def load_yaml(path: str) -> dict:
    """从 YAML 文件加载配置"""
    if not os.path.exists(path):
        logger.warning("配置文件 %s 不存在，使用默认配置", path)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    return data


def deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(yaml_path: str = "cfg.yml") -> dict:
    """加载完整配置：YAML + 默认值"""
    yaml_cfg = load_yaml(yaml_path)
    cfg = deep_merge(DEFAULT_CONFIG, yaml_cfg)
    logger.info("配置加载完成: sys.name=%s, port=%d", cfg["sys"]["name"], cfg["server"]["port"])
    return cfg


def apply_db_config(cfg: dict, db_configs: dict[str, str]) -> dict:
    """从数据库 key-value 配置覆盖内存配置"""
    mappings = [
        ("sys.name", ["sys", "name"]),
        ("sys.auth", ["sys", "auth"]),
        ("sys.api_auth", ["sys", "api_auth"]),
        ("sys.work_mode", ["sys", "work_mode"]),
        ("sys.default_workflow_id", ["sys", "default_workflow_id"]),
        ("api.llm_api_uri", ["api", "llm_api_uri"]),
        ("api.llm_api_key", ["api", "llm_api_key"]),
        ("api.llm_model_name", ["api", "llm_model_name"]),
        ("api.embedding_api_uri", ["api", "embedding_api_uri"]),
        ("api.embedding_api_key", ["api", "embedding_api_key"]),
        ("api.embedding_model_name", ["api", "embedding_model_name"]),
        ("api.rerank_api_uri", ["api", "rerank_api_uri"]),
        ("api.rerank_api_key", ["api", "rerank_api_key"]),
        ("api.rerank_model_name", ["api", "rerank_model_name"]),
        ("kb.chunk_size", ["kb", "chunk_size"]),
        ("kb.chunk_overlap", ["kb", "chunk_overlap"]),
        ("kb.top_k", ["kb", "top_k"]),
        ("kb.score_threshold", ["kb", "score_threshold"]),
        ("kb.rerank_enabled", ["kb", "rerank_enabled"]),
        ("kb.rerank_retrieve_n", ["kb", "rerank_retrieve_n"]),
        ("llm.temperature", ["llm", "temperature"]),
        ("llm.top_p", ["llm", "top_p"]),
        ("llm.max_tokens", ["llm", "max_tokens"]),
        ("faq.match_threshold", ["faq", "match_threshold"]),
    ]

    for db_key, cfg_path in mappings:
        if db_key in db_configs and db_configs[db_key]:
            val = db_configs[db_key]
            # 类型转换
            target = cfg
            for part in cfg_path[:-1]:
                target = target[part]
            key = cfg_path[-1]
            orig_val = target[key]
            if isinstance(orig_val, bool):
                target[key] = val.lower() == "true"
            elif isinstance(orig_val, int):
                target[key] = int(val)
            elif isinstance(orig_val, float):
                target[key] = float(val)
            else:
                target[key] = val

    # 兜底：overlap 必须严格小于 chunkSize 的一定比例，否则文本切分会死循环
    chunk_size = cfg["kb"].get("chunk_size", 300)
    chunk_overlap = cfg["kb"].get("chunk_overlap", 80)
    if chunk_overlap >= chunk_size:
        cfg["kb"]["chunk_overlap"] = chunk_size // 3

    return cfg