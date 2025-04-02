#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""

import logging.config
import os

from flask import Flask, request, jsonify, render_template
from semantic_search import search
from sql_agent import get_dt_with_nl
from sys_init import init_cfg

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_api_uri = ""
my_api_key = ""
my_model_name = ""
my_db_uri = ""

@app.route('/rag', methods=['GET'])
def rag_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    return render_template('rag_index.html')

@app.route('/', methods=['GET'])
def query_data_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    return render_template('query_data_index.html')

@app.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'
    :return:
    """
    data = request.get_json()
    print(data)
    return jsonify({"message": "Data received successfully!", "data": data}), 200


@app.route('/rag/submit', methods=['POST'])
def submit():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg')
    logger.info("rcv_msg: {}".format(msg))
    #answer = search(msg, True)
    answer = search(msg)
    logger.info(f"answer is：{answer}")
    return answer
@app.route('/query/data', methods=['POST'])
def query_data():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg').strip()
    logger.info(f"rcv_msg: {msg}")
    req_db_uri = request.form.get('db_uri')
    global my_db_uri
    if req_db_uri:
        my_db_uri = req_db_uri
    logger.info(f"ask_question({msg}, {my_db_uri}, {my_api_uri}, {my_api_key}, {my_model_name}, html, True)")
    answer = get_dt_with_nl(msg, my_db_uri, my_api_uri, my_api_key, my_model_name, 'html', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"

    return answer

@app.route('/gt/db/dt', methods=['POST'])
def get_db_dt():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg').strip()
    logger.info(f"rcv_msg: {msg}")
    req_db_uri = request.form.get('db_uri')
    global my_db_uri
    if req_db_uri:
        my_db_uri = req_db_uri
    logger.info(f"ask_question({msg}, {my_db_uri}, {my_api_uri}, {my_api_key}, {my_model_name}, 'json')")
    answer = get_dt_with_nl(msg, my_db_uri, my_api_uri, my_api_key, my_model_name, 'json', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer='{"msg":"没有查询到相关数据，请您尝试换个问题进行提问", "code":404}'

    return answer

def test_query_data(db_uri: str):
    """
    for test purpose only
    """
    msg = "查询2025年的数据"
    logger.info(f"rcv_msg: {msg}")

    # for sqlite
    # db_file = "test1.db"
    # db_uri = f"sqlite:///{db_file}"

    # for MySQL
    # db_uri = "mysql+pymysql://db_user:db_password@db_host/db_name"

    logger.info(f"ask_question({msg}, {db_uri}, {my_api_uri}, {my_api_key}, {my_model_name}, markdown, True)")
    answer = get_dt_with_nl(msg, db_uri, my_api_uri, my_api_key, my_model_name, 'markdown', True)
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"
    logger.info(f"answer is：\n{answer}")
    return answer

def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "居民如何开户？"
    logger.info(f"invoke question: {my_question}")
    answer = search(my_question, True)
    logger.info(f"answer is {answer}")


if __name__ == '__main__':
    # init_cfg()
    # test_req()

    """
    just for test, not for a production environment.
    """
    os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    my_cfg = init_cfg()
    my_api_uri = my_cfg["api_uri"]
    my_api_key = my_cfg["api_key"]
    my_model_name = my_cfg["model_name"]
    my_db_uri = my_cfg["db_uri"]
    logger.info(f"api_uri {my_api_uri}, api_key {my_api_key}, model_name {my_model_name}, db_uri {my_db_uri}")

    # test_query_data(db_uri)
    app.run(host='0.0.0.0', port=19000)
