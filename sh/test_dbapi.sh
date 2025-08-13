#!/bin/bash
# 从配置文件读取所有参数
API=$(sed -n '1p' dbapi_token.txt)     # 第一行: API地址
TOKEN=$(sed -n '2p' dbapi_token.txt)   # 第二行: TOKEN
NAME=$(sed -n '3p' dbapi_token.txt)    # 第三行: name
USER_ID=$(sed -n '4p' dbapi_token.txt)     # 第四行: uid
TENANT=$(sed -n '5p' dbapi_token.txt)  # 第五行: tenantName
echo 'API: '${API}
echo 'TOKEN: '${TOKEN}
echo 'NAME: '${NAME}
echo 'UID: '${USER_ID}
echo 'TENANT: '${TENANT}
SQL='select count(1) from a10analysis.ai_meter_info'
curl -ks --noproxy "*" \
    -H "Content-Type: application/json" \
    -H "token: ${TOKEN}" \
    -d '{
        "currentPage": "1",
        "pageSize": "20",
        "name": "'"${NAME}"'",
        "total": false,
        "script": "'"${SQL}"'",
        "tenantName": "'"${TENANT}"'",
        "uid": "'"${USER_ID}"'"
      }' \
  "${API}" | jq