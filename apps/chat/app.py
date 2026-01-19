#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import time

from flask import Flask, request, Response, jsonify, send_from_directory, abort, redirect, url_for

import os
import sys
import logging.config
import logging

from apps.chat.chat_util import LLMConfig, generate_stream_response, allowed_file, \
    MAX_FILE_SIZE, ALLOWED_EXTENSIONS, extract_text_from_file
from common import my_enums
from common.bp_auth import auth_bp, get_client_ip, auth_info
from common.const import UPLOAD_FOLDER, SESSION_TIMEOUT
from common.my_enums import AppType
from common.sys_init import init_yml_cfg

my_cfg = init_yml_cfg()

# 确保上传文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"上传文件夹路径: {UPLOAD_FOLDER}")

# 创建 Flask 应用
app = Flask(__name__, static_folder=None)
app.config['CFG'] = {}
app.config['CFG'] = my_cfg
app.config['APP_SOURCE'] = my_enums.AppType.CHAT.name.lower()

app.register_blueprint(auth_bp)

# 配置模板文件夹路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    print(f"模板文件夹路径: {TEMPLATE_DIR}")

# 配置日志
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
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=AppType.CHAT.name.lower()))

# @app.route('/')
# def index():
#     """渲染主页面"""
#     logger.info("访问首页")
#     return render_template('index.html', config={
#         'temperature': LLMConfig.TEMPERATURE
#     })

@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        custom_max_tokens = data.get('max_tokens')
        history_length = len(data.get('history', []))
        t = data.get('t', 0)
        uid = int(data.get('uid', ''))
        session_key = f"{uid}_{get_client_ip()}"
        if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
            raise RuntimeError("illegal_access")
        logger.info(f"收到聊天请求，消息长度: {len(user_message)}, 历史长度: {history_length}")
        logger.info(f"请求的max_tokens: {custom_max_tokens}")
        logger.info(f"默认MAX_TOKENS: {LLMConfig.MAX_TOKENS}")

        if not user_message:
            logger.warning("消息为空")
            return jsonify({'error': '消息不能为空'}), 400

        # 构建消息历史
        messages = [{"role": "system", "content": LLMConfig.SYSTEM_PROMPT}]

        # 添加上下文消息（如果需要）
        chat_history = data.get('history', [])
        for msg in chat_history[-10:]:  # 限制历史记录长度
            messages.append(msg)

        # 添加用户消息
        messages.append({"role": "user", "content": user_message})

        # 记录发送的messages内容（脱敏）
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if content:
                preview = content[:100] + "..." if len(content) > 100 else content
                logger.info(f"消息[{i}] role={role}, 内容预览: {preview}")

        # 返回流式响应
        return Response(
            generate_stream_response(messages, my_cfg['api'], max_tokens=custom_max_tokens),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'  # 禁用Nginx缓冲
            }
        )

    except Exception as e:
        logger.error(f"聊天请求处理失败: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        if 'file' not in request.files:
            logger.warning("没有选择文件")
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        file = request.files['file']

        if file.filename == '':
            logger.warning("文件名为空")
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        if not allowed_file(file.filename):
            logger.warning(f"不支持的文件类型: {file.filename}")
            return jsonify({
                'success': False,
                'error': f'不支持的文件类型。支持的类型: {", ".join(ALLOWED_EXTENSIONS)}'
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
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(temp_path)
        logger.info(f"文件保存成功: {temp_path}, 大小: {file_length} 字节")
        content = extract_text_from_file(temp_path, file.filename)

        # 清理临时文件
        try:
            os.remove(temp_path)
            logger.debug(f"临时文件已清理: {temp_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

        return jsonify({
            'success': True,
            'filename': file.filename,
            'content': content[:5000]  # 限制内容长度
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


# 添加健康检查路由
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'AI Chat Assistant'})

if __name__ == '__main__':
    # 检查API密钥
    if not my_cfg['api']['llm_api_key'] or not my_cfg['api']['llm_api_key'].strip():
        logger.warning("LLM_API_KEY 未设置，请配置环境变量或修改代码")
    else:
        logger.info(f"API密钥已配置，使用模型: {my_cfg['api']['llm_model_name']}")

    # 检查依赖库
    logger.info("检查依赖库...")
    try:
        import PyPDF2

        logger.info("✓ PyPDF2 已安装")
    except ImportError:
        logger.warning("⚠ PyPDF2 未安装，PDF文件解析将不可用")

    try:
        import docx

        logger.info("✓ python-docx 已安装")
    except ImportError:
        logger.warning("⚠ python-docx 未安装，Word文档解析将不可用")

    try:
        from openpyxl import load_workbook

        logger.info("✓ openpyxl 已安装")
    except ImportError:
        logger.warning("⚠ openpyxl 未安装，Excel文件解析将不可用")

    try:
        from PIL import Image
        import pytesseract

        logger.info("✓ PIL 和 pytesseract 已安装")
    except ImportError:
        logger.warning("⚠ PIL 或 pytesseract 未安装，图片文字识别将不可用")

    logger.info("启动Flask应用...")
    app.run(
        debug=True,
        host='0.0.0.0',
        port=19000,
        threaded=True
    )