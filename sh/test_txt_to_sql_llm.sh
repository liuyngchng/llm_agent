#!/bin/bash

API="https://aiproxy.petrotech.cnpc/v1/chat/completions"
AUTH_TOKEN="sk-8rfeNuXkbyydz3cx5f7bEc5d778040Fc9374E056Df1c2fFe"

API=$(sed -n '1p' sh/llm_token.txt)
AUTH_TOKEN=$(sed -n '2p' sh/llm_token.txt)
MODEL=$(sed -n '3p' sh/llm_token.txt)
QUESTION=$(sed -n '1p' sh/user_question.txt)

# 读取表结构文件，并进行适当的转义
SCHEMA_CONTENT=$(cat db_schema/ai_meter_read_info.sql | sed 's/"/\\"/g' | sed 's/\\n/\\\\n/g' | tr -d '\n' | sed 's/\\$/\\\\/g')

# 构建数据
DATA=$(cat <<EOF
{
  "model": "${MODEL}",
  "messages": [
    {"role": "system", "content": "你是一名MySQL 数据库专家."},
    {"role": "user", "content": "用户提出的问题是：${QUESTION}\n数据库的表结构如下所示：\n${SCHEMA_CONTENT}\n请输出查询数据的SQL语句"}
  ],
  "stream": false
}
EOF
)

# 显示将要执行的命令（调试用）
echo "执行的命令:"
echo "curl -ks --tlsv1 --noproxy '*' -w'\n' -X POST \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"Authorization: Bearer ${AUTH_TOKEN}\" \\"
echo "  \"${API}\" -d '${DATA}'"
echo ""
echo "响应:"

# 实际执行，添加认证头
curl -ks --tlsv1 --noproxy '*' -w'\n' -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  "${API}" -d "${DATA}" 2>&1

# 检查退出状态
if [ $? -eq 0 ]; then
    echo ""
    echo "请求成功完成"
else
    echo ""
    echo "请求失败，退出码: $?"
fi