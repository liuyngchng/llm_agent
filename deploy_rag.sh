docker stop llm_rag
#docker run -dit --name llm_rag --network host --rm \
docker run -dit --name llm_rag  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 19002:19000 \
  llm_rag:1.1
