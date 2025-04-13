curl -s http://127.0.0.1:8000/v1/models | jq

curl -ks --noproxy '*' -w'\n' --tlsv1 -X POST  'http://127.0.0.1:8000/v1/audio/transcriptions' \
	-H "Content-Type: multipart/form-data" \
	-H 'Authorization: Bearer sk-123' \
	-F "language=zh" \
	-F "task=transcribe" \
	-F "file=@static/asr_example_zh.wav" \
	-F "model=whisper-large-v3-turbo" | jq


curl -s --noproxy '*' -w '\n' -X POST 'http://localhost:19000/trans/audio' \
  -F 'audio=@static/asr_test.webm'