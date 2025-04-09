#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""

import logging.config
import os

from flask import Flask, request, jsonify, render_template, Response
from semantic_search import search, classify_question
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
    ctx = {
        "sys_name" : my_cfg['sys']['name'],

    }
    idx = 'rag_index.html'
    logger.info(f"return page {idx}")
    return render_template(idx, **ctx)



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
    labels = ["缴费", "上门服务", "其他"]
    classify_result = classify_question(msg, my_cfg, True)
    logger.info(f"classify_result: {classify_result}")
    content_type='text/markdown; charset=utf-8'
    if labels[0] in classify_result:
        answer = search(msg, my_cfg, True)
    elif labels[1] in classify_result:
        with open('static/service1.html', 'r', encoding='utf-8') as file:
            content = file.read()
        content_type = 'text/html; charset=utf-8'
        answer = f"<div>请填写以下表格，我们将安排工作人员上门为您提供服务</div> {content}"
    else:
        answer = "目前还没有有效的信息提供给您"
    logger.info(f"answer is：{answer}")
    return Response(answer, content_type=content_type, status=200)
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
