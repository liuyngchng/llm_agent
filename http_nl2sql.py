#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama langchain_core langchain_community pandas tabulate pymysql
"""

import logging.config
import os

from flask import Flask, request, jsonify, render_template
from sql_agent import get_dt_with_nl
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
# my_api_uri = my_cfg["ai"]["api_uri"]
# my_api_key = my_cfg["ai"]["api_key"]
# my_model_name = my_cfg["ai"]["model_name"]
# my_db_uri = my_cfg["db"]["uri"]

@app.route('/', methods=['GET'])
def query_data_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    dt_idx = "nl2sql_index.html"
    logger.info(f"return page {dt_idx}")
    return render_template(dt_idx)

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

@app.route('/query/data', methods=['POST'])
def query_data():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg').strip()
    logger.info(f"rcv_msg: {msg}")
    logger.info(f"ask_question({msg}, {my_cfg}, html, True)")
    answer = get_dt_with_nl(msg, my_cfg, 'html', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"

    return answer

@app.route('/gt/db/dt', methods=['POST'])
def get_db_dt():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000//gt/db/dt' -H "Content-Type: application/json"  -d '{"msg":"把数据明细给我调出来"}'
    :return:
    """
    msg = request.get_json().get('msg').strip()
    logger.info(f"rcv_msg: {msg}")
    logger.info(f"ask_question({msg}, {my_cfg}, 'json')")
    answer = get_dt_with_nl(msg, my_cfg, 'json', True)
    # logger.debug(f"answer is：{answer}")
    if not answer:
        answer='{"msg":"没有查询到相关数据，请您尝试换个问题进行提问", "code":404}'

    return answer

def test_query_data():
    """
    for test purpose only
    """
    msg = "查询2025年的数据"
    logger.info(f"ask_question({msg}, {my_cfg}, markdown, True)")
    answer = get_dt_with_nl(msg, my_cfg, 'markdown', True)
    if not answer:
        answer="没有查询到相关数据，请您尝试换个问题提问"
    logger.info(f"answer is：\n{answer}")
    return answer


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    logger.info(f"my_cfg {my_cfg}")
    # test_query_data()
    app.run(host='0.0.0.0', port=19000)
