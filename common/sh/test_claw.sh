#!/bin/bash

mkdir -p /data/claw
docker stop my_claw
docker rm my_claw

# 运行容器
docker run -dit \
  --security-opt seccomp=unconfined 	\
	--security-opt apparmor=unconfined 	\
	--privileged \
  --name my_claw \
  -p 38789:18789 \
  -p 38790:18790 \
  -p 38791:18791 \
  -v /data/claw:/root/.openclaw \
  openclaw:1.0


# 进入容器
docker exec -it my_claw bash