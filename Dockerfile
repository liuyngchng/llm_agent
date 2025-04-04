FROM ubuntu:24.04

WORKDIR /opt
ARG PROXY=""
# ARG PROXY=" -i http:///root/pypi/+simple --trusted-host devpi.11.11.77.81.nip.io"
#ARG PROXY=" -i https://pypi.tuna.tsinghua.edu.cn/simple"
RUN apt-get update
# for rag
# RUN apt-get -y install python3 python3-dev python3-pip virtualenv vim curl gcc g++ tesseract-ocr fonts-noto-color-emoji
# for sql_agent
RUN apt-get -y install python3 python3-dev python3-pip virtualenv vim curl
RUN apt-get clean
RUN virtualenv llm_py_env
RUN pwd
RUN ls llm_py_env/bin/activate
# RUN ["/bin/bash", "-c", "source llm_py_env/bin/activate"]

# for rag
# RUN ./llm_py_env/bin/pip install --no-cache-dir gunicorn langgraph langchain_ollama langchain_openai langchain_community langchain langchain_huggingface langchain_text_splitters langchain_huggingface langchain_unstructured unstructured unstructured[pdf] langchain_core flask pydantic python-docx nltk sentence-transformers faiss_cpu torch $PROXY

# for sql_agent
RUN ./llm_py_env/bin/pip install --no-cache-dir gunicorn flask langchain_openai langchain_ollama langchain_core langchain_community pandas tabulate pymysql
RUN  rm -rf ~/.cache/pip
RUN bash -c 'ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime'
RUN ulimit -n 65535

WORKDIR /opt/app
EXPOSE 19000
ENTRYPOINT ["sh", "./start.sh"]
