#!/bin/bash
WHL_PY_DIR="./whl_py_dir"
# 检查文件夹是否存在
if [ ! -d "${WHL_PY_DIR}" ]; then
    echo "错误：未找到 Python whl 依赖包的本地目录: ${WHL_PY_DIR} ，退出执行"
    exit 1
fi
cd ${WHL_PY_DIR}
echo "current_dir:`pwd`"
pip download gunicorn flask \
    concurrent-log-handler langchain_openai langchain_core langchain_community \
    openai pandas tabulate pymysql oracledb dmPython sounddevice pydub pycryptodome wheel sympy markdown
cd ..
echo "current_dir:`pwd`"
docker build --rm -f ./Dockerfile_txt2sql ./ -t llm_txt2sql:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f || true
docker images
