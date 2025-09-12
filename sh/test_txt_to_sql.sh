#!/bin/bash

API="http://127.0.0.1:19000/txt/to/sql"

curl -s --noproxy '*' -w'\n' -X POST \
  -H "Content-Type: application/json" \
  "${API}" -d @- <<EOF
{
  "schema": "$(cat db_schema/mysql.test.order_info.sql | sed 's/"/\\"/g' | tr '\n' ' ')",
  "txt": "查询去年通过微信支付的天然气销售订单的总金额。",
  "dialect": "mysql"
}
EOF