

curl -s -X POST http://127.0.0.1:16001/v1/messages \
  -H "x-api-key: sk-your-key" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 1024,
    "system": "你是个好助理",
    "temperature": 0.7,
    "stream": false
  }'