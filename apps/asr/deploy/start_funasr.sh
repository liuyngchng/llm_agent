#!/bin/bash

docker pull registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:runtime-sdk-cpu-0.4.7

CONTAINER_NAME="funasr-server"
IMAGE_NAME="funasr-with-ffmpeg"
IMAGE_VERSION="runtime-sdk-cpu-0.4.7"

# 检查并创建必要的目录
mkdir -p $(pwd)/funasr-runtime-resources/models

# 如果容器不存在，先创建
if [ ! "$(docker ps -a | grep $CONTAINER_NAME)" ]; then
    echo "Creating new container..."
    docker run -dit --name ${CONTAINER_NAME} \
      -p 10095:10095 \
      -v $(pwd)/funasr-runtime-resources/models:/workspace/models \
      ${IMAGE_NAME}:${IMAGE_VERSION} \
      tail -f /dev/null  # 保持容器运行
fi

# 启动容器（如果未运行）
echo "Starting container..."
docker start ${CONTAINER_NAME}

# 等待容器完全启动
sleep 2

# 在容器内启动服务
echo "Starting FunASR service inside container..."
docker exec -d ${CONTAINER_NAME} bash -c "
cd /workspace/FunASR/runtime/websocket/build/bin && \
if [ -f ./funasr-wss-server ]; then
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
    echo 'Service started'
else
    echo 'Error: funasr-wss-server not found'
    exit 1
fi
"

# 等待服务启动
sleep 3

# 检查服务状态
echo "Checking service status..."
docker exec ${CONTAINER_NAME} ps aux | grep funasr-wss-server | grep -v grep

# 检查端口
echo "Checking port 10095..."
netstat -tlnp | grep 10095

echo "FunASR service started on port 10095"
echo "View logs with: docker exec ${CONTAINER_NAME} tail -f /workspace/server.log"