#!/bin/bash
APP='txt2sql'
CONTAINER='http_'${APP}
docker stop ${CONTAINER}
docker rm ${CONTAINER}
#docker run -dit --name ${CONTAINER} --network host --rm \
docker run -dit --name ${CONTAINER}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/dm8_client:/opt/dm8_client \
  -p 19001:19000 \
  -e APP_NAME=${APP} \
  llm_txt2sql:1.1

docker ps -a  | grep ${CONTAINER} --color=always
docker logs -f ${CONTAINER}