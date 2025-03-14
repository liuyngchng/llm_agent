#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
# from langchain_community.vectorstores import SQLiteVSS
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM

import logging.config
import httpx
from flask import Flask, request, jsonify, render_template

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

api_url = "https://127.0.0.1:19114"
api_key = "123456789"


def init_cfg(cfg_file: str):
    global api_url, api_key  # 添加全局声明
    with open(cfg_file) as f:
        lines = f.readlines()
    api_url = lines[0].strip()
    api_key = lines[1].strip()


def req_with_vector_db(question: str) -> str:
    """
    加载本地矢量数据库文件, 调用 LLM API, 进行 RAG, 输出结果
    """
    embedding_model = "../bge-large-zh-v1.5"
    # api_url = "http://127.0.0.1:11435"

    faiss_index = "./faiss_index"

    # llm_name = "llama3.1:8b"
    # llm_name = "llama3.2:3b-text-q5_K_M"
    llm_name = "deepseek-r1:7b"
    remote_llm_name = "deepseek-r1"
    # for test purpose only, read index from local file
    logger.info("embedding_model: {}".format(embedding_model))
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model, cache_folder='./bge-cache')
    logger.info("try to load index from local file")
    loaded_index = FAISS.load_local(faiss_index, embeddings,
                                    allow_dangerous_deserialization=True)
    # loaded_index = SQLiteVSS.create_connection(db_file="/sqlite/vss.db")
    logger.info("load index from local file finish")

    # 创建远程 Ollama API代理
    logger.info("get remote llm agent")
    # 可调用无需 api_key 的model
    llm = OllamaLLM(model=llm_name, base_url=api_url)

    # 调用需要 api_key 的 model
    llm = ChatOpenAI(api_key=api_key, base_url=api_url, http_client=httpx.Client(verify=False), model=remote_llm_name)
    # 创建检索问答链
    logger.info("build retrieval")
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=loaded_index.as_retriever())

    # qa = RetrievalQA.from_chain_type(
    #     llm=llm,
    #     chain_type="map_reduce",
    #     retriever=loaded_index.as_retriever(search_kwargs={"k": 2, "score_threshold": 0.7}),
    #     return_source_documents=True
    # )
    # 提问
    logger.info("invoke retrieval {} to uri {}".format(question, api_url))
    result = qa.invoke(question)
    answer = result["result"]
    logger.info("answer is {}".format(answer))
    return answer


@app.route('/')
def index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    return render_template('index.html')


@app.route('/health', methods=['POST'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'
    :return:
    """
    data = request.get_json()
    print(data)
    return jsonify({"message": "Data received successfully!", "data": data}), 200


@app.route('/submit', methods=['POST'])
def submit():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg')
    logger.info("rcv_msg: {}".format(msg))
    answer = req_with_vector_db(msg)
    logger.info("answer is：{}".format(answer))
    return answer


def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "巴拉巴拉小魔仙是什么？"
    logger.info("invoke question: {}".format(my_question))
    answer = req_with_vector_db(my_question)
    logger.info("answer is {}".format(answer))


if __name__ == '__main__':
    # test_req()

    """
    just for test, not for a production environment.
    """
    init_cfg("env.cfg")
    logger.info("api_url={}, api_key={}".format(api_url, api_key))
    app.run(host='0.0.0.0', port=19000)
