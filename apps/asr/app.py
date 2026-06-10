#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import os
import logging.config
import uuid
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

import threading


from apps.asr.asr_util import asr_tasks, process_audio_async
from common.sys_init import init_yml_cfg
from common.auth_util import auth_info, get_client_ip, redirect_to_portal_login
from common import cm_utils, statistic_util, my_enums
from common.i18n._hooks import register_i18n
from common.i18n import get_msg
from common.my_enums import AppType

my_cfg = init_yml_cfg()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = my_enums.AppType.ASR.name.lower()

register_i18n(app, scope="asr")


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


# ASR 服务配置
ASR_HOST = my_cfg['funasr']['host']
ASR_PORT = my_cfg['funasr']['port']

# 支持的文件格式
SUPPORTED_FORMATS = {'.m4a', '.mp3', '.amr', '.wav', '.flac', '.ogg', '.aac'}


@app.route('/')
def app_home():
    app_source = AppType.ASR.name.lower()
    sys_name = my_enums.AppType.get_app_type(app_source)
    t = request.args.get("t")
    if not t:
        logger.info("no_token_redirect_auth_login_index")
        return redirect_to_portal_login(app_source)
    session_info = cm_utils.decode_token(t, my_cfg['sys']['cypher_key'])
    if not session_info:
        logger.info("no_session_info_redirect_auth_login_index")
        return redirect_to_portal_login(app_source)
    uid = session_info['uid']
    dt_idx = f"{app_source}_index.html"
    logger.info(f"return_page {dt_idx}")
    statistic_util.add_access_count_by_uid(uid, 1, app_source)

    if session_info["role"] == 2:
        hack_admin = "1"
    else:
        hack_admin = "0"

    # greeting = get_const("greeting", app_source)
    # arg1 = get_const("arg1", app_source)
    # arg2 = get_const("arg2", app_source)
    # arg3 = get_const("arg3", app_source)

    ctx = {
        "uid": uid,
        "t": t,
        "sys_name": sys_name,
        "greeting": "",
        "app_source": app_source,
        "hack_admin": hack_admin,
        "arg1": "",
        "arg2": "",
        "arg3": "",
    }

    session_key = f"{uid}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)


@app.route('/api/upload', methods=['POST'])
def upload_audio():
    """上传音频文件"""
    if 'file' not in request.files:
        info = {'error': '没有文件'}
        logger.info(info)
        return jsonify(info), 400

    file = request.files['file']
    if file.filename == '':
        info = {'error': '文件名为空'}
        logger.info(info)
        return jsonify(info), 400

    # 检查文件格式
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        info = {'error': f'不支持的文件格式，支持: {", ".join(SUPPORTED_FORMATS)}'}
        logger.info(info)
        return jsonify(info), 400

    # 保存原始文件
    original_filename = file.filename
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    input_path = UPLOAD_DIR / safe_filename
    file_path = str(input_path)
    file.save(file_path)
    logger.info(f"upload_file_saved, {file_path}")

    # 创建任务
    task_id = asr_tasks.create_task(original_filename, str(input_path), None)
    logger.info(f"create_task {task_id}")
    # 异步处理
    thread = threading.Thread(
        target=process_audio_async,
        args=(task_id, input_path, ASR_HOST, ASR_PORT)
    )
    thread.daemon = True
    thread.start()
    info = {
        'task_id': task_id,
        'status': 'converting',
        'message': '文件已上传，开始处理...'
    }
    logger.info(info)
    return jsonify(info)


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
        'progress': task.get('progress'),
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
    # ====== Debug链接：生成带 token 的直接访问链接 ======
    debug_token = cm_utils.create_token(1, 0, 86400, my_cfg['sys']['cypher_key'])
    print(f"\n{'='*70}")
    print(f"  Debug访问链接（直接点击进入）:")
    print(f"  >>> http://127.0.0.1:19010?t={debug_token}")
    print(f"  uid=1, role=0, token有效期=24h")
    print(f"{'='*70}\n")

    port = 19010
    logger.info(f"asr_service_listen_on_port {port}")
    app.run(debug=True, host='0.0.0.0', port=port)