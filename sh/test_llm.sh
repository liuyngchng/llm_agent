#!/bin/bash
API='https://aiproxy.petrotech.cnpc/v1/chat/completions'
TOKEN=$(head -n 1 llm_token.txt)
MODEL='deepseek-v3'
#MODEL='qwen2dot5-7b-chat'
#MODEL='kunlunllm-13b'
curl -ks --noproxy '*' \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
        "model": "'"${MODEL}"'",
        "messages": [
          {"role": "system", "content": "你是一名牙科医生."},
          {"role": "user", "content": "你好!"}
        ],
        "stream": false
      }' \
  "${API}" | jq