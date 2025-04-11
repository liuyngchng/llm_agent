#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
apt-get install ffmpeg
pip install pydub
"""
import io
import os
from typing import Union
from urllib.parse import urlparse

import httpx
from openai import OpenAI, APIConnectionError
import logging.config

from sys_init import init_yml_cfg
from pydub import AudioSegment

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def webm_to_wav(webm_data):
    audio = AudioSegment.from_file(io.BytesIO(webm_data), "webm")
    wav_buffer = io.BytesIO()
    audio.export(wav_buffer, format="wav")
    return wav_buffer.getvalue()

def _transcribe_core(audio_file: Union[str, io.BytesIO], cfg: dict):
    if isinstance(audio_file, io.BytesIO):
        audio_file.seek(0)
    scheme = urlparse(cfg.get("ai", {}).get("api_uri", "")).scheme
    http_client = httpx.Client(verify=False) if scheme == "https" else None
    client = OpenAI(
        base_url=cfg["ai"].get("api_uri"),
        api_key=cfg["ai"].get("api_key"),
        http_client=http_client
    )

    file_obj = open(audio_file, "rb") if isinstance(audio_file, str) else audio_file
    transcript = client.audio.transcriptions.create(
        model=cfg["ai"]["asr_model_name"],
        file=file_obj
    )
    return transcript.text

def transcribe_audio_file(audio_path: str, cfg:dict):
    try:
        return _transcribe_core(audio_path, cfg)
    except APIConnectionError as ex:
        logger.exception("transcribe_audio_file_err")

def transcribe_wav_audio_bytes(audio_bytes: bytes, cfg:dict):
    try:
        return _transcribe_core(io.BytesIO(audio_bytes), cfg)
    except APIConnectionError as ex:
        logger.exception("transcribe_audio_bytes_err")

def transcribe_webm_audio_bytes(webm_bytes: bytes, cfg:dict):
    if len(webm_bytes) == 0:
        raise ValueError("Empty audio data")
    wav_audio = webm_to_wav(webm_bytes)
    return transcribe_wav_audio_bytes(wav_audio, cfg)

def test_transcribe_audio():
    txt = transcribe_audio_file("./static/asr_example_zh.wav", my_cfg)
    logger.info(f"audio_txt: {txt}")


if __name__ == "__main__":
    os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    my_cfg = init_yml_cfg()
    test_transcribe_audio()