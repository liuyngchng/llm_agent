#!/bin/bash
# 检查当前目录结构，确保上级目录为 build，上上级目录为 apps
GRANDPARENT_DIR_LEGAL="apps"
PARENT_DIR_LEGAL="docx"
APP="docx"
CURRENT_DIR=$(pwd)
echo "current_dir: ${CURRENT_DIR}"
PARENT_DIR=$(dirname "${CURRENT_DIR}")
echo "parent_dir: $(basename "${PARENT_DIR}")"
GRANDPARENT_DIR=$(dirname "${PARENT_DIR}")
echo "grandparent_dir: $(basename "${GRANDPARENT_DIR}")"

if [[ "$(basename "${PARENT_DIR}")" != "${PARENT_DIR_LEGAL}" ]]; then
    echo "错误：请在目录 ${GRANDPARENT_DIR_LEGAL}/${APP}/${PARENT_DIR_LEGAL} 下执行脚本"
    exit 1
fi

if [[ "$(basename "${GRANDPARENT_DIR}")" != "${GRANDPARENT_DIR_LEGAL}" ]]; then
    echo "错误：请在目录 ${GRANDPARENT_DIR_LEGAL}/${APP}/${PARENT_DIR_LEGAL} 下执行脚本"
    exit 1
fi

echo "当前目录为: ${GRANDPARENT_DIR_LEGAL}/${PARENT_DIR_LEGAL}/$(basename "${CURRENT_DIR}")"

WHL_PY_DIR="./whl_py_dir_${APP}"
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
read -p "是否需要下载依赖包？(Y/N): " confirm
if [[ $confirm == [Yy] ]]; then
    echo "进入目录:${WHL_PY_DIR}"
    cd ${WHL_PY_DIR} || exit 1
    echo "current_dir:$(pwd)"

    pip download gunicorn flask \
        langchain_openai langchain_community \
        langchain langchain_text_splitters langchain_unstructured unstructured \
        unstructured[pdf] langchain_core pydantic python-docx python-pptx pillow \
        concurrent_log_handler pydub pycryptodome wheel tabulate chromadb \
        lxml websockets markdown

    cd ..
else
    echo "跳过依赖包下载步骤，直接使用 ${WHL_PY_DIR} 目录下的包进行镜像构建"

    # 检查 whl_py_dir 目录是否存在以及是否有 .whl 文件
    if [ ! -d "${WHL_PY_DIR}" ]; then
        echo "错误：目录 ${WHL_PY_DIR} 不存在，无法进行镜像构建"
        exit 1
    fi

    # 检查目录下是否有 .whl 文件
    if ! ls ${WHL_PY_DIR}/*.whl 1> /dev/null 2>&1; then
        echo "错误：目录 ${WHL_PY_DIR} 下没有找到 .whl 文件，无法进行镜像构建"
        exit 1
    fi
fi
echo "current_dir:$(pwd)"
docker build --rm -f ./Dockerfile_${APP} ./ -t llm_${APP}:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images
