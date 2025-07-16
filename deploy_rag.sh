#!/bin/bash
docker stop llm_rag
docker rm llm_rag
#docker run -dit --name llm_rag --network host --rm \
docker run -dit --name llm_rag  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -v /data/bge-large-zh-v1.5:/opt/bge-large-zh-v1.5 \
  -p 19002:19000 \
  llm_rag:1.1
