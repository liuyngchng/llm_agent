#!/bin/bash
APP='chat2db'
CONTAINER="${APP}_app"
APP_DIR="apps/${APP}"
# 检查当前目录下是否存在目录 ${APP_DIR}
if [ ! -d ${APP_DIR} ]; then
    echo "错误：当前目录下未找到 ${APP_DIR} 文件夹"
    echo "请确保在项目根目录下执行此脚本"
    exit 1
fi
echo "正在检查必需的配置文件..."
required_files=("cfg.db" "cfg.yml" "logging.conf")
for file in "${required_files[@]}"; do
    if [ ! -f "${APP_DIR}/${file}" ]; then
        echo "错误：${APP_DIR}/${file} 文件不存在"
        exit 1
    fi
done
echo "正在复制 ${APP} 服务配置文件"
# 拷贝配置文件并检查是否成功
cp ${APP_DIR}/cfg.db ./ && \
cp ${APP_DIR}/cfg.yml ./ && \
cp ${APP_DIR}/logging.conf ./ || {
    echo "错误：配置文件拷贝失败"
    exit 1
}
echo "正在部署 ${APP} 服务"
docker stop ${CONTAINER}
echo "正在删除 ${CONTAINER} 容器"
docker rm ${CONTAINER}
echo "正在创建 ${CONTAINER} 容器"
#docker run -dit --name ${CONTAINER} --network host --rm \
docker run -dit --name ${CONTAINER}  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -v /data/dm8_client:/opt/dm8_client \
  -p 19001:19000 \
  -e APP_NAME=${APP} \
  llm_chat2db:1.1
echo "容器 ${CONTAINER} 已启动"
docker ps -a  | grep ${CONTAINER} --color=always
echo "部署完成"
docker logs -f ${CONTAINER}