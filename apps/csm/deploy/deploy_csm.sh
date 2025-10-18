#!/bin/bash
app='http_csm'
docker stop ${app}
docker rm ${app}
#docker run -dit --name ${app} --network host --rm \
docker run -dit --name ${app}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -v /data/bge-large-zh-v1.5:/opt/bge-large-zh-v1.5 \
  -p 19004:19000 \
  -e MODULE_NAME=${app} \
  llm_docx:1.1

docker ps -a  | grep ${app} --color=always
docker logs -f ${app}
