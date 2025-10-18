#!/bin/bash

docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images