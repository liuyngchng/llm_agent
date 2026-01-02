#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os
import sys

import jwt
import logging.config

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8", disable_existing_loggers=False)
    print(f"使用日志配置文件: {log_config_path}")
else:
    print("日志配置文件不存在，使用默认配置")
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format=LOG_FORMATTER,force=True,stream=sys.stdout)

logger = logging.getLogger(__name__)

JWT_SECRET = "your_jwt_secret_here"


# 修改 office_util.py 中的 generate_jwt_token 函数

def generate_jwt_token(payload):
    """生成 OnlyOffice 兼容的 JWT 令牌"""
    import time

    # OnlyOffice 7.1+ 期望的格式：payload直接包含文档配置
    # 注意：这里我们直接将配置作为payload，不再嵌套在"payload"字段中
    payload_with_expiry = payload.copy()  # 复制原始payload

    # 添加JWT标准声明（可选，但建议添加）
    payload_with_expiry["iat"] = int(time.time())  # 签发时间
    payload_with_expiry["exp"] = int(time.time()) + 3600  # 1小时后过期

    # 生成 JWT
    token = jwt.encode(
        payload_with_expiry,
        JWT_SECRET,
        algorithm='HS256'
    )

    # PyJWT 返回的是 bytes，需要转为字符串
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    logger.debug(f"生成的 JWT Token: {token}")
    return token


# 同时修改 generate_onlyoffice_config 函数，确保传入正确的payload结构
def generate_onlyoffice_config(document_info, action="edit"):
    """生成 OnlyOffice 配置"""
    doc_key = document_info['key']
    doc_url = document_info['url']
    filename = document_info['original_filename']
    file_ext = document_info.get('file_ext', 'docx')

    # 确定文件类型
    file_type = file_ext if file_ext in ['docx', 'doc'] else 'docx'
    doc_type = "word"

    if file_ext in ['xlsx', 'xls']:
        doc_type = "cell"
    elif file_ext in ['pptx', 'ppt']:
        doc_type = "slide"

    # 获取 Docker 主机地址
    docker_host = get_docker_host()

    # 构建完整的配置对象（这将是JWT的payload）
    config = {
        "document": {
            "fileType": file_type,
            "key": doc_key,
            "title": filename,
            "url": doc_url,
            "permissions": {
                "edit": True,
                "comment": True,
                "download": True,
                "print": True,
                "review": True,
                "fillForms": True,
                "modifyFilter": True,
                "modifyContentControl": True
            }
        },
        "documentType": doc_type,
        "editorConfig": {
            "mode": "edit",
            "lang": "zh-CN",
            "callbackUrl": f"http://{docker_host}:19000/callback",
            "customization": {
                "autosave": False,
                "comments": True,
                "compactHeader": True,
                "feedback": False,
                "help": False,
                "hideRightMenu": False,
                "toolbarNoTabs": False,
                "zoom": 100
            },
            "user": {
                "id": "anonymous",
                "name": "匿名用户"
            }
        }
    }

    # 生成 JWT 令牌 - 现在直接传入config作为payload
    token = generate_jwt_token(config)

    # 返回完整的配置（包含token）
    final_config = config.copy()
    final_config["token"] = token

    logger.info(f"生成的 OnlyOffice 配置已包含 JWT Token")
    return final_config

def get_file_type(ext):
    """根据扩展名获取文件类型"""
    doc_types = {
        'docx': 'word', 'doc': 'word',
        'txt': 'text',
        'pdf': 'pdf',
        'xlsx': 'cell', 'xls': 'cell',
        'pptx': 'slide', 'ppt': 'slide'
    }
    return doc_types.get(ext, 'word')


def get_content_type(ext):
    """获取正确的Content-Type"""
    content_types = {
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'txt': 'text/plain',
        'pdf': 'application/pdf',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }
    return content_types.get(ext, 'application/octet-stream')


def get_docker_host():
    """获取Docker容器可以访问的宿主机地址"""
    # 在宿主机运行时，返回 host.docker.internal
    # 这样OnlyOffice容器就能访问到宿主机服务

    # 也可以尝试获取宿主机IP
    import socket
    try:
        # 获取局域网IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        host_ip = s.getsockname()[0]
        s.close()
        logger.info(f"检测到局域网IP: {host_ip}")

        # 返回Docker能访问的地址
        # 在容器内：host.docker.internal
        # 在宿主机：自己的IP
        return "127.0.0.1"

    except Exception as e:
        print(f"获取IP失败，使用默认值: {e}")
        return "127.0.0.1"