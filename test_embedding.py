#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from urllib.parse import urlparse

import httpx
from numpy import shape
from openai import OpenAI
from sys_init import init_yml_cfg
import logging.config
import numpy as np
import faiss

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    my_cfg = init_yml_cfg()['ai']
    scheme = urlparse(my_cfg.get("api_uri", "")).scheme
    http_client = httpx.Client(verify=False) if scheme == "https" else None
    client = OpenAI(
        base_url=my_cfg['api_uri'],
        api_key=my_cfg['api_key'],
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