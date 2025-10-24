#!/bin/bash
APP='chat'
CONTAINER=="${APP}_app"
docker stop ${CONTAINER}
docker rm ${CONTAINER}
#docker run -dit --name ${CONTAINER} --network host --rm \
docker run -dit --name ${CONTAINER}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -v /data/bge-large-zh-v1.5:/opt/bge-large-zh-v1.5 \
  -p 19002:19000 \
  -e APP_NAME=${APP} \
  llm_docx:1.1

docker ps -a  | grep ${CONTAINER} --color=always
docker logs -f ${CONTAINER}
