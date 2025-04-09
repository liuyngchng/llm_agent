#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

def test():
    logger.info("test")


import requests

API_KEY = "your_api_key"
ASR_ENDPOINT = "https://api.example.com/v1/audio/transcriptions"  # 替换为实际接口地址


def transcribe_audio(audio_path):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "multipart/form-data"
    }

    files = {
        "file": open(audio_path, "rb"),
        "model": (None, "whisper-1")  # 替换为实际模型名称
    }

    response = requests.post(ASR_ENDPOINT, headers=headers, files=files)
    return response.json()["text"]





if __name__ == "__main__":
    """
    https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch
    """
    logger.info("test")
    # 使用示例
    result = transcribe_audio("audio.wav")
    print("识别结果:", result)