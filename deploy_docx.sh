#!/bin/bash
docker stop llm_docx
docker rm llm_docx
#docker run -dit --name llm_docx --network host --rm \
docker run -dit --name llm_docx  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 19003:19000 \
  llm_rag:1.1
