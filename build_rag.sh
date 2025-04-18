#!/bin/bash
# 将次文件拷贝至 python 离线 whl 目录所在的目录执行，同时修改自己 Dockerfile_rag 的真实绝对路径
docker build --rm -f ./Dockerfile_rag ./ -t llm_rag:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -r
docker images
