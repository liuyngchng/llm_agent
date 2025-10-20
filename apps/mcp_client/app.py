#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
MCP 客户端  Web 界面
"""

import logging.config
import json
import os

from flask import (Flask, render_template, request, jsonify, Response,
                   stream_with_context, send_from_directory, abort)
from apps.mcp_client.client_service import auto_call_mcp, auto_call_mcp_yield
from common.sys_init import init_yml_cfg

# 配置日志
logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__, static_folder=None)
app.config['JSON_AS_ASCII'] = False
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

# 初始化配置
cfg = init_yml_cfg()

@app.route('/static/<path:file_name>')
def get_static_file(file_name):
    static_dirs = [
        os.path.join(os.path.dirname(__file__), '../../common/static'),
        os.path.join(os.path.dirname(__file__), 'static'),
    ]

    for static_dir in static_dirs:
        if os.path.exists(os.path.join(static_dir, file_name)):
            logger.debug(f"get_static_file, {static_dir}, {file_name}")
            return send_from_directory(static_dir, file_name)
    logger.error(f"no_file_found_error, {file_name}")
    abort(404)

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/query', methods=['POST'])
def process_query():
    """处理用户查询的 API 端点"""
    try:
        # 获取用户输入
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': '缺少问题参数'}), 400

        question = data['question']
        logger.info(f"收到用户查询: {question}")

        # 检查是否请求流式响应
        stream = data.get('stream', False)

        if stream:
            # 流式响应
            def generate():
                try:
                    for chunk in auto_call_mcp_yield(question, cfg):
                        yield f"data: {chunk}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    error_msg = json.dumps({
                        "type": "error",
                        "content": f"处理过程中发生错误: {str(e)}"
                    }, ensure_ascii=False)
                    yield f"data: {error_msg}\n\n"
                    yield "data: [DONE]\n\n"

            return Response(stream_with_context(generate()),
                            mimetype='text/event-stream',
                            headers={
                                'Cache-Control': 'no-cache',
                                'Connection': 'keep-alive',
                                'X-Accel-Buffering': 'no'  # 禁用Nginx缓冲
                            })
        else:
            # 普通响应
            result = auto_call_mcp(question, cfg)
            return jsonify({
                'success': True,
                'question': question,
                'answer': result
            })

    except Exception as e:
        logger.exception("处理查询时发生错误")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health')
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    # 启动 Flask 应用
    app.run(debug=True, host='0.0.0.0', port=19002)