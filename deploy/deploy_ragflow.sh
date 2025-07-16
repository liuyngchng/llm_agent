#!/bin/bash
app='ragflow'
docker stop ${app}
docker rm ${app}
docker run -dit \
  -v /home/rd/workspace/ragflow:/ragflow \
  --name ragflow \
  --network host \
  ragflow:v0.12.0
docker logs -f ${app}