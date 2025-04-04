#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""

import logging.config
import os

from flask import Flask, request, jsonify, render_template
from semantic_search import search

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
    app.run(host='0.0.0.0', port=19000)
