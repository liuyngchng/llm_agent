#!/bin/bash
API=$(sed -n '1p' llm_token.txt)
TOKEN=$(sed -n '2p' llm_token.txt)
MODEL=$(sed -n '3p' llm_token.txt)
echo "API: ${API}"
echo "TOKEN: ${TOKEN}"
echo "MODEL: ${MODEL}"
# 其中的 tools 部分对于支持 tools 函数调用的模型是必须的
curl -ks --noproxy '*' \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
        "model": "'"${MODEL}"'",
        "messages": [
          {"role": "system", "content": "你是一名气象信息向导."},
          {"role": "user", "content": "你都知道什么知识?"}
        ],
        "stream": false
      }' \
  "${API}" | jq