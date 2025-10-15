#!/bin/bash
# 兼容 OpenAI 的 api 的格式为 https://llm_api.your_orgnization_domain/v1
API=$(sed -n '1p' llm_token.txt)
TOKEN=$(sed -n '2p' llm_token.txt)
MODEL=$(sed -n '3p' llm_token.txt)
echo "API: ${API}"
echo "TOKEN: ${TOKEN}"
echo "MODEL: ${MODEL}"

# 函数：获取模型清单
get_models_list() {
    echo "正在获取模型清单..."
    curl -ks --noproxy '*' \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${TOKEN}" \
      "${API}/models" | jq
}

# 函数：与LLM聊天
chat_with_llm() {
    echo "正在与模型 ${MODEL} 对话..."
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
      "${API}/chat/completions" | jq
}

# 使用示例：
# 获取模型清单
get_models_list

echo "----------------------------------------"

# 与LLM聊天
chat_with_llm