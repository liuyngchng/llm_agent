#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
矢量知识库构建
"""
import logging.config
import os
import threading
import time

from flask import (request, jsonify, redirect, url_for, Blueprint)
from werkzeug.utils import secure_filename

from sys_init import init_yml_cfg
from vdb_util import vector_file_in_progress

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

file_vdb = Blueprint('file_vdb', __name__)

UPLOAD_FOLDER = 'upload_doc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 确保上传目录存在

my_cfg = init_yml_cfg()

task_progress = {}  # 存储文本进度信息
thread_lock = threading.Lock()


@file_vdb.route('/upload', methods=['POST'])
def upload_file():
    logger.info(f"start_upload_file, {request}")
    if 'file' not in request.files:
        return jsonify({"error": "未找到文件"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400

    try:
        # 安全检查和处理文件名
        original_filename = secure_filename(file.filename)
        if not original_filename:  # 安全检查后文件名仍为空
            logger.error("文件名安全检查失败")
            return jsonify({"error": "无效文件名"}), 400
        # 检查文件类型
        allowed_extensions = {'.docx', '.pdf', '.txt'}
        file_ext = os.path.splitext(original_filename)[1].lower()  # 提取扩展名并转为小写
        if file_ext not in allowed_extensions:
            return jsonify({"error": "不支持的文件类型，仅允许docx/pdf/txt"}), 400

        # 定义允许的文件类型及其魔数签名
        ALLOWED_TYPES = {
            '.pdf': [b'%PDF'],          # PDF签名
            '.docx': [b'PK\x03\x04'],   # ZIP格式签名(DOCX本质是ZIP)
            '.txt': []                  # 文本文件无固定签名
        }
        # 读取文件头进行魔数验证
        file.seek(0)
        header = file.read(4)  # 读取前4字节

        # 特殊处理DOCX(PK\x03\x04)和PDF(%PDF)
        if file_ext in ['.docx', '.pdf']:
            valid_signatures = ALLOWED_TYPES[file_ext]
            if not any(header.startswith(sig) for sig in valid_signatures):
                return jsonify({"error": "文件内容与类型不符"}), 400

        file.seek(0)  # 重置文件指针
        # 生成唯一任务ID和文件名
        task_id = str(int(time.time() * 1000))  # 使用毫秒提高唯一性
        filename = f"{task_id}_{original_filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)

        # 确保上传目录存在
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # 保存文件
        file.save(save_path)

        # 初始化任务进度
        with thread_lock:
            task_progress[task_id] = {
                'progress': 0,
                'filename': filename,
                'timestamp': time.time()
            }
        logger.info(f"文件上传成功: {filename}, 大小: {os.path.getsize(save_path)}字节")
        return jsonify({
            "success": True,
            "task_id": task_id,
            "file_name": filename,
            "message": "文件上传成功"
        }), 200

    except Exception as e:
        logger.error(f"文件上传处理失败: {str(e)}", exc_info=True)
        return jsonify({
            "error": "文件处理失败",
            "details": str(e)
        }), 500


@file_vdb.route("/index/doc", methods=['POST'])
def index_doc():
    logger.info(f"start_index_doc, {request}")
    data = request.json
    task_id = data.get("task_id")
    file_name = data.get("file_name")
    uid = data.get("uid")

    if not task_id or not file_name:
        return jsonify({"error": "缺少参数"}), 400

    threading.Thread(
        target=process_doc,
        args=(task_id, file_name, uid)
    ).start()

    return jsonify({"status": "started", "task_id": task_id}), 200

@file_vdb.route('/get/process/info', methods=['POST'])
def get_doc_process_info():
    task_id = request.json.get("task_id")
    if not task_id:
        return jsonify({"error": "缺少任务ID"}), 400
    with thread_lock:
        progress_info = task_progress.get(task_id, {"text": "未知状态"})
    return jsonify({
        "task_id": task_id,
        "progress": progress_info["text"]
    }), 200

def clean_tasks():
    while True:
        with thread_lock:
            now = time.time()
            expired = [k for k, v in task_progress.items()
                      if now - v['timestamp'] > 3600]  # 1小时过期
            for k in expired:
                del task_progress[k]
        time.sleep(300)


def process_doc(task_id: str, file_name: str, uid: str):
    try:
        task_progress[task_id] = {"text": "开始解析文档结构...", "timestamp": time.time()}
        my_target_doc = os.path.join(UPLOAD_FOLDER, file_name)
        output_vdb_dir = os.path.join(UPLOAD_FOLDER, f"faiss_oa_idx_{uid}")
        vector_file_in_progress(task_id, thread_lock, task_progress, my_target_doc,
            output_vdb_dir, my_cfg['api'],300, 80)
    except Exception as e:
        with thread_lock:
            task_progress[task_id] = {
                "text": f"任务处理失败: {str(e)}",
                "timestamp": time.time()
            }
        logger.exception("文档生成异常", e)

if __name__ == '__main__':
    logger.info("just for test")