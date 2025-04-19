#!/bin/bash
docker build --rm -f ./Dockerfile_rag ./ -t llm_rag:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -r
docker images
