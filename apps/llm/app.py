#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
大语言模型服务
"""
import logging.config
import json
import os.path
import time
import uuid
import functools

from flask import Flask, request, Response, stream_with_context
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch

from common.sys_init import init_yml_cfg

app = Flask(__name__)

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

my_cfg = init_yml_cfg()

# 加载模型
model_path = my_cfg['model']['path']
model_name = my_cfg['model']['name']
api_key = my_cfg['model'].get('key', '')  # 从配置读取API密钥
print(f"on host, or in container, model_path={model_path}, model_name={model_name}")


def timeout(seconds=60):
    """简单的超时装饰器"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()

            execution_time = end_time - start_time
            if execution_time > seconds:
                logger.warning(f"Function {func.__name__} took {execution_time:.2f}s (exceeded {seconds}s timeout)")
            return result
        return wrapper
    return decorator


def authenticate_request():
    """验证API密钥"""
    # 检查是否设置了API密钥
    if not api_key:
        return True  # 如果没有设置密钥，则允许所有请求

    # 从请求头获取Authorization
    auth_header = request.headers.get('Authorization', '')

    if not auth_header:
        logger.warning("Missing Authorization header")
        return False

    # 支持 Bearer token 和直接API key
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]  # 去掉 'Bearer ' 前缀
    else:
        token = auth_header

    # 验证token
    if token == api_key:
        return True
    else:
        logger.warning(f"Invalid API key: {token[:8]}...")
        return False


def require_auth(f):
    """认证装饰器"""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate_request():
            return Response(
                json.dumps({
                    "error": {
                        "message": "Invalid authentication",
                        "type": "invalid_request_error",
                        "code": 401
                    }
                }, ensure_ascii=False),
                mimetype='application/json',
                status=401
            )
        return f(*args, **kwargs)

    return decorated_function


try:
    abs_path = os.path.abspath(model_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"model_path_not_exist_err, {abs_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    # 4-bit 量化配置, for GPU with limited resource
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        # quantization_config=bnb_config,   # for GPU
        torch_dtype=torch.bfloat16,         # bfloat16以减少内存使用, for CPU or limited GPU
        # device_map="auto",                # for GPU
        device_map="cpu",                   # for CPU, 明确指定CPU
        low_cpu_mem_usage=True,             # for CPU, 优化CPU内存使用
        trust_remote_code=True
    )

    # 验证模型加载
    test_input = tokenizer("Test", return_tensors="pt")
    with torch.no_grad():
        _ = model.generate(**test_input, max_new_tokens=1)
    logger.info("Model loaded and verified successfully")

except Exception as e:
    logger.error(f"Model loading failed: {str(e)}")
    raise


@timeout(120)
def generate_response(prompt, max_length=512, temperature=0.7):
    """带性能监控的生成响应"""
    start_time = time.time()
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=max_length,
            temperature=temperature,
            do_sample=temperature > 0.1,
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
            early_stopping=True,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    final_response = response[len(prompt):].strip()
    generation_time = time.time() - start_time
    logger.info(f"Generation completed in {generation_time:.2f}s, tokens: {len(tokenizer.encode(final_response))}")
    return final_response


def build_prompt(messages):
    """构建prompt"""
    prompt = ""
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        if role == 'user':
            prompt += f"user: {content}\n"
        elif role == 'assistant':
            prompt += f"assistant: {content}\n"
    prompt += "assistant: "
    return prompt


def gen_stream(prompt, max_tokens, temperature):
    """生成流式响应的生成器函数"""
    request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    timestamp = int(time.time())

    logger.info(f"Starting stream generation for prompt length: {len(prompt)}")

    try:
        yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                   'created': timestamp, 'model': model_name,
                                   'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        prompt_length = len(inputs['input_ids'][0])

        logger.info(f"Input tokens: {prompt_length}, max_new_tokens: {max_tokens}")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1,
                early_stopping=True,
                return_dict_in_generate=True,
                output_scores=False
            )

        generated_ids = outputs.sequences[0]
        total_length = len(generated_ids)
        logger.info(f"Generated {total_length - prompt_length} new tokens")
        accumulated_text = ""
        for i in range(prompt_length, total_length):
            token_id = generated_ids[i].unsqueeze(0)
            token_text = tokenizer.decode(token_id, skip_special_tokens=True,
                                          clean_up_tokenization_spaces=False)
            if token_text.strip():
                accumulated_text += token_text
                yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                           'created': timestamp, 'model': model_name,
                                           'choices': [{'index': 0, 'delta': {'content': token_text}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
                time.sleep(0.01)

        logger.info(f"Stream generation completed: {accumulated_text[:100]}...")

        yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                   'created': timestamp, 'model': model_name,
                                   'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Stream generation error: {str(e)}")
        yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                   'created': timestamp, 'model': model_name,
                                   'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


def gen_normal_response(prompt, max_tokens, temperature):
    """生成普通响应"""
    request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    timestamp = int(time.time())

    try:
        response_text = generate_response(
            prompt,
            max_length=len(tokenizer.encode(prompt)) + max_tokens,
            temperature=temperature
        )

        response_data = {
            "id": request_id,
            "object": "chat.completion",
            "created": timestamp,
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(tokenizer.encode(prompt)),
                "completion_tokens": len(tokenizer.encode(response_text)),
                "total_tokens": len(tokenizer.encode(prompt)) + len(tokenizer.encode(response_text))
            }
        }

        return json.dumps(response_data, ensure_ascii=False), 200

    except Exception as e:
        logger.error(f"Non-stream generation error: {str(e)}")
        error_data = {"error": str(e)}
        return json.dumps(error_data, ensure_ascii=False), 500


@app.route('/v1/chat/completions', methods=['POST'])
@require_auth  # 添加认证
def chat_completions():
    start_time = time.time()
    data = request.json

    if not data:
        return json.dumps({"error": "Request body is required"}, ensure_ascii=False), 400

    logger.info(f"chat_data received")

    messages = data.get('messages', [])
    stream = data.get('stream', False)
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 512)

    if not messages or not isinstance(messages, list):
        return json.dumps({"error": "Messages must be a non-empty list"}, ensure_ascii=False), 400

    prompt = build_prompt(messages)
    logger.info(f"generated_prompt_length: {len(prompt)}")

    try:
        if stream:
            logger.info("Returning stream response")
            return Response(
                stream_with_context(gen_stream(prompt, max_tokens, temperature)),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                }
            )
        else:
            logger.info("Returning normal response")
            response_data, status_code = gen_normal_response(prompt, max_tokens, temperature)
            processing_time = time.time() - start_time
            logger.info(f"Request processed in {processing_time:.2f}s, stream: {stream}")
            return Response(response_data, mimetype='application/json', status=status_code)
    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        error_data = {"error": "Internal server error"}
        return Response(json.dumps(error_data, ensure_ascii=False),
                        mimetype='application/json', status=500)


@app.route('/v1/models', methods=['GET'])
@require_auth  # 添加认证
def list_models():
    timestamp = int(time.time())
    return json.dumps({
        "object": "list",
        "data": [{
            "id": model_name,
            "object": "model",
            "created": timestamp,
            "owned_by": "deepseek"
        }]
    }, ensure_ascii=False)


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return json.dumps({
        "status": "healthy",
        "model_loaded": True,
        "model": model_name,
        "timestamp": int(time.time())
    }, ensure_ascii=False)


@app.route('/', methods=['GET'])
def welcome():
    """欢迎页面"""
    return json.dumps({
        "status": 200,
        "msg": "hello LLM world, your can use API to interact with me",
        "model": model_name,
        "timestamp": int(time.time())
    }, ensure_ascii=False)


if __name__ == '__main__':
    # port = get_console_arg1()
    port = 16000
    logger.info(f"Starting {model_name} API server, listening on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)