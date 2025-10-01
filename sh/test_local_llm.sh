#!/bin/bash

curl http://localhost:8000/health

curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好，简单回答"}],
    "stream": false,
    "max_tokens": 50
  }'