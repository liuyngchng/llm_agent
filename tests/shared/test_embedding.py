#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from urllib.parse import urlparse

import httpx
from numpy import shape
from openai import OpenAI
from sys_init import init_yml_cfg
import logging.config
import numpy as np
import faiss

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    my_cfg = init_yml_cfg()['api']
    scheme = urlparse(my_cfg.get("llm_api_uri", "")).scheme
    http_client = httpx.Client(verify=False) if scheme == "https" else None
    client = OpenAI(
        base_url=my_cfg['llm_api_uri'],
        api_key=my_cfg['llm_api_key'],
        http_client=http_client
    )
    response = client.embeddings.create(
        model=my_cfg['embedding_model_name'],
        input=["你的文本", "我的文本", "他的文本"]
    )
    vector = np.array([response.data[0].embedding], dtype='float32')
    logger.info(f"vector: {vector}, shape_of_array: {shape(vector)}")
    index = faiss.IndexFlatL2(vector.shape[1])
    index.add(vector)
    faiss.write_index(index, "my_vectors.faiss")