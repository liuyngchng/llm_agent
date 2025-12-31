#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from flask import Flask, render_template, request, Response, jsonify, send_from_directory, abort
import json
import requests
from typing import Generator
import os
import sys
from dotenv import load_dotenv
import logging.config
import logging

from common.const import UPLOAD_FOLDER

# 加载环境变量
load_dotenv()

# 确保上传文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"上传文件夹路径: {UPLOAD_FOLDER}")

# 创建 Flask 应用
app = Flask(__name__)

# 配置模板文件夹路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
if not os.path.exists(TEMPLATE_DIR):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    print(f"模板文件夹路径: {TEMPLATE_DIR}")

ALLOWED_EXTENSIONS = {
    'txt', 'md', 'py', 'js', 'html', 'css', 'json',
    'pdf', 'xlsx', 'docx',
    'jpg', 'jpeg', 'png', 'gif'
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

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


# ============== 配置常量 ==============
# LLM API 配置（可替换为任何兼容OpenAI API的接口）
class LLMConfig:
    # API 基础配置
    API_BASE_URL = os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
    API_KEY = os.getenv("LLM_API_KEY", "")
    MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")

    # 请求参数配置
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 8000))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
    TOP_P = float(os.getenv("TOP_P", 0.9))

    # 流式响应配置
    STREAM = True
    TIMEOUT = 1180  # 请求超时时间（秒）

    # 系统提示词
    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "你是一个有用的AI助手。请用中文回答用户的问题。")


# ============== 辅助函数 ==============
def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_file(filepath, filename):
    """从文件中提取文本内容"""
    try:
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

        logger.info(f"正在提取文件: {filename}, 扩展名: {ext}")

        # 文本文件直接读取
        if ext in ['txt', 'md', 'py', 'js', 'html', 'css', 'json']:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                logger.info(f"文本文件读取成功，长度: {len(content)} 字符")
                return content

        # PDF文件（需要安装PyPDF2或pdfplumber）
        elif ext == 'pdf':
            try:
                import PyPDF2
                text = []
                with open(filepath, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    for page_num, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        text.append(page_text)
                result = '\n'.join(text)
                logger.info(f"PDF文件解析成功，页数: {len(pdf.pages)}，长度: {len(result)} 字符")
                return result
            except ImportError:
                logger.warning("需要安装PyPDF2库来解析PDF文件")
                return "[需要安装PyPDF2库来解析PDF文件]"

        # Word文档（需要安装python-docx）
        elif ext in ['docx']:
            try:
                import docx
                doc = docx.Document(filepath)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                result = '\n'.join(text)
                logger.info(f"Word文档解析成功，段落数: {len(text)}，长度: {len(result)} 字符")
                return result
            except ImportError:
                logger.warning("需要安装python-docx库来解析Word文档")
                return "[需要安装python-docx库来解析Word文档]"

        # Excel文件（需要安装openpyxl）
        elif ext in ['xlsx']:
            try:
                from openpyxl import load_workbook
                wb = load_workbook(filename=filepath, read_only=True, data_only=True)
                text_lines = []

                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    text_lines.append(f"## {sheet_name}")

                    # 获取最大列宽
                    max_col = ws.max_column
                    max_row = ws.max_row

                    if max_row > 0 and max_col > 0:
                        # 创建Markdown表格
                        rows = []
                        for row in ws.iter_rows(min_row=1, max_row=max_row,
                                                min_col=1, max_col=max_col,
                                                values_only=True):
                            # 将None转换为空字符串
                            formatted_row = [str(cell).replace('|', '\\|') if cell is not None else ""
                                             for cell in row]
                            rows.append(formatted_row)

                        # 生成Markdown表格
                        if rows:
                            # 表头分隔线
                            header_separator = ['---'] * len(rows[0])

                            # 构建Markdown
                            md_lines = []
                            md_lines.append('| ' + ' | '.join(rows[0]) + ' |')
                            md_lines.append('| ' + ' | '.join(header_separator) + ' |')

                            for row in rows[1:]:
                                md_lines.append('| ' + ' | '.join(row) + ' |')

                            text_lines.append('\n'.join(md_lines))
                        text_lines.append('')  # 空行分隔

                result = '\n'.join(text_lines)
                logger.info(f"Excel文件解析成功，工作表数: {len(wb.sheetnames)}，长度: {len(result)} 字符")
                return result
            except ImportError:
                logger.warning("需要安装openpyxl库来解析Excel文件")
                return "[需要安装openpyxl库来解析Excel文件]"
            except Exception as e:
                logger.error(f"读取Excel文件时出错: {str(e)}")
                return f"[读取Excel文件时出错: {str(e)}]"

        # 图片文件（需要安装PIL和pytesseract）
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            try:
                from PIL import Image
                import pytesseract
                image = Image.open(filepath)
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                logger.info(f"图片文件识别成功，识别到 {len(text)} 字符")
                return text if text else "[图片中未识别到文字]"
            except ImportError:
                logger.warning("需要安装PIL和pytesseract库来识别图片文字")
                return "[需要安装PIL和pytesseract库来识别图片文字]"

        else:
            logger.warning(f"不支持的文件格式: {ext}")
            return f"[不支持的文件格式: {ext}]"

    except Exception as e:
        logger.error(f"读取文件时出错: {str(e)}")
        return f"[读取文件时出错: {str(e)}]"


def generate_stream_response(messages: list, max_tokens: int = None) -> Generator[str, None, None]:
    """
    生成流式响应
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLMConfig.API_KEY}"
    }

    payload = {
        "model": LLMConfig.MODEL_NAME,
        "messages": messages,
        "max_tokens": max_tokens or LLMConfig.MAX_TOKENS,
        "temperature": LLMConfig.TEMPERATURE,
        "top_p": LLMConfig.TOP_P,
        "stream": LLMConfig.STREAM,
    }

    try:
        logger.info(f"向LLM API发送请求，模型: {LLMConfig.MODEL_NAME}, 消息数量: {len(messages)}")

        response = requests.post(
            f"{LLMConfig.API_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=LLMConfig.TIMEOUT
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]  # 移除 'data: ' 前缀
                    if data != '[DONE]':
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta and delta['content']:
                                    yield f"data: {json.dumps({'content': delta['content']})}\n\n"
                        except json.JSONDecodeError:
                            logger.warning("解析JSON数据失败")
                            continue

        yield "data: [DONE]\n\n"

    except requests.exceptions.RequestException as e:
        error_msg = f"API请求错误: {str(e)}"
        logger.error(error_msg)
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        yield "data: [DONE]\n\n"


# ============== 路由 ==============

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
    return render_template('index.html', config={
        'temperature': LLMConfig.TEMPERATURE
    })


@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        custom_max_tokens = data.get('max_tokens')
        history_length = len(data.get('history', []))

        logger.info(f"收到聊天请求，消息长度: {len(user_message)}, 历史长度: {history_length}")

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

        # 确保上传文件夹存在
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # 保存临时文件
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(temp_path)

        logger.info(f"文件保存成功: {temp_path}, 大小: {file_length} 字节")

        # 提取文本内容
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
    """获取当前配置（不包含敏感信息）"""
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