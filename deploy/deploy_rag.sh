#!/bin/bash
app='llm_rag'
docker stop ${app}
docker rm ${app}
#docker run -dit --name ${app} --network host --rm \
docker run -dit --name ${app}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -v /data/bge-large-zh-v1.5:/opt/bge-large-zh-v1.5 \
  -p 19002:19000 \
  llm_rag:1.1
