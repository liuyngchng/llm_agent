#!/bin/bash
APP='chat2db'
CONTAINER="${APP}_app"
APP_DIR="apps/${APP}"
docker stop ${CONTAINER}
docker rm ${CONTAINER}
#docker run -dit --name ${CONTAINER} --network host --rm \
docker run -dit --name ${CONTAINER}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 18000:19000 \
  -e APP_NAME=${app} \
  llm_chat2db:1.1

docker ps -a  | grep ${CONTAINER} --color=always
docker logs -f ${CONTAINER}