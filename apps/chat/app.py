#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import tempfile
import time

from flask import Flask, request, Response, jsonify, send_from_directory, abort, redirect, url_for

import os
import sys

from dotenv import load_dotenv
import logging.config
import logging

from apps.chat.chat_util import LLMConfig, generate_stream_response, allowed_file, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, \
    extract_text_from_file
from apps.chat.document_processor import DocumentProcessor
from common import my_enums
from common.bp_auth import auth_bp, get_client_ip, auth_info
from common.const import UPLOAD_FOLDER, SESSION_TIMEOUT
from common.my_enums import AppType
from common.sys_init import init_yml_cfg

# 加载环境变量
load_dotenv()
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

# 初始化文档处理器
doc_processor = DocumentProcessor(UPLOAD_FOLDER)

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
            generate_stream_response(messages, max_tokens=custom_max_tokens),
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


@app.route('/document_chat')
def document_chat():
    """文档问答页面"""
    try:
        uid = request.args.get('uid')
        t = request.args.get('t')
        app_source = request.args.get('app_source', AppType.CHAT.name.lower())

        if not uid or not t:
            return redirect(url_for('auth.login_index', app_source=app_source))

        # 验证会话（使用原有逻辑）
        session_key = f"{uid}_{get_client_ip()}"
        if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
            return redirect(url_for('auth.login_index', app_source=app_source))

        logger.info(f"用户 {uid} 访问文档问答页面")

        # 渲染文档聊天页面
        return render_template('document_chat.html',
                               uid=uid,
                               t=t,
                               app_source=app_source)

    except Exception as e:
        logger.error(f"渲染文档页面失败: {str(e)}")
        return redirect(url_for('app_home'))

@app.route('/upload_document', methods=['POST'])
def upload_document():
    """上传并处理大文档"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        if not file.filename.lower().endswith('.docx'):
            return jsonify({'success': False, 'error': '仅支持Word文档(.docx)'}), 400

        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
            file.save(tmp_file.name)
            temp_path = tmp_file.name

        try:
            # 处理大文档
            result = doc_processor.process_large_document(temp_path, file.filename)

            if 'error' in result:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 500

            return jsonify({
                'success': True,
                'document_id': result['metadata']['file_hash'],
                'filename': file.filename,
                'total_chunks': result.get('total_chunks', 0),
                'vectorized': result.get('vectorized', False),
                'message': f'文档已成功处理，分为 {result.get("total_chunks", 0)} 个分块'
            })

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass

    except Exception as e:
        logger.error(f"上传大文档失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/chat_with_document', methods=['POST'])
def chat_with_document():
    """基于文档的聊天"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        document_id = data.get('document_id')

        if not user_message:
            return jsonify({'error': '消息不能为空'}), 400

        if not document_id:
            return jsonify({'error': '请指定文档ID'}), 400

        # 身份验证（使用原有逻辑）
        uid = int(data.get('uid', ''))
        session_key = f"{uid}_{get_client_ip()}"
        if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
            raise RuntimeError("illegal_access")

        # 搜索相关文档片段
        relevant_chunks = doc_processor.search_relevant_chunks(document_id, user_message, top_k=3)

        if not relevant_chunks:
            return jsonify({
                'error': '未找到相关文档内容，请尝试其他问题'
            }), 404

        # 构建增强的提示词
        context_parts = []
        for i, chunk in enumerate(relevant_chunks):
            context_parts.append(f"【文档片段 {i + 1}】\n{chunk['content'][:1500]}...")

        context = "\n\n".join(context_parts)

        enhanced_prompt = f"""基于以下文档片段，回答用户的问题：

{context}

用户问题：{user_message}

要求：
1. 只根据提供的文档内容回答
2. 如果文档中没有相关信息，请说明"文档中没有找到相关信息"
3. 回答要具体，必要时可以引用片段编号
4. 用中文回答

回答："""

        # 构建消息
        messages = [
            {"role": "system", "content": "你是一个专业的文档问答助手。"},
            {"role": "user", "content": enhanced_prompt}
        ]

        # 流式响应
        return Response(
            generate_stream_response(messages),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"文档聊天失败: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/list_documents', methods=['GET'])
def list_documents():
    """获取已处理的文档列表"""
    try:
        documents = []
        cache_dir = os.path.join(UPLOAD_FOLDER, "document_cache")
        if not os.path.exists(cache_dir):
            return jsonify({
                'success': True,
                'documents': documents,
                'total': 0
            })

        for file in os.listdir(cache_dir):
            if file.endswith('.json'):
                file_path = os.path.join(cache_dir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        documents.append({
                            'document_id': data['metadata']['file_hash'],
                            'filename': data['metadata']['filename'],
                            'processed_time': data.get('processed_time'),
                            'total_chunks': data.get('total_chunks', 0),
                            'file_size': data['metadata'].get('file_size')
                        })
                except Exception as e:
                    logger.error(f"读取文档缓存失败 {file}: {e}")

        return jsonify({
            'success': True,
            'documents': documents,
            'total': len(documents)
        })

    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/config', methods=['GET'])
def get_config():
    """获取当前配置（配置中不包含敏感信息）"""
    logger.info("获取配置信息")
    config_info = {
        'model': LLMConfig.MODEL_NAME,
        'max_tokens': LLMConfig.MAX_TOKENS,
        'temperature': LLMConfig.TEMPERATURE,
        'has_api_key': bool(LLMConfig.API_KEY and LLMConfig.API_KEY.strip())
    }
    return jsonify(config_info)


# 添加健康检查路由
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'AI Chat Assistant'})

if __name__ == '__main__':
    # 检查API密钥
    if not LLMConfig.API_KEY or not LLMConfig.API_KEY.strip():
        logger.warning("LLM_API_KEY 未设置，请配置环境变量或修改代码")
    else:
        logger.info(f"API密钥已配置，使用模型: {LLMConfig.MODEL_NAME}")

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