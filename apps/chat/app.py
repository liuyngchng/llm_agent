from flask import Flask, render_template, request, Response, jsonify
import json
import requests
from typing import Generator
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

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
    return render_template('index.html')

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
        port=5000,
        threaded=True
    )
