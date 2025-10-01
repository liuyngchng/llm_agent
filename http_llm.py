#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import json
import time
import uuid

from flask import Flask, request, jsonify, Response, stream_with_context
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import threading

app = Flask(__name__)

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

# 加载模型
model_path = "../DeepSeek-R1-Distill-Qwen-7B"
model_name = "DeepSeek-R1"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    dtype=torch.bfloat16,
    device_map="cpu",
    low_cpu_mem_usage=True
)


def generate_response(prompt, max_length=512, temperature=0.7):
    """普通生成响应"""
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=max_length,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response[len(prompt):].strip()


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
        # 先发送开始消息
        yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                   'created': timestamp, 'model': model_name,
                                   'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"

        # 生成流式内容 - 关键修复：确保这里实际生成了内容
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
        prompt_length = len(inputs['input_ids'][0])

        logger.info(f"Input tokens: {prompt_length}, max_new_tokens: {max_tokens}")

        with torch.no_grad():
            # 使用 generate 并确保返回所有序列
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

        # 获取生成的序列
        generated_ids = outputs.sequences[0]
        total_length = len(generated_ids)

        logger.info(f"Generated {total_length - prompt_length} new tokens")

        # 逐个token输出
        accumulated_text = ""
        for i in range(prompt_length, total_length):
            token_id = generated_ids[i].unsqueeze(0)
            token_text = tokenizer.decode(token_id, skip_special_tokens=True,
                                          clean_up_tokenization_spaces=False)

            if token_text.strip():
                accumulated_text += token_text
                yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                           'created': timestamp, 'model': model_name,
                                           'choices': [{'index': 0, 'delta': {'content': token_text}, 'finish_reason': None}]})}\n\n"

                # 添加小延迟，让流式效果更明显
                time.sleep(0.01)

        logger.info(f"Stream generation completed: {accumulated_text[:100]}...")

        # 发送结束消息
        yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                   'created': timestamp, 'model': model_name,
                                   'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Stream generation error: {str(e)}")
        yield f"data: {json.dumps({'id': request_id, 'object': 'chat.completion.chunk',
                                   'created': timestamp, 'model': model_name,
                                   'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
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

        return jsonify({
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
        })

    except Exception as e:
        logger.error(f"Non-stream generation error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# OpenAI 兼容的聊天接口
@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    start_time = time.time()
    data = request.json

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    logger.info(f"chat_data received")

    messages = data.get('messages', [])
    stream = data.get('stream', False)
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 512)

    # 验证消息格式
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "Messages must be a non-empty list"}), 400

    # 构建prompt
    prompt = build_prompt(messages)
    logger.info(f"generated_prompt_length: {len(prompt)}")

    try:
        if stream:
            # 流式响应
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
            # 非流式响应
            logger.info("Returning normal response")
            response = gen_normal_response(prompt, max_tokens, temperature)

        processing_time = time.time() - start_time
        logger.info(f"Request processed in {processing_time:.2f}s, stream: {stream}")
        return response

    except Exception as e:
        logger.error(f"Chat completion error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


# 模型列表接口
@app.route('/v1/models', methods=['GET'])
def list_models():
    timestamp = int(time.time())
    return jsonify({
        "object": "list",
        "data": [{
            "id": model_name,
            "object": "model",
            "created": timestamp,
            "owned_by": "deepseek"
        }]
    })


# 健康检查接口
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "model_loaded": True,
        "model": model_name,
        "timestamp": int(time.time())
    })


if __name__ == '__main__':
    port = 8000
    logger.info(f"Starting {model_name} API server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)