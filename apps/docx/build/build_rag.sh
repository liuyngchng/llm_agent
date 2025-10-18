#!/bin/bash
LLM_PY_ENV="./llm_py_env"
# 检查文件夹是否存在
if [ ! -d "${LLM_PY_ENV}" ]; then
    echo "错误：未找到Pyton安装包的本地目录: ${LLM_PY_ENV} ，退出执行"
    exit 1
fi
docker build --rm -f ./Dockerfile_rag ./ -t llm_rag:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images
