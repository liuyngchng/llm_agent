#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
作为数据库连接的代理，用于获取配置数据库相关的信息
"""
import os
import logging.config
from functools import wraps

from flask import Flask, request, jsonify

import cfg_util
from sys_init import init_yml_cfg
from utils import get_console_arg1

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

def token_required(f):
    """ 认证装饰器 """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        # 这里可以添加token验证逻辑
        # 简单示例：假设token格式为 "Bearer <token>"
        if not token.startswith('Bearer '):
            return jsonify({'error': 'Invalid token format'}), 401

        # 提取token并验证
        token = token[7:]  # 去掉"Bearer "前缀

        # 这里可以添加更复杂的token验证逻辑
        # 例如检查token是否在有效期内等

        return f(*args, **kwargs)

    return decorated


@app.route('/dt/auth', methods=['POST'])
def auth_user():
    """ 用户认证 """
    try:
        data = request.get_json()
        user = data.get('user')
        t = data.get('t')

        if not user or not t:
            return jsonify({'error': 'Missing user or token'}), 400

        result = cfg_util.auth_user(user, t, my_cfg)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Auth API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500



@app.route('/dt/user/<uid>', methods=['GET'])
@token_required
def get_user_info(uid: str):
    """ 获取用户信息 """
    try:
        user_info = cfg_util.get_user_info_by_uid(uid)
        return jsonify(user_info)
    except Exception as e:
        logger.error(f"Get user info API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# 根据用户名获取UID API
@app.route('/dt/user/name/<user_name>', methods=['GET'])
@token_required
def get_uid_by_user(user_name: str):
    try:
        uid = cfg_util.get_uid_by_user(user_name)
        return jsonify({'uid': uid})
    except Exception as e:
        logger.error(f"Get UID by user API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/dt/ds_config/<uid>', methods=['GET'])
@token_required
def get_ds_cfg(uid):
    try:
        config = cfg_util.get_ds_cfg_by_uid(uid, my_cfg)
        return jsonify(config)
    except Exception as e:
        logger.error(f"Get DS config API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/dt/const/<app_name>/<key>', methods=['GET'])
@token_required
def get_const_by_app_and_key(app_name: str, key: str):
    """ 获取常量 """
    try:
        value = cfg_util.get_const(key, app_name)
        return jsonify({'value': value})
    except Exception as e:
        logger.error(f"Get const API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/dt/consts/<app_name>', methods=['GET'])
@token_required
def get_const_dict_by_app(app_name):
    """ 获取多个常量 """
    try:
        consts = cfg_util.get_consts(app_name)
        return jsonify(consts)
    except Exception as e:
        logger.error(f"Get consts API error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# 健康检查API
@app.route('/dt/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    logger.info(f"my_cfg {my_cfg.get('db')},\n{my_cfg.get('api')}")
    # test_query_data()
    app.config['ENV'] = 'dev'
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)