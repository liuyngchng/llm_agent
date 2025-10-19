#!/bin/bash
APP='docx'
CONTAINER='http_'${APP}
APP_DIR="apps/docx"
# 检查当前目录下是否存在 apps/txt2sql 文件夹
if [ ! -d ${APP_DIR} ]; then
    echo "错误：当前目录下未找到 ${APP_DIR} 文件夹"
    echo "请确保在项目根目录下执行此脚本"
    exit 1
fi
echo "正在复制 ${APP} 服务配置文件"
cp ${APP_DIR}/cfg.db ./
cp ${APP_DIR}/cfg.yml ./
cp ${APP_DIR}/logging.conf ./
echo "正在部署 ${APP} 服务"
docker stop ${CONTAINER}
echo "正在删除 ${APP} 服务"
docker rm ${CONTAINER}
echo "正在创建 ${CONTAINER} 容器"
#docker run -dit --name ${CONTAINER} --network host --rm \
docker run -dit --name ${CONTAINER}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/nltk_data:/usr/share/nltk_data \
  -p 19003:19000 \
  -e APP_NAME=${APP} \
  llm_docx:1.1
echo "容器 ${CONTAINER} 已启动"
docker ps -a  | grep ${CONTAINER} --color=always
echo "部署完成"
docker logs -f ${CONTAINER}
