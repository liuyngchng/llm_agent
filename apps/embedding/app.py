#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
文本向量化 embedding 模型服务
"""

from fastapi import FastAPI, HTTPException, Depends
from sentence_transformers import SentenceTransformer
import uvicorn
import logging.config
from pydantic import BaseModel
from typing import Optional, List, Union
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from common.sys_init import init_yml_cfg

app = FastAPI()

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

# 安全方案
security = HTTPBearer()

my_cfg = init_yml_cfg()

model = SentenceTransformer(f"./../../{my_cfg["api"]["embedding_model_name"]}", device='cpu')
# # 明确指定使用 CPU
# model = SentenceTransformer('your_model_name', device='cpu')
# # 或明确指定使用 GPU
# model = SentenceTransformer('your_model_name', device='cuda')

# 有效的 API Keys（在实际应用中应该从环境变量或数据库读取）
VALID_API_KEYS = {
    my_cfg["api"]["embedding_api_key"]
}


# 定义 OpenAI 兼容的请求/响应模型
class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str]]  # 支持字符串和字符串列表
    user: Optional[str] = None
    encoding_format: Optional[str] = "float"  # 支持 float 或 base64


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


def process_input(input_data: Union[str, List[str]]) -> List[str]:
    """处理输入数据，统一转换为字符串列表"""
    if isinstance(input_data, str):
        return [input_data]
    elif isinstance(input_data, list):
        if not all(isinstance(item, str) for item in input_data):
            raise HTTPException(status_code=400, detail="输入列表中的元素必须是字符串")
        return input_data
    else:
        raise HTTPException(status_code=400, detail="输入必须是字符串或字符串列表")


@app.post("/v1/embeddings")
async def create_embedding(
        request: EmbeddingRequest,
        api_key: str = Depends(verify_api_key)
):
    """OpenAI 兼容的嵌入端点"""
    try:
        # 处理输入格式
        input_texts = process_input(request.input)

        if not input_texts:
            raise HTTPException(status_code=400, detail="输入不能为空")

        if len(input_texts) > 100:  # 限制批量大小
            raise HTTPException(status_code=400, detail="单次请求最多处理100个文本")

        # 检查每个文本的长度
        for i, text in enumerate(input_texts):
            if len(text.strip()) == 0:
                raise HTTPException(status_code=400, detail=f"第 {i + 1} 个文本为空")
            if len(text) > 8192:  # 限制单个文本长度
                raise HTTPException(status_code=400, detail=f"第 {i + 1} 个文本过长（最大8192字符）")

        # 计算嵌入
        embeddings = model.encode(input_texts).tolist()

        # 构建 OpenAI 兼容的响应
        data = []
        for i, emb in enumerate(embeddings):
            # 处理 encoding_format 参数
            if request.encoding_format == "base64":
                # 如果需要 base64 格式，这里可以转换
                # 但通常使用 float 格式
                embedding_data = emb
            else:
                embedding_data = emb

            data.append(EmbeddingData(index=i, embedding=embedding_data))

        # 模拟 token 使用量（实际可以根据文本长度计算）
        total_tokens = sum(len(text) for text in input_texts)

        return EmbeddingResponse(
            data=data,
            model=request.model,
            usage={
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens
            }
        )

    except HTTPException:
        raise
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
    logger.info(f"模型设备: {model.device}, {model._target_device}")
    logger.info(f"api_cfg, {my_cfg['api']}")
    uvicorn.run(app, host="0.0.0.0", port=17000)