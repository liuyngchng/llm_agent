#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
import wave
import requests
import websockets
import logging.config

from typing import Optional
import json

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


def convert_to_wav(input_path: str, output_path: str) -> bool:
    """将各种音频格式转换为 16kHz 单声道 WAV"""
    try:
        # 使用 ffmpeg 转换（需要安装 ffmpeg）
        cmd = f"ffmpeg -i {input_path} -ar 16000 -ac 1 -y {output_path} -loglevel quiet"
        os.system(cmd)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"转换失败: {e}")
        return False


def read_audio_pcm(wav_path: str, chunk_ms: int = 500) -> bytes:
    """读取 WAV 文件的 PCM 数据"""
    with wave.open(wav_path, 'rb') as wav:
        # 检查格式
        if wav.getframerate() != 16000:
            raise ValueError(f"采样率必须是 16000Hz，当前为 {wav.getframerate()}Hz")
        if wav.getnchannels() != 1:
            raise ValueError("必须是单声道")

        # 读取所有音频数据
        pcm_data = wav.readframes(wav.getnframes())

    return pcm_data


async def recognize_with_websocket(audio_pcm: bytes, funasr_ws_url:str) -> str:
    """通过 WebSocket 调用 FunASR 进行识别"""
    try:
        async with websockets.connect(funasr_ws_url) as ws:
            # 发送音频数据
            await ws.send(audio_pcm)

            # 发送结束标志
            await ws.send('{"eof": 1}')

            # 接收结果
            results = []
            async for message in ws:
                data = json.loads(message)
                if 'text' in data and data['text']:
                    results.append(data['text'])
                if 'is_final' in data and data['is_final']:
                    break

            return ' '.join(results) if results else ''

    except Exception as e:
        print(f"WebSocket 识别失败: {e}")
        return ""


async def recognize_with_http(file_path: str, funasr_http_url: str) -> str:
    """通过 HTTP 方式调用 FunASR（在线文件识别）"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            logger.info(f"start_request {funasr_http_url}/recognition")
            response = requests.post(f"{funasr_http_url}/recognition", files=files, timeout=60)
            logger.info(f"end_request {funasr_http_url}/recognition")
        if response.status_code == 200:
            result = response.json()
            return result.get('text', '')
        else:
            print(f"HTTP 识别失败: {response.status_code}")
            return ''

    except Exception as e:
        print(f"HTTP 识别失败: {e}")
        return ""

