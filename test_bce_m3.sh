curl -X POST "http://127.0.0.1:8000/v1/embed" \
	-H "Content-Type: application/json" \
	-d '{"model": "bge-m3", "text": "需要编码的文本"}'