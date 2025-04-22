#!/bin/bash

PROXY='-i http://devpi.11.11.77.81.nip.io/root/pypi/+simple --trusted-host devpi.11.11.77.81.nip.io'
echo ${PROXY}
pip install gunicorn \
    langgraph langchain_ollama langchain_openai langchain_community \
    langchain langchain_huggingface langchain_text_splitters langchain_huggingface langchain_unstructured unstructured \
    unstructured[pdf] langchain_core flask pydantic python-docx nltk sentence-transformers faiss_cpu torch \
    concurrent_log_handler pymysql cx_Oracle sounddevice pydub pycryptodome wheel qrcode[pil] lxml tabulate ${PROXY}