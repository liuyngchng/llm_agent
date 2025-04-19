#!/bin/bash
docker build --rm -f ./Dockerfile_nl2sql ./ -t llm_nl2sql:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -r
docker images
