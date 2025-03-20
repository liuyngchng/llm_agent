FROM ubuntu:22.04 

WORKDIR /opt
ARG PROXY=""
ARG PROXY=" -i http:///root/pypi/+simple --trusted-host devpi.11.11.77.81.nip.io"
#ARG PROXY=" -i https://pypi.tuna.tsinghua.edu.cn/simple"
RUN apt-get update
RUN apt-get -y install python3.10 python3.10-dev python3-pip virtualenv vim curl gcc g++ tesseract-ocr
RUN virtualenv llm_py_env
#RUN pwd
#RUN ls llm_py_env/bin/activate
RUN ["/bin/bash", "-c", "source llm_py_env/bin/activate"]
RUN pip install --no-cache-dir gunicorn langgraph langchain_ollama langchain_openai langchain_community langchain langchain_huggingface langchain_text_splitters langchain_huggingface langchain_unstructured unstructured unstructured[pdf] langchain_core flask pydantic python-docx nltk sentence-transformers faiss_gpu faiss_cpu torch $PROXY

RUN  rm -rf ~/.cache/pip
RUN bash -c 'ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime'
RUN ulimit -n 65535

WORKDIR /opt/app
EXPOSE 19000
ENTRYPOINT ["sh", "./start.sh"]
