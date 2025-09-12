#!/bin/bash
app='http_open_api'
docker stop ${app}
docker rm ${app}
#docker run -dit --name llm_nl2sql --network host --rm \
docker run -dit --name ${app}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 18000:19000 \
  -e MODULE_NAME=${app} \
  llm_rag:1.1

docker ps -a  | grep ${app} --color=always
docker logs -f ${app}