#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pip install sounddevice numpy
ubuntu 24.04
apt install portaudio19-dev
"""

import requests
import logging.config
import sounddevice as sd
import wave

from pydantic import SecretStr

from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

my_cfg = init_yml_cfg()
API_KEY = SecretStr(my_cfg['ai']['api_key'])
ASR_ENDPOINT = f"{my_cfg['ai']['api_uri']}/audio/transcriptions"
MODEL_NAME = my_cfg['ai']['asr_model_name']

def record_realtime(duration=10, fs=16000):
    logger.info("开始录音...")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # 阻塞等待录音完成
    return audio.flatten().tobytes()

# 调用ASR函数时保存为临时文件
def start_audio(file_name: str):
    with wave.open(file_name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(record_realtime())

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


    logger.info(f"ASR_ENDPOINT {ASR_ENDPOINT}, MODEL_NAME {MODEL_NAME}, API_KEY {API_KEY}")
    # 使用示例
    # audio_file = "static/asr_example_zh.wav"
    # result = transcribe_audio(audio_file)
    # logger.info(f"demo识别结果:{result}")
    audio_file = "my_audio.wav"
    start_audio(audio_file)
    logger.info("录音完毕")
    result = transcribe_audio(audio_file)
    logger.info(f"实时语音识别结果:{result}")
