#!/bin/bash
API='https://aiproxy.petrotech.cnpc/v1/chat/completions'
TOKEN=$(head -n 1 llm_token.txt)
#MODEL='deepseek-v3'  # 可切换其他模型测试
#MODEL='deepseek-r1'
MODEL='qwen2dot5-7b-chat'
#MODEL='qwen2dot5-72b-chat'
#MODEL='kunlunllm-13b'
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
          {"role": "user", "content": "伦敦今天的天气怎么样?"}
        ],
        "tools": [{
          "type": "function",
          "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
              "type": "object",
              "properties": {
                "location": {"type": "string", "description": "城市名称"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
              },
              "required": ["location"]
            }
          }
        }],
        "stream": false
      }' \
  "${API}" | jq