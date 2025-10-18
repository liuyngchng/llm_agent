#!/bin/bash
WHL_PY_DIR="./whl_py_dir"
# 检查文件夹是否存在
if [ ! -d "${WHL_PY_DIR}" ]; then
    echo "错误：未找到 Python whl 依赖包的本地目录: ${WHL_PY_DIR} ，退出执行"
    exit 1
fi
cd ${WHL_PY_DIR}
echo "current_dir:`pwd`"
pip download gunicorn \
    langgraph langchain_ollama langchain_openai langchain_community \
    langchain langchain_huggingface langchain_text_splitters langchain_huggingface langchain_unstructured unstructured \
    unstructured[pdf] langchain_core flask flask_cors pydantic python-docx python-pptx pillow nltk sentence-transformers torch \
    concurrent_log_handler pydub pycryptodome wheel qrcode[pil] tabulate chromadb \
    pypdf2 lxml websockets markdown
cd ..
echo "current_dir:`pwd`"
docker build --rm -f ./Dockerfile_docx ./ -t llm_docx:1.0
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi -f
docker images
