#!/bin/bash

CONTAINER_NAME="funasr-server"
IMAGE_NAME="funasr-with-ffmpeg"
IMAGE_VERSION="runtime-sdk-cpu-0.4.7"

# 如果容器不存在，先创建
if [ ! "$(docker ps -a | grep $CONTAINER_NAME)" ]; then
    docker run -d --name ${CONTAINER_NAME} \
      -p 10095:10095 \
      -v $(pwd)/funasr-runtime-resources/models:/workspace/models \
      ${IMAGE_NAME}:${IMAGE_VERSION} \
      bash -c "tail -f /dev/null"  # 保持容器运行
fi

# 启动容器（如果未运行）
docker start ${CONTAINER_NAME}

# 在容器内启动服务
docker exec -d ${CONTAINER_NAME} bash -c "
cd /workspace/FunASR/runtime/websocket/build/bin && \
./funasr-wss-server \
  --model-dir /workspace/models/damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx \
  --vad-dir /workspace/models/damo/speech_fsmn_vad_zh-cn-16k-common-onnx \
  --punc-dir /workspace/models/damo/punc_ct-transformer_cn-en-common-vocab471067-large-onnx \
  --itn-dir /workspace/models/thuduj12/fst_itn_zh \
  --lm-dir /workspace/models/damo/speech_ngram_lm_zh-cn-ai-wesp-fst \
  --port 10095 \
  --certfile '' \
  --decoder-thread-num 4 \
  --io-thread-num 1 \
  --model-thread-num 1 \
  > /workspace/server.log 2>&1 &
"

echo "FunASR service started on port 10095"