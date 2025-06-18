#!/bin/bash
if [ $# -eq 0 ]; then
    echo "错误：请提供图片文件名作为参数"
    exit 1
fi
api_uri='https://123.456'
api_token='sk-123.456'
echo "api_uri=${api_uri}, api_token=${api_token}"
image_path="$1"
echo "image_path=${image_path}"
mime_type="image/$(file -b --mime-type "$image_path" | cut -d'/' -f2)"
echo "mime_type=${mime_type}"
image_base64=$(base64 -i "${image_path}" -w 0 | awk -v type="${mime_type}" '{print "data:" type ";base64,"$0}')

# 使用临时文件存储JSON数据（解决参数过长问题）
tmpfile=$(mktemp)

# 生成带图片的JSON请求体
cat <<EOF > "$tmpfile"
{
  "model": "qwen2-7b-vl",
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


echo "request llm_api ${api_uri}"
curl -ks --noproxy '*' ${api_uri}  \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${api_token}" \
  -d "@$tmpfile" | jq

# 清理临时文件
rm -f "$tmpfile"