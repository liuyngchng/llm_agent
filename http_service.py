#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import logging.config
import os

from flask import Flask, request, jsonify, render_template
from semantic_search import search
from sql_agent import ask_question

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

api_uri = ""
api_key = ""
model_name = ""
def init_cfg(cfg_file="env.cfg")-> dict[str, str] | None:
    # global api_uri, api_key, model_name
    _my_cfg = {"api_uri":"http://127.0.0.1:11434", "api_key":"", "model_name":"deepseek-r1"}
    with open(cfg_file) as f:
        lines = f.readlines()
    if len(lines) < 2:
        logger.error("cfg_err_in_file_{}".format(cfg_file))
        return _my_cfg
    try:
        _my_cfg["api_uri"] = lines[0].strip()
        _my_cfg["api_key"] = lines[1].strip()
        _my_cfg["model_name"] = lines[2].strip()
        logger.info(f"init_cfg_info, {_my_cfg}")
    except Exception as e:
        logger.error("init_cfg_error: {}".format(e))
    return _my_cfg

@app.route('/rag', methods=['GET'])
def rag_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    return render_template('rag_index.html')

@app.route('/query', methods=['GET'])
def query_data_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    return render_template('query_data_index.html')

@app.route('/health', methods=['GET'])
@app.route('/', methods=['GET'])
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
    logger.info("answer is：{}".format(answer))
    return answer
@app.route('/query/data', methods=['POST'])
def query_data():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg')
    logger.info("rcv_msg: {}".format(msg))
    #answer = search(msg, True)
    db_file = "test1.db"
    db_uri = f"sqlite:///{db_file}"
    logger.info(f"ask_question({msg}, {db_uri}, {api_uri}, {api_key}, {model_name}, True)")
    answer = ask_question(msg, db_uri, api_uri, api_key, model_name, True)

    if not answer:
        answer="没有查询到数据，请您尝试换个问题提问"
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
    os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    my_cfg = init_cfg()
    api_uri = my_cfg["api_uri"]
    api_key = my_cfg["api_key"]
    model_name = my_cfg["model_name"]
    logger.info(f"api_uri {api_uri}, api_key {api_key}, model_name {model_name}")
    app.run(host='0.0.0.0', port=19000)
