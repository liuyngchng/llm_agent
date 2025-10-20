#!/bin/bash
WHL_PY_DIR="./whl_py_dir"
# 检查文件夹是否存在
if [ ! -d "${WHL_PY_DIR}" ]; then
    echo "未找到目录: ${WHL_PY_DIR} ，正在创建..."
    mkdir -p "${WHL_PY_DIR}"
    if [ $? -eq 0 ]; then
        echo "目录 ${WHL_PY_DIR} 创建成功"
    else
        echo "错误：目录 ${WHL_PY_DIR} 创建失败，退出执行"
        exit 1
    fi
fi
echo "进入目录:${WHL_PY_DIR}"
cd ${WHL_PY_DIR} || exit 1
echo "current_dir:$(pwd)"
pip download gunicorn flask \
    concurrent-log-handler langchain_openai langchain_core langchain_community \
    openai pandas tabulate pymysql oracledb dmPython sounddevice pydub pycryptodome wheel sympy markdown
cd ..
echo "current_dir:$(pwd)"
docker build --rm -f ./Dockerfile_chat2db ./ -t llm_chat2db:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f || true
docker images
