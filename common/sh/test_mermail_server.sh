#!/bin/bash
# 读取 mermaid_script.txt 内容
script_content=$(cat mermaid_script.txt)

# 发送请求生成 PNG 图片
curl -X POST http://11.10.36.2:8000/png \
  -H "Content-Type: text/plain" \
  -d "$script_content" \
  --output my_graph.png