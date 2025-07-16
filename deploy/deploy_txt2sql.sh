#!/bin/bash
app='http_txt2sql'
docker stop ${app}
docker rm ${app}
#docker run -dit --name llm_nl2sql --network host --rm \
docker run -dit --name ${app}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 19001:19000 \
  llm_rag:1.1

docker ps -a  | grep ${app} --color=always
docker logs -f ${app}