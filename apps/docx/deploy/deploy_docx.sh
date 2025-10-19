#!/bin/bash
APP='docx'
CONTAINER='http_'${APP}
docker stop ${CONTAINER}
docker rm ${CONTAINER}
#docker run -dit --name ${CONTAINER} --network host --rm \
docker run -dit --name ${CONTAINER}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -p 19003:19000 \
  -e APP_NAME=${APP} \
  llm_docx:1.1

docker ps -a  | grep ${CONTAINER} --color=always
docker logs -f ${CONTAINER}
