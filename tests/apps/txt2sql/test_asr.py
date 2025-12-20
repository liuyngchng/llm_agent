#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install sounddevice numpy keyboard
pip install "vllm[audio]"
ubuntu 24.04
apt install portaudio19-dev
"""

import requests
import logging.config
import sounddevice as sd
import wave
import keyboard
import numpy as np
from threading import Thread, Event

from pydantic import SecretStr

from sys_init import init_yml_cfg

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

my_cfg = init_yml_cfg()
API_KEY = SecretStr(my_cfg['api']['asr_api_key'])
ASR_ENDPOINT = f"{my_cfg['api']['asr_api_uri']}/audio/transcriptions"
MODEL_NAME = my_cfg['api']['asr_model_name']

def record_realtime(duration=10, fs=16000) -> bytes:
    """
    函数调用发起录音
    duration: 录音时间长度默认10秒， 时长到自动停止录音
    """
    logger.info(f"开始录音，时长 {duration} 秒")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # 阻塞等待录音完成
    return audio.flatten().tobytes()

def customized_record_realtime(stop_event, fs=16000) -> bytes:
    audio = []
    def callback(indata, *_):
        if not stop_event.is_set():
            audio.append(indata.copy())

    with sd.InputStream(callback=callback, channels=1, samplerate=fs):
        print("按 Q 结束录音")
        stop_event.wait()  # 阻塞等待结束信号

    return np.concatenate(audio).tobytes()

# 调用ASR函数时保存为临时文件
def start_audio(file_name: str):
    with wave.open(file_name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(record_realtime())

def transcribe_audio(audio_path):
    headers = {
        "Authorization": f"Bearer {API_KEY.get_secret_value()}"
    }

    files = {
        "txt_file": open(audio_path, "rb")
    }

    data = {
        "model": MODEL_NAME,
        "language":"zh",
        "task":"transcribe"
    }
    #如果有证书的话,自签证书还需要在操作系统安装证书
    # response = requests.post(ASR_ENDPOINT, headers=headers, files=files, data=data, verify="./cert/my.crt", proxies=None)
    logger.info(f"requests.post({ASR_ENDPOINT}, headers={headers}, files={files}, data={data}, verify=False, proxies=None)")
    response = requests.post(ASR_ENDPOINT, headers=headers, files=files, data=data, verify=False, proxies=None)
    return response.json()

def test_transcribe_my_wav_audio_file() -> str:
    logger.info(f"ASR_ENDPOINT {ASR_ENDPOINT}, MODEL_NAME {MODEL_NAME}, API_KEY {API_KEY.get_secret_value()}")
    # 使用示例
    audio_file = "common/static/asr_example_zh.wav"
    result = transcribe_audio(audio_file)
    logger.info(f"demo识别结果:{result}")
    return result

def test_transcribe_my_realtime_audio() -> str:
    audio_file = "my_audio.wav"
    start_audio(audio_file)
    logger.info("录音完毕")
    result = transcribe_audio(audio_file)
    logger.info(f"实时语音识别结果:{result}")
    return result

def test_customized_transcribe_my_realtime_audio():
    stop_flag = Event()
    keyboard.wait('S')  # 按 S 开始录音
    rec_thread = Thread(target=customized_record_realtime, args=(stop_flag,))
    rec_thread.start()

    keyboard.wait('Q')  # 按 Q 结束录音
    stop_flag.set()
    rec_thread.join()

    # 新增保存逻辑
    audio_data = customized_record_realtime(stop_flag)  # 获取录音字节流
    with wave.open("output.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16位深度=2字节
        wf.setframerate(16000)
        wf.writeframes(audio_data)

if __name__ == "__main__":
    """
    https://www.modelscope.cn/models/iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch
    
    curl -ks --noproxy '*' -w'\n' --tlsv1 -X POST  '{llm_api_uri}/audio/transcriptions' \
        -H "Content-Type: multipart/form-data" \
        -H 'Authorization: Bearer {llm_api_key}' \
        -F "txt_file=@static/asr_example_zh.wav" \
        -F "model={asr_model_name}" | jq
    """
    logger.info("start test")
    test_transcribe_my_wav_audio_file()
    # test_transcribe_my_realtime_audio()
    # test_customized_transcribe_my_realtime_audio()



