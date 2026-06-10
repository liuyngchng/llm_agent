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

export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=${DEEPSEEK_API_KEY}
export API_TIMEOUT_MS=600000
export ANTHROPIC_MODEL=deepseek-v4-pro
export ANTHROPIC_SMALL_FAST_MODEL=deepseek-v4-flash
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_ATTRIBUTION_HEADER=0

echo -e "\033[32m✅ 公网 ANTHROPIC 环境变量设置完成\033[0m"