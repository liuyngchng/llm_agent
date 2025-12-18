#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
用户权限认证 HTTP 服务
"""
import json
import os
import time
import logging.config
from flask import Blueprint
from flask import (request,)

from common.const import UPLOAD_FOLDER
from common.sys_init import init_yml_cfg

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.dirname(current_dir)
template_folder = os.path.join(common_dir, 'common', 'templates')
uploader_bp = Blueprint('uploader', __name__, template_folder=template_folder)
my_cfg = init_yml_cfg()



@uploader_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    上传文件，支持单个或多个文件上传
    """
    logger.info(f"upload_file, {request}")

    # 检查是否有文件
    if 'file' not in request.files and 'files' not in request.files:
        return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400

    uid = int(request.form.get('uid'))
    logger.info(f"{uid}, upload_file")
    uploaded_files = []

    # 处理单个文件上传
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        file_info = save_uploaded_file(file, uid)
        uploaded_files.append(file_info)

    # 处理多个文件上传
    if 'files' in request.files:
        files = request.files.getlist('files')
        for file in files:
            if file.filename != '':
                file_info = save_uploaded_file(file, uid)
                uploaded_files.append(file_info)

    if not uploaded_files:
        return json.dumps({"error": "没有有效的上传文件"}, ensure_ascii=False), 400

    logger.info(f"{uid}, files_uploaded, {uploaded_files}")

    # 返回格式：单个文件返回对象，多个文件返回数组
    if len(uploaded_files) == 1:
        return json.dumps(uploaded_files[0], ensure_ascii=False), 200
    else:
        return json.dumps({"files": uploaded_files}, ensure_ascii=False), 200


def save_uploaded_file(file, uid):
    """保存上传的文件"""
    # 生成任务ID，使用毫秒数
    file_id = int(time.time() * 1000)
    file_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_FOLDER, file_name)
    file.save(save_path)

    logger.info(f"{uid}, upload_file_saved_as {file_name}, {file_id}")

    return {
        "file_id": file_id,
        "file_name": file_name,
        "original_name": file.filename
    }

def get_client_ip():
    """获取客户端真实 IP"""
    # 如果有X-Forwarded-For，取第一个IP（因为可能是代理链）
    x_forwarded_for = request.headers.get('X-Forwarded-For', '')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip
