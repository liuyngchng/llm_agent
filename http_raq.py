#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""

import logging.config
import os

from flask import Flask, request, jsonify, render_template
from semantic_search import search
from sys_init import init_yml_cfg

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)


@app.route('/', methods=['GET'])
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
    answer = search(msg, my_cfg, True)
    logger.info(f"answer is：{answer}")
    return answer

def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    logger.info(f"config {my_cfg}")
    my_question = "我想充值缴费？"
    logger.info(f"invoke question: {my_question}")

    answer = search(my_question, my_cfg, True)
    logger.info(f"answer is \r\n{answer}")


if __name__ == '__main__':
    # test_req()
    app.run(host='0.0.0.0', port=19000)
