#!/bin/bash
if [ $# -eq 0 ]; then
    echo "错误：请提供图片文件名作为参数"
    exit 1
fi
#your llm config file, api_uri in first line and api_token in second line
config_file="llm_token.txt"
if [ ! -f "${config_file}" ]; then
    echo "错误：LLM 配置文件 $config_file 不存在"
    exit 1
fi
api_uri=$(sed -n '1p' "$config_file")
api_token=$(sed -n '2p' "$config_file")
model_name="qwen2-7b-vl"
echo "api_uri=${api_uri}, api_token=${api_token}, model_name=${model_name}"
image_path="$1"
echo "image_path=${image_path}"
mime_type="image/$(file -b --mime-type "$image_path" | cut -d'/' -f2)"
echo "mime_type=${mime_type}"
image_base64=$(base64 -i "${image_path}" -w 0 | awk -v type="${mime_type}" '{print "data:" type ";base64,"$0}')

tmpfile=$(mktemp)

cat <<EOF > "$tmpfile"
{
  "model": "${model_name}",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "输出图片中的文字"},
        {
          "type": "image_url",
          "image_url": {
            "url": "${image_base64}"
          }
        }
      ]
    }
  ],
  "max_tokens": 2000
}
EOF

# 读取临时文件内容
json_data=$(cat "$tmpfile")

# 打印完整的curl命令（两种方式）

echo "方式1 - 使用临时文件:"
echo "curl -ks --noproxy '*' '${api_uri}' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer ${api_token}' \\"
echo "  -d '@$tmpfile'"
echo ""

echo "方式2 - 直接包含JSON数据:"
echo "curl -ks --noproxy '*' '${api_uri}' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer ${api_token}' \\"
echo "  -d '${json_data}'"
echo ""

# 执行curl命令（使用临时文件方式更安全）并统计时间
echo "执行结果:"
start_time=$(date +%s)
#https://you_host:/v1/chat/completions
curl -ks --noproxy '*' "${api_uri}/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${api_token}" \
  -d "@$tmpfile"
end_time=$(date +%s)

# 计算执行时间（秒）
execution_time=$((end_time - start_time))
echo ""
echo "执行时间: ${execution_time} 秒"

rm -f "$tmpfile"