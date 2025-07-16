#!/bin/bash
docker build --rm -f ./Dockerfile_docx ./ -t llm_docx:1.0
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images
