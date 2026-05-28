#!/bin/bash

# 运行容器
docker run -dit \
  --name my_claw \
  -p 19001:18789 \
  -v /data/claw/workspace:/root/.openclaw/workspace \
  openclaw:1.0


# 进入容器
docker exec -it my_claw bash