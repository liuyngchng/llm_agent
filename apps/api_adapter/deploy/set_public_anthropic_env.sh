#!/bin/bash

export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=${DEEPSEEK_API_KEY}
export API_TIMEOUT_MS=600000
export ANTHROPIC_MODEL=deepseek-v4-pro
export ANTHROPIC_SMALL_FAST_MODEL=deepseek-v4-flash
# 防止联网验证、模型回退、检查更新失败导致的卡顿或错误
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
# 关闭计费头,加速推理
export CLAUDE_CODE_ATTRIBUTION_HEADER=0