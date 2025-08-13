#!/bin/bash
curl -X POST "http://127.0.0.1:8000/v1/embed" \
	-H "Content-Type: application/json" \
	-d '{"model": "bge-m3", "text": "需要编码的文本"}'
	
	
curl -ks --noproxy '*' -w'\n' --tlsv1 -X POST  'https://aiproxy.petrotech.cnpc/v1/embeddings' \
	-H "Content-Type: application/json"\
	-H 'Authorization: Bearer sk-8r****Fe'\
	-d '{"model": "bge-m3","input": "本"}' | jq	
