#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import json
import sys
import os
import jwt
import logging.config

from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, abort, request, jsonify

from apps.online_office.office_util import generate_jwt_token, JWT_SECRET, get_content_type, generate_onlyoffice_config, \
    get_docker_host, get_file_type
from common.const import UPLOAD_FOLDER

import uuid
import shutil
from datetime import datetime

# 在已有配置后添加文档相关的配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCUMENT_FOLDER = os.path.join(BASE_DIR, 'documents')
DOCUMENT_UPLOAD_FOLDER = os.path.join(DOCUMENT_FOLDER, 'uploads')
DOCUMENT_PREVIEW_FOLDER = os.path.join(DOCUMENT_FOLDER, 'preview')
DOCUMENT_TEMP_FOLDER = os.path.join(DOCUMENT_FOLDER, 'temp')

# 创建必要的文件夹
for folder in [DOCUMENT_FOLDER, DOCUMENT_UPLOAD_FOLDER, DOCUMENT_PREVIEW_FOLDER, DOCUMENT_TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# 扩展允许的文件类型
ALLOWED_DOC_EXTENSIONS = {'docx', 'doc', 'txt', 'pdf', 'xlsx', 'pptx'}
DOC_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 文档数据结构
documents_db = {}  # 简单的内存存储，生产环境请用数据库


ONLY_OFFICE_API = "http://localhost"

# 创建 Flask 应用
app = Flask(__name__, static_folder=None)

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8", disable_existing_loggers=False)
    print(f"使用日志配置文件: {log_config_path}")
else:
    print("日志配置文件不存在，使用默认配置")
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format=LOG_FORMATTER,force=True,stream=sys.stdout)

logger = logging.getLogger(__name__)
logger.info("应用程序启动")

# 加载环境变量
load_dotenv()

# 确保上传文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"上传文件夹路径: {UPLOAD_FOLDER}")

@app.route('/static/<path:file_name>')
def get_static_file(file_name):
    """提供静态文件"""
    static_dirs = [
        os.path.join(os.path.dirname(__file__), 'static'),
        os.path.join(os.path.dirname(__file__), '../../common/static'),
    ]

    for static_dir in static_dirs:
        file_path = os.path.join(static_dir, file_name)
        if os.path.exists(file_path):
            logger.debug(f"提供静态文件: {file_name} 从 {static_dir}")
            return send_from_directory(static_dir, file_name)

    logger.error(f"静态文件未找到: {file_name}")
    abort(404)


@app.route('/webfonts/<path:file_name>')
def get_webfonts_file(file_name):
    """提供字体文件"""
    font_file_name = f"webfonts/{file_name}"
    return get_static_file(font_file_name)



@app.route('/')
def index():
    """渲染主页面"""
    logger.info("访问首页")
    return render_template(
        'index.html',
        config={
            'only_office_api': ONLY_OFFICE_API
        }
    )


@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """上传文档并准备预览"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        # 检查文件扩展名
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if file_ext not in ALLOWED_DOC_EXTENSIONS:
            return jsonify({
                'success': False,
                'error': f'不支持的文件类型。支持: {", ".join(ALLOWED_DOC_EXTENSIONS)}'
            }), 400

        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > DOC_MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': f'文件太大。最大支持 {DOC_MAX_FILE_SIZE // 1024 // 1024}MB'
            }), 400

        # 生成唯一ID和文件名
        doc_id = str(uuid.uuid4())
        safe_filename = f"{doc_id}.{file_ext}"
        upload_path = os.path.join(DOCUMENT_UPLOAD_FOLDER, safe_filename)

        # 保存文件
        file.save(upload_path)
        logger.info(f"文档上传成功: {safe_filename}, 大小: {file_size}字节")

        # 获取文档信息
        original_filename = file.filename
        file_type = get_file_type(file_ext)

        # 获取Docker可访问的主机地址
        docker_host = get_docker_host()
        logger.info(f"使用Docker主机地址: {docker_host}")
        file_url = f"http://{docker_host}:19000/api/documents/download/{doc_id}"
        logger.info(f"文档URL（Docker）: {file_url}")

        # 存储文档信息
        timestamp = int(datetime.now().timestamp())
        document_info = {
            'id': doc_id,
            'original_filename': original_filename,
            'filename': safe_filename,
            'file_type': file_type,
            'file_ext': file_ext,
            'size': file_size,
            'upload_time': datetime.now().isoformat(),
            'url': file_url,
            'path': upload_path,
            'key': f"{doc_id}_{timestamp}"
        }

        documents_db[doc_id] = document_info
        onlyoffice_config = generate_onlyoffice_config(document_info)
        logger.info(f"生成的OnlyOffice配置: {json.dumps(onlyoffice_config, indent=2)}")

        return jsonify({
            'success': True,
            'document': {
                'id': doc_id,
                'original_filename': original_filename,
                'file_type': file_type,
                'size': file_size,
                'url': file_url,
                'key': document_info['key'],
                'file_ext': file_ext
            },
            'onlyoffice_config': onlyoffice_config  # 返回完整配置
        })

    except Exception as e:
        logger.error(f"文档上传失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/download/<doc_id>')
def download_document(doc_id):
    """提供文档下载（OnlyOffice会访问这个URL获取文档）"""
    try:
        if doc_id not in documents_db:
            abort(404, "文档不存在")

        doc_info = documents_db[doc_id]
        file_path = doc_info['path']

        if not os.path.exists(file_path):
            abort(404, "文件不存在")

        # 设置正确的Content-Type
        content_type = get_content_type(doc_info['file_ext'])

        return send_from_directory(
            os.path.dirname(file_path),
            os.path.basename(file_path),
            as_attachment=False,
            mimetype=content_type
        )

    except Exception as e:
        logger.error(f"下载文档失败: {str(e)}")
        abort(500)


@app.route('/api/documents/list')
def list_documents():
    """获取文档列表"""
    docs = list(documents_db.values())
    # 只返回必要信息，不包含路径等敏感信息
    for doc in docs:
        doc.pop('path', None)
    return jsonify({'documents': docs})


@app.route('/api/documents/<doc_id>')
def get_document_info(doc_id):
    """获取单个文档信息"""
    if doc_id not in documents_db:
        abort(404, "文档不存在")

    doc_info = documents_db[doc_id].copy()
    doc_info.pop('path', None)  # 不暴露路径
    return jsonify({'document': doc_info})


@app.route('/api/debug/jwt', methods=['GET'])
def debug_jwt():
    """调试JWT生成"""
    test_payload = {
        "document": {
            "fileType": "docx",
            "key": "test_key",
            "title": "test.docx",
            "url": "http://localhost:19000/api/documents/download/test"
        }
    }

    token = generate_jwt_token(test_payload)

    # 验证令牌
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return jsonify({
            'success': True,
            'token': token,
            'decoded': decoded,
            'secret_used': JWT_SECRET
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'token': token
        })


@app.route('/callback', methods=['POST'])
def onlyoffice_callback():
    """处理OnlyOffice的回调请求"""
    try:
        data = request.json
        logger.info(f"收到OnlyOffice回调: {data}")

        # 获取回调类型
        status = data.get('status', 0)

        if status == 0:  # 用户正在查看文档
            logger.info("用户正在查看文档")
            return jsonify({"error": 0})

        elif status == 1:  # 文档已编辑
            logger.info("文档已被编辑")
            # 可以在这里处理编辑事件
            return jsonify({"error": 0})

        elif status == 2:  # 文档已保存（重要！）
            logger.info("文档已保存")

            # 获取文档URL
            if 'url' in data:
                download_url = data['url']
                logger.info(f"文档下载URL: {download_url}")

                # 这里可以下载文档到服务器
                # 或者记录保存事件

            return jsonify({"error": 0})

        elif status == 3:  # 保存文档时出错
            logger.error("保存文档时出错")
            return jsonify({"error": 0})

        elif status == 4:  # 文档关闭且未保存
            logger.info("文档关闭且未保存")
            return jsonify({"error": 0})

        elif status == 6:  # 用户正在编辑文档
            users = data.get('users', [])
            logger.info(f"用户正在编辑文档: {users}")
            return jsonify({"error": 0})

        elif status == 7:  # 强制保存请求
            logger.info("收到强制保存请求")
            return jsonify({"error": 0})

        else:
            logger.warning(f"未知的回调状态: {status}")
            return jsonify({"error": 0})

    except Exception as e:
        logger.error(f"处理回调失败: {str(e)}")
        return jsonify({"error": 1, "message": str(e)})


@app.route('/api/documents/save/<doc_id>', methods=['POST'])
def save_document(doc_id):
    """保存文档（从OnlyOffice下载）"""
    try:
        if doc_id not in documents_db:
            return jsonify({'success': False, 'error': '文档不存在'}), 404

        # 从请求中获取文档数据
        file_data = request.data

        if not file_data:
            return jsonify({'success': False, 'error': '没有文档数据'}), 400

        # 保存文档到服务器
        doc_info = documents_db[doc_id]
        file_path = doc_info['path']

        # 备份原文件（可选）
        backup_path = file_path + '.backup'
        if os.path.exists(file_path):
            shutil.copy2(file_path, backup_path)

        # 保存新文件
        with open(file_path, 'wb') as f:
            f.write(file_data)

        logger.info(f"文档已保存: {doc_info['original_filename']}")

        return jsonify({
            'success': True,
            'message': '文档保存成功'
        })

    except Exception as e:
        logger.error(f"保存文档失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':

    JWT_AVAILABLE = True
    logger.info("启动Flask应用...")
    app.run(
        debug=False,
        host='0.0.0.0',
        port=19000,
        threaded=True
    )