#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import json
import logging.config
import os
import time

from flask import Flask, render_template, Response, request

from my_enums import DataType
from sql_yield import SqlYield
from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False
my_cfg = init_yml_cfg()

@app.route('/', methods=['GET'])
def stream_index():
    logger.info("render stream.html")
    return render_template('stream.html')

@app.route('/stream', methods=['POST', 'GET'])
def stream():
    t = int(request.args.get('t', 0))
    q = request.args.get('q', '')
    logger.info(f"rcv_req, t={t}, q={q}")
    sql_yield = SqlYield(my_cfg)
    return Response(sql_yield.yield_dt_with_nl("332987916", q, DataType.MARKDOWN.value), mimetype='text/event-stream')
    # return Response(generate_data(), mimetype='text/event-stream')

def generate_data():
    messages = ["大模型思考中...", "用户问题优化中...","优化后的问题是：***",
                "用户问题转换为SQL中...","SQL语句为：***","数据查询中...",
                "查询到的数据:****","正在绘图...","绘图结果为：\ndata_chart", "本次查询已完成"]
    for msg in messages:
        time.sleep(1)  # 模拟处理延迟
        yield f"data: {msg}\n\n"


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    app.run(host='0.0.0.0', port=19000)
