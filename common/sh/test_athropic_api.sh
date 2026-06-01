

curl -s -X POST http://127.0.0.1:16001/v1/messages \
  -H "x-api-key: sk-8rfeNuXkbyydz3cx5f7bEc5d778040Fc9374E056Df1c2fFe" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 1024,
    "system": "You are a helpful assistant",
    "temperature": 0.7,
    "stream": false
  }'