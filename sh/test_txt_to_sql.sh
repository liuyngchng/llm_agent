#!/bin/bash

API="http://127.0.0.1:19000/txt/to/sql"

# 构建数据
DATA=$(cat <<EOF
{
  "schema": "$(cat db_schema/mysql.test.order_info.sql | sed 's/"/\\"/g' | tr '\n' ' ')",
  "txt": "查询去年通过微信支付的天然气销售订单的总金额。",
  "dialect": "mysql"
}
EOF
)

# 显示将要执行的命令
echo "执行的命令:"
echo "curl -s --noproxy '*' -w'\n' -X POST \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  \"${API}\" -d '${DATA}'"
echo ""
echo "响应:"

# 实际执行
curl -s --noproxy '*' -w'\n' -X POST \
  -H "Content-Type: application/json" \
  "${API}" -d "${DATA}"