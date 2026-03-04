curl https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-ant-apikey-your-real-key-here" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-haiku-20240307",
    "max_tokens": 200,
    "messages": [
      {"role": "user", "content": "写一首关于春天的五言绝句"}
    ]
  }'