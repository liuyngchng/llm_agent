#!/bin/bash
API=$(sed -n '1p' llm_token.txt)
TOKEN=$(sed -n '2p' llm_token.txt)
MODEL=$(sed -n '3p' llm_token.txt)
echo "API: ${API}"
echo "TOKEN: ${TOKEN}"
echo "MODEL: ${MODEL}"

# 构建curl命令
CMD=$(cat <<EOF
curl -ks --noproxy '*' \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${TOKEN}" \\
  -d '{
        "model": "${MODEL}",
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
      }' \\
  "${API}"
EOF
)

# 打印要执行的命令
echo "执行的命令:"
echo "$CMD"
echo
echo "执行结果:"

# 执行命令并通过jq格式化输出
eval "$CMD" | jq