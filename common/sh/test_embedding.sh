#!/bin/bash

API=$(sed -n '1p' llm_token.txt)
TOKEN=$(sed -n '2p' llm_token.txt)
MODEL=$(sed -n '3p' llm_token.txt)
echo "API: ${API}"
echo "TOKEN: ${TOKEN}"
echo "MODEL: ${MODEL}"
curl -ks --noproxy '*' -w'\n' --tlsv1 -X POST  "${API}/embeddings" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d @- <<EOF | jq
{
    "model": "${MODEL}",
    "input": "这就是一个测试而已，别太上心了"
}
EOF
