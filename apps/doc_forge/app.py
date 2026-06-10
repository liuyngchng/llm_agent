#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import time
import json

from flask import Flask, request, Response, jsonify, send_from_directory, abort, render_template
from jinja2 import ChoiceLoader, FileSystemLoader

import os
import logging.config
import logging

from apps.doc_forge.chat_util import LLMConfig, generate_stream_response_with_execution, \
    build_doc_processing_system_prompt, allowed_file, \
    MAX_FILE_SIZE
from common import my_enums, statistic_util, cm_utils
from common.auth_util import auth_info, get_client_ip, redirect_to_portal_login, get_portal_login_url
from common.cm_utils import estimate_tokens
from common.const import SESSION_TIMEOUT, get_const
from common.i18n._hooks import register_i18n
from common.i18n import get_msg
from common.my_enums import AppType
from common.ocr_util import ImageOCR
from common.statistic_util import add_input_token_by_uid, add_output_token_by_uid
from common.sys_init import init_yml_cfg

my_cfg = init_yml_cfg()

UPLOAD_DIR = my_cfg['sys'].get('upload_dir')
if not UPLOAD_DIR:
    raise RuntimeError("cfg.yml 中未配置 sys.upload_dir，请设置一个绝对路径")

# 工作空间目录：优先使用 cfg.yml 中的 sys.workspace，这个配置需要是一个绝对路径，如果没有配置，则直接报错
WORKSPACE_DIR = my_cfg['sys'].get('workspace')
if not WORKSPACE_DIR:
    raise RuntimeError("cfg.yml 中未配置 sys.workspace，请设置一个绝对路径")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(WORKSPACE_DIR, exist_ok=True)
print(f"上传文件夹路径: {UPLOAD_DIR}, 工作空间路径: {WORKSPACE_DIR}")

# 初始化 OCR 识别器
ocr_engine = ImageOCR(my_cfg)
print(f"OCR引擎已初始化，模型: {ocr_engine.model_name}, API: {ocr_engine.api_uri}")

# 会话文件追踪: uid -> [file_paths]
session_files = {}

# 创建 Flask 应用
app = Flask(__name__, static_folder=None)
# 将 common/templates 加入模板搜索路径
common_templates = os.path.join(os.path.dirname(__file__), '../../common/templates')
app.jinja_loader = ChoiceLoader([
    app.jinja_loader,
    FileSystemLoader(common_templates)
])
app.config['CFG'] = {}
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = my_enums.AppType.DOC_FORGE.name.lower()

register_i18n(app, scope="doc_forge")

# 配置模板文件夹路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    print(f"模板文件夹路径: {TEMPLATE_DIR}")

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format=LOG_FORMATTER,force=True)
logger = logging.getLogger(__name__)

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
            # logger.debug(f"提供静态文件: {file_name} 从 {static_dir}")
            return send_from_directory(static_dir, file_name)

    logger.error(f"静态文件未找到: {file_name}")
    abort(404)


@app.route('/webfonts/<path:file_name>')
def get_webfonts_file(file_name):
    """提供字体文件"""
    font_file_name = f"webfonts/{file_name}"
    return get_static_file(font_file_name)

@app.route('/')
def app_home():
    app_source = AppType.DOC_FORGE.name.lower()
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

    greeting = get_const("greeting", app_source)
    arg1 = get_const("arg1", app_source)
    arg2 = get_const("arg2", app_source)
    arg3 = get_const("arg3", app_source)

    ctx = {
        "uid": uid,
        "t": t,
        "sys_name": sys_name,
        "greeting": greeting,
        "app_source": app_source,
        "hack_admin": hack_admin,
        "arg1": arg1,
        "arg2": arg2,
        "arg3": arg3,
    }

    session_key = f"{uid}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)



@app.route('/doc_forge', methods=['POST'])
def chat():
    """处理聊天请求 — 支持文档处理与脚本执行"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        custom_max_tokens = data.get('max_tokens')
        history_length = len(data.get('history', []))
        t = data.get('t', 0)
        uid = int(data.get('uid', -1))
        session_key = f"{uid}_{get_client_ip()}"
        if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
            return jsonify({'error': 'auth_expired', 'redirect': get_portal_login_url(AppType.DOC_FORGE.name.lower())}), 401
        logger.info(f"收到用户消息: {user_message}, 历史长度: {history_length}, custom_max_tokens, {custom_max_tokens}")

        if not user_message:
            logger.warning("消息为空")
            return jsonify({'error': get_msg('doc_forge.error_empty_message')}), 400

        # 获取当前用户的已上传文件路径
        user_files = session_files.get(uid, [])

        # 构建增强的系统提示词（包含可用文件信息）
        system_prompt = build_doc_processing_system_prompt(
            file_paths=user_files,
            output_dir=WORKSPACE_DIR,
            upload_dir=UPLOAD_DIR
        )

        # 构建消息历史
        messages = [{"role": "system", "content": system_prompt}]

        # 添加上下文消息
        chat_history = data.get('history', [])
        for msg in chat_history[-10:]:
            messages.append(msg)

        # 添加用户消息
        messages.append({"role": "user", "content": user_message})
        logger.info(f"user_msg_input: messages_count={len(messages)}")
        input_tokens = estimate_tokens(str(messages))
        logger.info(f"{uid}, input_tokens, {input_tokens}")
        add_input_token_by_uid(uid, input_tokens, AppType.DOC_FORGE.name.lower())

        # 包裹流式响应，统计 output tokens
        def generate_and_count():
            full_response = ""
            for sse_chunk in generate_stream_response_with_execution(
                messages, my_cfg['api'],
                output_dir=WORKSPACE_DIR,
                upload_dir=UPLOAD_DIR,
                max_tokens=custom_max_tokens,
                file_paths=user_files
            ):
                yield sse_chunk
                if sse_chunk.startswith('data: ') and sse_chunk != 'data: [DONE]\n\n':
                    try:
                        chunk_data = json.loads(sse_chunk[6:].strip())
                        if 'content' in chunk_data:
                            full_response += chunk_data['content']
                    except (json.JSONDecodeError, KeyError):
                        pass
            output_tokens = estimate_tokens(full_response)
            logger.info(f"{uid}, output_tokens, {output_tokens}")
            add_output_token_by_uid(uid, output_tokens, AppType.DOC_FORGE.name.lower())
            # 记录完整返回给前端的内容
            logger.info(f"最终返回给前端的完整消息:\n{full_response}")

        return Response(
            generate_and_count(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"聊天请求处理失败: {str(e)}")
        return jsonify({'error': get_msg('common.server_error', msg=str(e))}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传 — 文件被持久化保存以供后续处理"""
    try:
        if 'file' not in request.files:
            logger.warning("没有选择文件")
            return jsonify({'success': False, 'error': get_msg('doc_forge.error_no_file')}), 400

        file = request.files['file']
        uid = int(request.form.get('uid', '-1'))

        if file.filename == '':
            logger.warning("文件名为空")
            return jsonify({'success': False, 'error': get_msg('doc_forge.error_no_file')}), 400

        if not allowed_file(file.filename):
            logger.warning(f"不支持的文件类型: {file.filename}")
            return jsonify({
                'success': False,
                'error': get_msg('doc_forge.error_unsupported_file', name=file.filename)
            }), 400

        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)

        if file_length > MAX_FILE_SIZE:
            logger.warning(f"文件太大: {file_length} > {MAX_FILE_SIZE}")
            return jsonify({
                'success': False,
                'error': f'文件太大。最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB'
            }), 400

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # 使用时间戳前缀避免文件名冲突
        saved_filename = f"{int(time.time())}_{file.filename}"
        saved_path = os.path.join(UPLOAD_DIR, saved_filename)
        file.save(saved_path)
        logger.info(f"文件保存成功: {saved_path}, 大小: {file_length} 字节")

        # 追踪此用户的文件
        if uid not in session_files:
            session_files[uid] = []
        session_files[uid].append(saved_path)

        return jsonify({
            'success': True,
            'filename': file.filename,
            'saved_filename': saved_filename,
            'file_count': len(session_files[uid])
        })

    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/config', methods=['GET'])
def get_config():
    """获取当前配置（配置中不包含敏感信息）"""
    logger.info("获取配置信息")
    config_info = {
        'model': my_cfg['api']['llm_model_name'],
        'max_tokens': LLMConfig.MAX_TOKENS,
        'temperature': LLMConfig.TEMPERATURE,
        'has_api_key': bool(my_cfg['api']['llm_api_key'] and my_cfg['api']['llm_api_key'].strip())
    }
    return jsonify(config_info)


@app.route('/download/output/<path:filename>')
def download_output(filename):
    """下载生成的文档文件"""
    file_path = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(file_path):
        logger.warning(f"下载文件不存在: {file_path}")
        abort(404)
    logger.info(f"下载文件: {file_path}")
    return send_from_directory(WORKSPACE_DIR, filename, as_attachment=True)


@app.route('/download/upload/<path:filename>')
def download_upload(filename):
    """下载上传的原始文件"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        logger.warning(f"下载文件不存在: {file_path}")
        abort(404)
    logger.info(f"下载文件: {file_path}")
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)


@app.route('/workspace-files', methods=['GET'])
def list_workspace_files():
    """列出工作空间中的所有文件"""
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
        # 按修改时间倒序排列
        files.sort(key=lambda x: x['mtime'], reverse=True)
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        logger.error(f"列出工作空间文件失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/workspace/<path:filename>')
def download_workspace_file(filename):
    """下载工作空间中的文件"""
    file_path = os.path.join(WORKSPACE_DIR, filename)
    # 防止目录穿越
    real_path = os.path.realpath(file_path)
    if not real_path.startswith(os.path.realpath(WORKSPACE_DIR)):
        logger.warning(f"非法下载路径: {filename}")
        abort(403)
    if not os.path.exists(real_path):
        logger.warning(f"工作空间文件不存在: {real_path}")
        abort(404)
    logger.info(f"下载工作空间文件: {real_path}")
    return send_from_directory(WORKSPACE_DIR, filename, as_attachment=True)


@app.route('/workspace-files/<path:filename>', methods=['DELETE'])
def delete_workspace_file(filename):
    """删除工作空间中的文件"""
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


# 添加健康检查路由
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'DocForge'})

if __name__ == '__main__':
    # ====== Debug/开发模式：生成带 token 的直接访问链接 ======
    debug_uid = 1
    debug_role = 0
    debug_timeout = 86400  # 24小时
    debug_token = cm_utils.create_token(debug_uid, debug_role, debug_timeout, my_cfg['sys']['cypher_key'])
    print(f"\n{'='*70}")
    print(f"  Debug访问链接（直接点击进入）:")
    port = my_cfg['sys'].get('port', 20000)
    print(f"  >>> http://127.0.0.1:{port}?t={debug_token}")
    print(f"  uid={debug_uid}, role={debug_role}, token有效期=24h")
    print(f"{'='*70}\n")

    # 检查API密钥
    if not my_cfg['api']['llm_api_key'] or not my_cfg['api']['llm_api_key'].strip():
        logger.warning("LLM_API_KEY 未设置，请配置环境变量或修改代码")
    else:
        logger.info(f"API密钥已配置，使用模型: {my_cfg['api']['llm_model_name']}")

    # OCR 引擎状态
    if ocr_engine and ocr_engine.api_uri:
        logger.info(f"✓ OCR 引擎已初始化，模型: {ocr_engine.model_name}，API: {ocr_engine.api_uri}")
    else:
        logger.warning("⚠ OCR 引擎未配置，图片文字识别将不可用")

    # 检查依赖库
    logger.debug("检查依赖库...")
    try:
        import pdfplumber

        logger.debug("✓ pdfplumber 已安装")
    except ImportError:
        logger.warning("⚠ pdfplumber 未安装，PDF文件解析将不可用")

    try:
        import docx

        logger.debug("✓ python-docx 已安装")
    except ImportError:
        logger.warning("⚠ python-docx 未安装，Word文档解析将不可用")

    try:
        from openpyxl import load_workbook

        logger.debug("✓ openpyxl 已安装")
    except ImportError:
        logger.warning("⚠ openpyxl 未安装，Excel文件解析将不可用")

    port = 20000
    logger.info(f"chat_service_listen_on_port {port}")
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)