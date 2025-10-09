#!/bin/bash
app='http_txt2sql'
docker stop ${app}
docker rm ${app}
#docker run -dit --name llm_nl2sql --network host --rm \
docker run -dit --name ${app}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/dm8_client:/opt/dm8_client \
  -p 19001:19000 \
  -e MODULE_NAME=${app} \
  llm_txt2sql:1.1

docker ps -a  | grep ${app} --color=always
docker logs -f ${app}