#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

# config.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class VectorSearchConfig:
    """向量检索配置"""
    vector_db_path: str
    embedding_model: str
    api_key: str
    api_base: str
    chunk_size: int = 300
    chunk_overlap: int = 80
    default_top_k: int = 3
    default_score_threshold: float = 0.5
    timeout: int = 30
    max_retries: int = 3