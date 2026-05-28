#!/bin/bash

mkdir -p /data/claw/workspace
docker stop my_claw
docker rm my_claw

# 运行容器
docker run -dit \
  --security-opt seccomp=unconfined 	\
	--security-opt apparmor=unconfined 	\
	--privileged \
  --name my_claw \
  -p 18789:18789 \
  -v /data/claw:/root/.openclaw \
  openclaw:1.0


# 进入容器
docker exec -it my_claw bash