#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.config
import os
import uuid
import uvicorn

import websockets
from fastapi.security import HTTPBearer
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from apps.asr.asr import convert_to_wav, recognize_with_http, read_audio_pcm, recognize_with_websocket
from common.sys_init import init_yml_cfg

app = FastAPI(title="FunASR 语音识别服务")

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

# 安全方案
security = HTTPBearer()

my_cfg = init_yml_cfg()

# FunASR 服务地址
# "ws://127.0.0.1:19010"  # WebSocket 地址
FUNASR_WS_URL = my_cfg['funasr']['ws_api_uri']
# "http://127.0.0.1:19010"  # HTTP 地址
FUNASR_HTTP_URL = my_cfg['funasr']['http_api_uri']

# 临时文件存储目录
TEMP_DIR = "./temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)


@app.post("/recognize", summary="语音识别接口")
async def recognize_audio(
        file: UploadFile = File(..., description="上传音频文件 (支持 wav, mp3, m4a, flac 等格式)"),
        use_http: bool = False
):
    """
    上传音频文件并进行语音识别

    参数:
    - file: 音频文件
    - use_http: 是否使用 HTTP 接口（默认使用 WebSocket，更稳定）

    返回:
    - text: 识别出的文本
    - success: 是否成功
    - message: 提示信息
    """
    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    temp_original = os.path.join(TEMP_DIR, f"{file_id}_original.{file.filename.split('.')[-1]}")
    temp_converted = os.path.join(TEMP_DIR, f"{file_id}_16k.wav")

    try:
        # 1. 保存上传的原始文件
        content = await file.read()
        with open(temp_original, 'wb') as f:
            f.write(content)

        # 2. 转换为 16kHz 单声道 WAV
        if not convert_to_wav(temp_original, temp_converted):
            raise HTTPException(status_code=400, detail="音频格式转换失败，请确保上传的是有效的音频文件")

        # 3. 调用 FunASR 识别
        if use_http:
            text = await recognize_with_http(temp_converted, FUNASR_HTTP_URL)
        else:
            pcm_data = read_audio_pcm(temp_converted)
            text = await recognize_with_websocket(pcm_data, FUNASR_WS_URL)

        if text:
            return JSONResponse({
                "success": True,
                "text": text,
                "message": "识别成功"
            })
        else:
            return JSONResponse({
                "success": False,
                "text": "",
                "message": "识别失败，未获取到有效文本"
            })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

    finally:
        # 清理临时文件
        for f in [temp_original, temp_converted]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass


@app.get("/health", summary="健康检查")
async def health_check():
    """检查 FunASR 服务是否可用"""
    try:
        # 尝试 WebSocket 连接
        async with websockets.connect(FUNASR_WS_URL, timeout=5):
            return {"status": "healthy", "funasr": "connected"}
    except:
        return {"status": "unhealthy", "funasr": "disconnected"}


if __name__ == "__main__":


    # 启动服务
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=19010,
        log_level="info"
    )