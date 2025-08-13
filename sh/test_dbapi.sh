API=$(head -n 1 dbapi_token.txt)                # 第一行作为API
TOKEN=$(head -n 2 dbapi_token.txt | tail -n 1)  # 第二行作为TOKEN
SQL='select count(1) from a10analysis.ai_gas_pay'
curl -ks --noproxy "*" \
    -H "Content-Type: application/json" \
    -H "token: ${TOKEN}" \
    -d '{
        "currentPage": "1",
        "pageSize": "20",
        "name": "a10analysis",
        "total": false,
        "script": "'"${SQL}"'",
        "tenantName": "trqgd",
        "uid": "50615629"
      }' \
  "${API}" | jq