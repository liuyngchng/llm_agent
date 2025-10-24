#!/bin/bash

PROXY='-i http://devpi.11.11.77.81.nip.io/root/pypi/+simple --trusted-host devpi.11.11.77.81.nip.io'
echo ${PROXY}
pip install gunicorn flask \
    langchain_openai langchain_community \
    langchain langchain_text_splitters langchain_unstructured unstructured \
    unstructured[pdf] langchain_core pydantic python-docx python-pptx pillow \
    concurrent_log_handler pydub pycryptodome wheel tabulate chromadb \
    lxml websockets markdown ${PROXY}