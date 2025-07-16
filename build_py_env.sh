#!/bin/bash
docker_file='./Dockerfile_py'
img='ubuntu_py:24.04'
echo "build with file ${docker_file}, from image ${img}"
docker build --rm -f ${docker_file} ./ -t ${img}
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images
