#!/bin/bash
docker build --rm -f ./Dockerfile_py ./ -t ubuntu_py:24.04
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images
