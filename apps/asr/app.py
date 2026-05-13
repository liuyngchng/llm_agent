#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import os
import logging.config
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for

import threading


from apps.asr.asr_util import asr_tasks, process_audio_async
from common.sys_init import init_yml_cfg

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

# 配置目录
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / 'uploads'
CONVERTED_DIR = BASE_DIR / 'converted'
RESULTS_DIR = BASE_DIR / 'results'

for dir_path in [UPLOAD_DIR, CONVERTED_DIR, RESULTS_DIR]:
    dir_path.mkdir(exist_ok=True)

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


my_cfg = init_yml_cfg()

# ASR 服务配置
ASR_HOST = "127.0.0.1"
ASR_PORT = 10095

# 支持的文件格式
SUPPORTED_FORMATS = {'.m4a', '.mp3', '.amr', '.wav', '.flac', '.ogg', '.aac'}




@app.route('/')
def index():
    """主页"""
    return render_template('index.html', sys_name="音频转文字助手")


@app.route('/api/upload', methods=['POST'])
def upload_audio():
    """上传音频文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    # 检查文件格式
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        return jsonify({'error': f'不支持的文件格式，支持: {", ".join(SUPPORTED_FORMATS)}'}), 400

    # 保存原始文件
    original_filename = file.filename
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    input_path = UPLOAD_DIR / safe_filename
    file.save(str(input_path))

    # 创建任务
    task_id = asr_tasks.create_task(original_filename, str(input_path), None)

    # 异步处理
    thread = threading.Thread(target=process_audio_async, args=(task_id, input_path))
    thread.daemon = True
    thread.start()

    return jsonify({
        'task_id': task_id,
        'status': 'converting',
        'message': '文件已上传，开始处理...'
    })


@app.route('/api/status/<task_id>')
def get_task_status(task_id):
    """获取任务状态"""
    task = asr_tasks.get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    return jsonify({
        'task_id': task['id'],
        'status': task['status'],
        'result_text': task.get('result_text'),
        'error': task.get('error'),
        'original_filename': task['original_filename'],
        'timestamp': task['timestamp'].isoformat()
    })


@app.route('/api/download/<task_id>')
def download_result(task_id):
    """下载识别结果"""
    task = asr_tasks.get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    if task['status'] != 'completed' or not task.get('result_text'):
        return jsonify({'error': '任务未完成或结果不存在'}), 400

    # 生成下载文件
    result_file = RESULTS_DIR / f"{task_id}.txt"
    original_name = Path(task['original_filename']).stem
    download_name = f"{original_name}_转写结果.txt"

    return send_file(
        result_file,
        as_attachment=True,
        download_name=download_name,
        mimetype='text/plain'
    )


@app.route('/api/tasks')
def get_all_tasks():
    """获取所有任务"""
    tasks = []
    for task_id, task in asr_tasks.tasks.items():
        tasks.append({
            'task_id': task['id'],
            'original_filename': task['original_filename'],
            'status': task['status'],
            'timestamp': task['timestamp'].isoformat(),
            'has_result': task['status'] == 'completed'
        })
    # 按时间倒序
    tasks.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify({'tasks': tasks[:20]})


@app.route('/api/clear_tasks', methods=['POST'])
def clear_completed_tasks():
    """清理已完成的任务"""
    to_delete = []
    for task_id, task in asr_tasks.tasks.items():
        if task['status'] in ['completed', 'failed']:
            to_delete.append(task_id)

    for task_id in to_delete:
        asr_tasks.delete_task(task_id)

    return jsonify({'message': f'已清理 {len(to_delete)} 个任务'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)