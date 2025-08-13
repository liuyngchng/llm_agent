#!/bin/bash
TOKEN=$(head -n 1 llm_token.txt)
curl -ks --noproxy '*' -w'\n' --tlsv1 -X POST  'https://aiproxy.petrotech.cnpc/v1/embeddings' \
    -H "Content-Type: application/json" \
	  -H "Authorization: Bearer ${TOKEN}" \
    -d '{"model": "bge-m3","input": "本"}' | jq
