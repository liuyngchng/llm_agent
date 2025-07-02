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
import cfg_util as cfg_utl

from flask import (Flask, request, jsonify, render_template,
                   send_from_directory, abort, redirect, url_for)

from docx_cmt_util import get_para_comment_dict, modify_para_with_comment_prompt_in_process
from docx_util import extract_catalogue, fill_doc_in_progress
from http_auth import auth_bp

from sys_init import init_yml_cfg



logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.config['JSON_AS_ASCII'] = False
UPLOAD_FOLDER = 'upload_doc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 确保上传目录存在

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
task_progress = {}  # 存储文本进度信息
progress_lock = threading.Lock()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source='vdb'))

@app.route('/upload', methods=['POST'])  # 修正路由路径
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "未找到文件"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400

    # 生成任务ID和文件名
    task_id = str(int(time.time()))
    filename = f"{task_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # 初始化进度
    with progress_lock:
        task_progress[task_id] = 0
    logger.info(f"upload_file_saved_as {filename}")
    return jsonify({
        "task_id": task_id,
        "file_name": filename
    }), 200


@app.route("/write/doc", methods=['POST'])
def write_doc():
    data = request.json
    task_id = data.get("task_id")
    file_name = data.get("file_name")

    if not task_id or not file_name:
        return jsonify({"error": "缺少参数"}), 400

    threading.Thread(
        target=process_document,
        args=(task_id, file_name)
    ).start()

    return jsonify({"status": "started", "task_id": task_id}), 200


@app.route('/download/<filename>', methods=['GET'])
def download_output(filename):
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        logger.error(f"文件 {filename} 不存在")
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.route('/get/process/info', methods=['POST'])
def get_doc_process_info():
    task_id = request.json.get("task_id")
    if not task_id:
        return jsonify({"error": "缺少任务ID"}), 400
    with progress_lock:
        progress_info = task_progress.get(task_id, {"text": "未知状态"})
    return jsonify({
        "task_id": task_id,
        "progress": progress_info["text"]
    }), 200

def clean_tasks():
    while True:
        with progress_lock:
            now = time.time()
            expired = [k for k, v in task_progress.items()
                      if now - v['timestamp'] > 3600]  # 1小时过期
            for k in expired:
                del task_progress[k]
        time.sleep(300)




def process_document(task_id, file_name):
    try:
        task_progress[task_id] = {"text": "开始解析文档结构...", "timestamp": time.time()}
        my_target_doc = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(my_target_doc)
        output_file = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.docx")
        with progress_lock:
            task_progress[task_id] = {
                "text": "开始处理文档...",
                "timestamp": time.time()
            }
        para_comment_dict = get_para_comment_dict(my_target_doc)
        if para_comment_dict:
            logger.info("process_word_comment_doc")
            modify_para_with_comment_prompt_in_process(
                task_id,
                progress_lock,
                task_progress,
                my_target_doc,
                "我正在写一个可行性研究报告",
                para_comment_dict,
                my_cfg,
                output_file
            )
        else:
            logger.info("fill_doc_with_catalogue")
            fill_doc_in_progress(
                task_id,
                progress_lock,
                task_progress,
                "我正在写一个可行性研究报告",
                my_target_doc,
                catalogue,
                my_cfg,
                output_file,
            )
    except Exception as e:
        with progress_lock:
            task_progress[task_id] = {
                "text": f"任务处理失败: {str(e)}",
                "timestamp": time.time()
            }
        logger.exception("文档生成异常", e)

if __name__ == '__main__':
    threading.Thread(target=clean_tasks, daemon=True).start()
    app.run(host='0.0.0.0', port=19000)