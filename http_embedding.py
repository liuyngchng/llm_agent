#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from fastapi import FastAPI, HTTPException, Depends, Header, Security
from sentence_transformers import SentenceTransformer
import uvicorn
from pydantic import BaseModel
from typing import Optional, List
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sys_init import init_yml_cfg

app = FastAPI()
model = SentenceTransformer('./../bge-large-zh-v1.5')

# 安全方案
security = HTTPBearer()

my_cfg = init_yml_cfg()

# 有效的 API Keys（在实际应用中应该从环境变量或数据库读取）
VALID_API_KEYS = {
    my_cfg["api"]["embedding_api_key"]
}


# 定义 OpenAI 兼容的请求/响应模型
class EmbeddingRequest(BaseModel):
    model: str
    input: List[str]  # 兼容 OpenAI 格式


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: dict = {"prompt_tokens": 0, "total_tokens": 0}


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证 API Key"""
    api_key = credentials.credentials

    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="无效的 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key


@app.post("/v1/embeddings")
async def create_embedding(
        request: EmbeddingRequest,
        api_key: str = Depends(verify_api_key)
):
    """OpenAI 兼容的嵌入端点"""
    try:
        if not request.input:
            raise HTTPException(status_code=400, detail="输入不能为空")

        if len(request.input) > 100:  # 限制批量大小
            raise HTTPException(status_code=400, detail="单次请求最多处理100个文本")

        # 计算嵌入
        embeddings = model.encode(request.input).tolist()

        # 构建 OpenAI 兼容的响应
        data = []
        for i, emb in enumerate(embeddings):
            data.append(EmbeddingData(index=i, embedding=emb))

        # 模拟 token 使用量（实际可以根据文本长度计算）
        total_tokens = sum(len(text) for text in request.input)

        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage={
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")


@app.post("/v1/engines/{model_name}/embeddings")
async def create_embedding_legacy(
        model_name: str,
        request: EmbeddingRequest,
        api_key: str = Depends(verify_api_key)
):
    """兼容旧版 OpenAI 引擎格式的端点"""
    # 重用主端点逻辑
    request.model = model_name
    return await create_embedding(request, api_key)


@app.get("/health")
async def health():
    """健康检查端点（不需要认证）"""
    return {"status": "healthy", "model": "bge-large-zh-v1.5"}


@app.get("/v1/models")
async def list_models(api_key: str = Depends(verify_api_key)):
    """列出可用模型（OpenAI 兼容）"""
    return {
        "object": "list",
        "data": [
            {
                "id": "bge-large-zh-v1.5",
                "object": "model",
                "created": 1677610602,
                "owned_by": "BAAI"
            }
        ]
    }


# 可选的根路径重定向
@app.get("/")
async def root():
    return {
        "message": "BGE Embedding Service",
        "version": "1.0",
        "endpoints": {
            "embeddings": "/v1/embeddings",
            "models": "/v1/models",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=17000)