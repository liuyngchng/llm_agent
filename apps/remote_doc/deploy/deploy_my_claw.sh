#!/bin/bash
APP="openclaw"
CONTAINER="openclaw-gateway"
echo "开始部署 ${APP} 服务"
docker stop ${CONTAINER}
echo "正在删除 ${APP} 服务"
docker rm ${CONTAINER}
echo "开始创建 ${CONTAINER} 容器"
docker run -dit \
  --name ${CONTAINER} \
  --rm \
  -v /data/openclaw:/root/.openclaw \
  -v /data/remote/workspace:/root/.openclaw/workspace \
  -e NODE_TLS_REJECT_UNAUTHORIZED=0 \
  -e TZ=Asia/Shanghai \
  -e LANG=C.UTF-8 \
  -e LC_ALL=C.UTF-8 \
  -p 19001:18789 \
  ghcr.io/openclaw/openclaw:latest \
  openclaw gateway run --allow-unconfigured
echo "容器 ${CONTAINER} 已启动"
docker ps -a  | grep ${CONTAINER} --color=always
echo "部署完成"
docker logs -f ${CONTAINER}
