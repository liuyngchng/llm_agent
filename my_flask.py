#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route('/')
def hello_world():
    """
     A hello world test
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    return '{"status":200, "msg":"Hello World!"}'

@app.route('/greet/<name>')
def greet(name):
    """
    get param from URI path
    :param name:
    :return:
    """
    return f'Hello {name}'


@app.route('/msg')
def get_msg():
    """
    return a  JSON msg
    :return:
    """
    return '{"status":200, "msg":"a new message"}'

@app.route('/submit', methods=['POST'])
def submit():
    """
    form submit, get data from form
    :return:
    """
    username = request.form.get('username')
    return f'Hello, {username}!'


@app.route('/data', methods=['POST'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/data' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'
    :return:
    """
    data = request.get_json()
    print(data)
    return jsonify({"message": "Data received successfully!", "data": data}), 200


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    app.run(host='0.0.0.0', port=19000)
