#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
import uvicorn
from pydantic import BaseModel

app = FastAPI()
model = SentenceTransformer('./../bge-large-zh-v1.5')


# 定义 OpenAI 兼容的请求/响应模型
class EmbeddingRequest(BaseModel):
    model: str
    input: list[str]  # 兼容 OpenAI 格式


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str


@app.post("/v1/embeddings")
async def create_embedding(request: EmbeddingRequest):
    embeddings = model.encode(request.input).tolist()

    # 构建 OpenAI 兼容的响应
    data = []
    for i, emb in enumerate(embeddings):
        data.append(EmbeddingData(index=i, embedding=emb))

    return EmbeddingResponse(data=data, model=request.model)


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)