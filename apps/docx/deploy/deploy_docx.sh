#!/bin/bash
app='http_docx'
docker stop ${app}
docker rm ${app}
#docker run -dit --name ${app} --network host --rm \
docker run -dit --name ${app}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -p 19003:19000 \
  -e MODULE_NAME=${app} \
  llm_rag:1.1

docker ps -a  | grep ${app} --color=always
docker logs -f ${app}
