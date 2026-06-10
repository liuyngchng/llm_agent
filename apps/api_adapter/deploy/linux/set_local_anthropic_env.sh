#!/bin/bash
# 动态获取脚本名称和路径
SCRIPT_NAME=$(basename "$BASH_SOURCE")
SCRIPT_PATH=$(realpath "$BASH_SOURCE")

# 提示用户必须使用 source 执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "错误：请使用 source 执行此脚本"
    echo "正确用法：source $SCRIPT_PATH"
    echo "或者：. $SCRIPT_PATH"
    return 1 2>/dev/null || exit 1
fi

echo "正在执行: $SCRIPT_NAME"
# 检查 LOCAL_LLM_API_KEY 环境变量
if [ -z "${LOCAL_LLM_API_KEY}" ]; then
    echo "错误: LOCAL_LLM_API_KEY 环境变量未设置"
    return 1
else
    echo "LOCAL_LLM_API_KEY 已设置: ${LOCAL_LLM_API_KEY}"
fi

# 探测 16001 端口服务是否启动
echo "正在检查 127.0.0.1:16001 端口服务..."
if timeout 3 bash -c "echo >/dev/tcp/127.0.0.1/16001" 2>/dev/null; then
    echo "端口 16001 服务已启动"
else
    echo "错误: 端口 16001 服务未启动或无法连接"
    return 1
fi

# 设置环境变量
export ANTHROPIC_BASE_URL=http://127.0.0.1:16001
export ANTHROPIC_AUTH_TOKEN=${LOCAL_LLM_API_KEY}
export API_TIMEOUT_MS=600000
export ANTHROPIC_MODEL=deepseek-chat
export ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_ATTRIBUTION_HEADER=0

echo -e "\033[32m✅ 本地 ANTHROPIC 环境变量设置完成\033[0m"
