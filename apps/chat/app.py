from flask import Flask, render_template, request, Response, jsonify
import json
import requests
from typing import Generator
import os
from dotenv import load_dotenv
import mimetypes
import tempfile

from common.const import UPLOAD_FOLDER

# 加载环境变量
load_dotenv()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app = Flask(__name__)

ALLOWED_EXTENSIONS = {
    'txt', 'md', 'py', 'js', 'html', 'css', 'json',
    'pdf', 'xlsx', 'docx',
    'jpg', 'jpeg', 'png', 'gif'
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ============== 配置常量 ==============
# LLM API 配置（可替换为任何兼容OpenAI API的接口）
class LLMConfig:
    # API 基础配置
    API_BASE_URL = os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
    API_KEY = os.getenv("LLM_API_KEY", "sk-********")
    MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")

    # 请求参数配置
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 2000))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
    TOP_P = float(os.getenv("TOP_P", 0.9))

    # 流式响应配置
    STREAM = True
    TIMEOUT = 30  # 请求超时时间（秒）

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

        # 文本文件直接读取
        if ext in ['txt', 'md', 'py', 'js', 'html', 'css', 'json']:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

        # PDF文件（需要安装PyPDF2或pdfplumber）
        elif ext == 'pdf':
            try:
                import PyPDF2
                text = []
                with open(filepath, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    for page in pdf.pages:
                        text.append(page.extract_text())
                return '\n'.join(text)
            except ImportError:
                return "[需要安装PyPDF2库来解析PDF文件]"

        # Word文档（需要安装python-docx）
        elif ext in ['docx']:
            try:
                import docx
                doc = docx.Document(filepath)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return '\n'.join(text)
            except ImportError:
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

                return '\n'.join(text_lines)
            except ImportError:
                return "[需要安装openpyxl库来解析Excel文件]"
            except Exception as e:
                return f"[读取Excel文件时出错: {str(e)}]"

        # 图片文件（需要安装PIL和pytesseract）
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            try:
                from PIL import Image
                import pytesseract
                image = Image.open(filepath)
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                return text if text else "[图片中未识别到文字]"
            except ImportError:
                return "[需要安装PIL和pytesseract库来识别图片文字]"

        else:
            return f"[不支持的文件格式: {ext}]"

    except Exception as e:
        return f"[读取文件时出错: {str(e)}]"


def generate_stream_response(messages: list) -> Generator[str, None, None]:
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
        "max_tokens": LLMConfig.MAX_TOKENS,
        "temperature": LLMConfig.TEMPERATURE,
        "top_p": LLMConfig.TOP_P,
        "stream": LLMConfig.STREAM,
    }

    try:
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
                            continue

        yield "data: [DONE]\n\n"

    except requests.exceptions.RequestException as e:
        error_msg = f"API请求错误: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        yield "data: [DONE]\n\n"


# ============== 路由 ==============
@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html', config={
        'temperature': LLMConfig.TEMPERATURE
    })


@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()

        if not user_message:
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
            generate_stream_response(messages),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'  # 禁用Nginx缓冲
            }
        )

    except Exception as e:
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400

        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'不支持的文件类型。支持的类型: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)

        if file_length > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': f'文件太大。最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB'
            }), 400

        # 保存临时文件
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(temp_path)

        # 提取文本内容
        content = extract_text_from_file(temp_path, file.filename)


        return jsonify({
            'success': True,
            'filename': file.filename,
            'content': content[:5000]  # 限制内容长度
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/config', methods=['GET'])
def get_config():
    """获取当前配置（不包含敏感信息）"""
    config_info = {
        'model': LLMConfig.MODEL_NAME,
        'max_tokens': LLMConfig.MAX_TOKENS,
        'temperature': LLMConfig.TEMPERATURE,
        'has_api_key': bool(LLMConfig.API_KEY)
    }
    return jsonify(config_info)


if __name__ == '__main__':
    # 检查API密钥
    if not LLMConfig.API_KEY:
        print("警告: LLM_API_KEY 未设置，请配置环境变量或修改代码")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=19000,
        threaded=True
    )