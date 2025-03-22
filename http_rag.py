#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import logging.config

from flask import Flask, request, jsonify, render_template
from semantic_search import search, init_cfg

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)



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
    #answer = search(msg, True)
    answer = search(msg)
    logger.info("answer is：{}".format(answer))
    return answer


def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "居民如何开户？"
    logger.info("invoke question: {}".format(my_question))
    answer = search(my_question, True)
    logger.info("answer is {}".format(answer))


if __name__ == '__main__':
    # init_cfg()
    # test_req()

    """
    just for test, not for a production environment.
    """
    init_cfg()
    app.run(host='0.0.0.0', port=19000)
