#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install gunicorn flask
"""
import json
import logging.config

from flask import Flask, Response

app = Flask(__name__)
logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

@app.route('/', methods=['GET'])
def index():
    """
    just for test purpose only
    """
    data = {"status":200, "message": "service OK"}
    print(f"return {data}")
    logger.info(f"return {data}")
    response = Response(
        json.dumps(data, ensure_ascii=False),
        content_type="application/json; charset=utf-8",
        status=200
    )
    return response


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    port = 19000
    print(f"listening_port {port}")
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)
