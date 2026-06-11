#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import time
import os
import logging.config
import logging

from flask import Flask, request, jsonify, send_from_directory, abort, render_template
from jinja2 import ChoiceLoader, FileSystemLoader

from common import my_enums, cm_utils
from common.auth_util import auth_info, get_client_ip, redirect_to_portal_login
from common.const import SESSION_TIMEOUT
from common.i18n._hooks import register_i18n
from common.i18n import get_msg
from common.my_enums import AppType
from common.statistic_util import add_access_count_by_uid
from common.sys_init import init_yml_cfg

my_cfg = init_yml_cfg()

# 工作空间目录
WORKSPACE_DIR = my_cfg['sys'].get('workspace')
if not WORKSPACE_DIR:
    raise RuntimeError("cfg.yml 中未配置 sys.workspace，请设置一个绝对路径")

os.makedirs(WORKSPACE_DIR, exist_ok=True)
print(f"工作空间路径: {WORKSPACE_DIR}")

app = Flask(__name__, static_folder=None)
common_templates = os.path.join(os.path.dirname(__file__), '../../common/templates')
app.jinja_loader = ChoiceLoader([
    app.jinja_loader,
    FileSystemLoader(common_templates)
])
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = AppType.REMOTE_DOC.name.lower()

register_i18n(app, scope="my_remote_doc")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


@app.route('/static/<path:file_name>')
def get_static_file(file_name):
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
    return get_static_file(f"webfonts/{file_name}")


@app.route('/')
def app_home():
    app_source = AppType.REMOTE_DOC.name.lower()
    sys_name = AppType.get_app_type(app_source)
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
    add_access_count_by_uid(uid, 1, app_source)

    ctx = {
        "uid": uid,
        "t": t,
        "sys_name": sys_name,
        "app_source": app_source,
    }
    session_key = f"{uid}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)


@app.route('/workspace-files', methods=['GET'])
def list_workspace_files():
    try:
        files = []
        if os.path.exists(WORKSPACE_DIR):
            for f in os.listdir(WORKSPACE_DIR):
                file_path = os.path.join(WORKSPACE_DIR, f)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    files.append({
                        'name': f,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime,
                        'ext': os.path.splitext(f)[1].lower(),
                    })
        files.sort(key=lambda x: x['mtime'], reverse=True)
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        logger.error(f"列出工作空间文件失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/workspace/<path:filename>')
def download_workspace_file(filename):
    file_path = os.path.join(WORKSPACE_DIR, filename)
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(os.path.realpath(WORKSPACE_DIR)):
        logger.warning(f"非法下载路径: {filename}")
        abort(403)
    if not os.path.exists(real_path):
        logger.warning(f"工作空间文件不存在: {real_path}")
        abort(404)
    logger.info(f"下载工作空间文件: {real_path}")
    return send_from_directory(WORKSPACE_DIR, filename, as_attachment=True)


# 受保护的文件/目录，不允许删除
PROTECTED_NAMES = {'AGENTS.md', 'HEARTBEAT.md', 'IDENTITY.md', 'SOUL.md', 'TOOLS.md', 'USER.md', 'memory'}


@app.route('/workspace-files/<path:filename>', methods=['DELETE'])
def delete_workspace_file(filename):
    if filename in PROTECTED_NAMES:
        logger.warning(f"尝试删除受保护文件: {filename}")
        abort(403)
    file_path = os.path.join(WORKSPACE_DIR, filename)
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(os.path.realpath(WORKSPACE_DIR)):
        logger.warning(f"非法删除路径: {filename}")
        abort(403)
    if not os.path.exists(real_path):
        logger.warning(f"工作空间文件不存在: {real_path}")
        abort(404)
    try:
        os.remove(real_path)
        logger.info(f"已删除工作空间文件: {real_path}")
        return jsonify({'success': True, 'message': f'文件 {filename} 已删除'})
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '文件名为空'}), 400

        filename = file.filename
        # 避免文件名冲突：重名文件加时间戳前缀
        dest_path = os.path.join(WORKSPACE_DIR, filename)
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{int(time.time())}{ext}"
            dest_path = os.path.join(WORKSPACE_DIR, filename)

        file.save(dest_path)
        logger.info(f"文件上传成功: {dest_path}")
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'MyRemoteDoc'})


if __name__ == '__main__':
    # ====== Debug链接：生成带 token 的直接访问链接 ======
    debug_token = cm_utils.create_token(1, 0, 86400, my_cfg['sys']['cypher_key'])
    print(f"\n{'='*70}")
    print(f"  Debug访问链接（直接点击进入）:")
    print(f"  >>> http://127.0.0.1:19013?t={debug_token}")
    print(f"  uid=1, role=0, token有效期=24h")
    print(f"{'='*70}\n")

    port = 19013
    logger.info(f"my_remote_doc service listen on port {port}")
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
