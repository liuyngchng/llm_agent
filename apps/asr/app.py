#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import os
import logging.config
import uuid
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, abort

import threading


from apps.asr.asr_util import asr_tasks, process_audio_async
from common.sys_init import init_yml_cfg
from common.auth_util import auth_info, get_client_ip, redirect_to_portal_login
from common import cm_utils, statistic_util, my_enums
from common.i18n._hooks import register_i18n
from common.i18n import get_msg
from common.my_enums import AppType

my_cfg = init_yml_cfg()

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = my_enums.AppType.ASR.name.lower()

register_i18n(app, scope="asr")


@app.route('/static/<path:file_name>')
def get_static_file(file_name):
    """提供静态文件，优先 app 自身 static，其次 common/static"""
    static_dirs = [
        os.path.join(os.path.dirname(__file__), 'static'),
        os.path.join(os.path.dirname(__file__), '../../common/static'),
    ]
    for static_dir in static_dirs:
        file_path = os.path.join(static_dir, file_name)
        if os.path.exists(file_path):
            return send_from_directory(static_dir, file_name)
    logger.error(f"静态文件未找到: {file_name}")
    abort(404)


@app.route('/webfonts/<path:file_name>')
def get_webfonts_file(file_name):
    """提供字体文件"""
    font_file_name = f"webfonts/{file_name}"
    return get_static_file(font_file_name)


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


# ============================================================
# 页面路由
# ============================================================

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


@app.route('/asr/task', methods=['GET'])
def asr_task_index():
    """我的任务页面"""
    logger.info(f"asr_task_index, {request.args}")
    t = request.args.get('t', '').strip()
    app_source = request.args.get('app_source', 'asr')
    if not t:
        logger.warning("no_token_in_asr_task")
        return redirect_to_portal_login(app_source)
    session_info = cm_utils.decode_token(t, my_cfg['sys']['cypher_key'])
    if not session_info:
        logger.warning("invalid_token_in_asr_task")
        return redirect_to_portal_login(app_source)
    uid = str(session_info['uid'])
    session_key = f"{uid}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    statistic_util.add_access_count_by_uid(int(uid), 1, app_source)
    warning_info = request.args.get('warning_info', "")
    sys_name = my_enums.AppType.get_app_type(app_source)
    ctx = {
        "uid": uid,
        "t": t,
        "sys_name": sys_name,
        "app_source": app_source,
        "warning_info": warning_info,
    }
    dt_idx = "asr_my_task.html"
    logger.info(f"{uid}, return_asr_task_page {dt_idx}")
    return render_template(dt_idx, **ctx)


# ============================================================
# API 路由
# ============================================================

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

    # 获取用户 ID（从表单或 URL 参数）
    uid = int(request.form.get('uid', request.args.get('uid', 0)))

    # 保存原始文件
    original_filename = file.filename
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    input_path = UPLOAD_DIR / safe_filename
    file_path = str(input_path)
    file.save(file_path)
    logger.info(f"upload_file_saved, {file_path}")

    # 创建任务（持久化到 SQLite）
    task_id = asr_tasks.create_task(original_filename, str(input_path), None, uid=uid)
    logger.info(f"create_task {task_id}, uid={uid}")
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
        'message': '文件已上传，后台开始处理...'
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
        'task_id': task['task_id'],
        'status': task['status'],
        'result_text': task.get('result_text'),
        'error': task.get('error'),
        'progress': task.get('progress'),
        'original_filename': task['original_filename'],
    })


@app.route('/asr/my/task', methods=['POST'])
def my_asr_task():
    """获取当前用户的 ASR 任务列表"""
    data = request.json or {}
    uid = int(data.get('uid', 0))
    logger.debug(f"{uid}, get_my_asr_tasks")
    task_list = asr_tasks.get_user_tasks(uid)
    logger.debug(f"{uid}, found {len(task_list)} tasks")
    return jsonify({'tasks': task_list}), 200


@app.route('/asr/download/<task_id>')
def download_result(task_id):
    """下载识别结果"""
    task = asr_tasks.get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    if task['status'] != 'completed' or not task.get('result_text'):
        return jsonify({'error': '任务未完成或结果不存在'}), 400

    result_file = RESULTS_DIR / f"{task_id}.txt"
    if not result_file.exists():
        return jsonify({'error': '结果文件不存在'}), 404

    original_name = Path(task['original_filename']).stem
    download_name = f"{original_name}_转写结果.txt"

    return send_file(
        result_file,
        as_attachment=True,
        download_name=download_name,
        mimetype='text/plain'
    )


@app.route('/asr/del/task', methods=['POST'])
def delete_asr_task():
    """删除指定任务"""
    data = request.json or {}
    task_id = data.get('task_id', '')
    if not task_id:
        return jsonify({'error': '缺少 task_id'}), 400
    logger.info(f"delete_asr_task {task_id}")
    asr_tasks.delete_task(task_id)
    return jsonify({'message': '已删除'}), 200


@app.route('/api/tasks')
def get_all_tasks():
    """获取所有任务（兼容旧接口，不分用户）"""
    uid = int(request.args.get('uid', 0))
    tasks = asr_tasks.get_user_tasks(uid)
    result = []
    for task in tasks:
        result.append({
            'task_id': task['task_id'],
            'original_filename': task['original_filename'],
            'status': task['status'],
            'timestamp': task['created_at'],
            'has_result': task['status'] == 'completed'
        })
    return jsonify({'tasks': result[:20]})


@app.route('/api/clear_tasks', methods=['POST'])
def clear_completed_tasks():
    """清理已完成的任务（兼容旧接口）"""
    uid = int(request.json.get('uid', 0) if request.json else 0)
    tasks = asr_tasks.get_user_tasks(uid)
    count = 0
    for task in tasks:
        if task['status'] in ['completed', 'failed']:
            asr_tasks.delete_task(task['task_id'])
            count += 1

    return jsonify({'message': f'已清理 {count} 个任务'})


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