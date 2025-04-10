#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import logging.config

from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

def test():
    logger.info("test")

my_cfg = init_yml_cfg()

API_KEY = my_cfg['ai']['api_key']
ASR_ENDPOINT = f"{my_cfg['ai']['api_uri']}/audio/transcriptions"  # 替换为实际接口地址

MODEL_NAME = my_cfg['ai']['asr_model_name']

def transcribe_audio(audio_path):
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    files = {
        "file": open(audio_path, "rb")
    }

    data = {
        "model": MODEL_NAME  # 改为通过data参数传递
    }
    response = requests.post(ASR_ENDPOINT, headers=headers, files=files, data=data, verify=False, proxies=None)
    return response.json()


if __name__ == "__main__":
    """
    https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch
    
    curl -ks --noproxy '*' -w'\n' --tlsv1 -X POST  '{api_uri}/audio/transcriptions' \
        -H "Content-Type: multipart/form-data" \
        -H 'Authorization: Bearer {api_key}' \
        -F "file=@static/asr_example_zh.wav" \
        -F "model={asr_model_name}" | jq
    """
    logger.info("start test")
    # 使用示例
    logger.info(f"ASR_ENDPOINT {ASR_ENDPOINT}, MODEL_NAME {MODEL_NAME}, API_KEY {API_KEY}")
    result = transcribe_audio("static/asr_example_zh.wav")
    logger.info(f"识别结果:{result}")