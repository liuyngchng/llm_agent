#!/bin/bash

ffmpeg -i input.m4a output.wav
cd /workspace/FunASR/runtime/python/websocket
python ./funasr_wss_client.py --host "127.0.0.1" --port 10095 \
  --ssl 0 --mode offline \
  --audio_in "/home/rd/Downloads/output.wav" \
  --output_dir "./results"