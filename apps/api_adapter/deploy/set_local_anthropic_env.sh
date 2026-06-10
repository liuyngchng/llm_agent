#!/bin/bash

# 检查 LOCAL_LLM_API_KEY 环境变量
if [ -z "${LOCAL_LLM_API_KEY}" ]; then
    echo "错误: LOCAL_LLM_API_KEY 环境变量未设置"
    exit 1
else
    echo "LOCAL_LLM_API_KEY 已设置: ${LOCAL_LLM_API_KEY}"
fi

# 探测 16001 端口服务是否启动
echo "正在检查 127.0.0.1:16001 端口服务..."
if timeout 3 bash -c "echo >/dev/tcp/127.0.0.1/16001" 2>/dev/null; then
    echo "端口 16001 服务已启动"
else
    echo "错误: 端口 16001 服务未启动或无法连接"
    exit 1
fi

# 设置环境变量
export ANTHROPIC_BASE_URL=http://127.0.0.1:16001
export ANTHROPIC_AUTH_TOKEN=${LOCAL_LLM_API_KEY}
export API_TIMEOUT_MS=600000
export ANTHROPIC_MODEL=deepseek-chat
export ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat

echo "本地 ANTHROPIC 环境变量设置完成"
