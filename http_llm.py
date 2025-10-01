#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config

from flask import Flask, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import threading

app = Flask(__name__)

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

# 加载模型
model_path = "../DeepSeek-R1-Distill-Qwen-7B"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    dtype=torch.bfloat16,
    device_map="cpu",
    low_cpu_mem_usage=True
)


def generate_response(prompt, max_length=512):
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=max_length,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response[len(prompt):]  # 返回新生成的部分


# OpenAI 兼容的聊天接口
@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.json
    logger.info(f"chat_data, {data}")
    messages = data.get('messages', [])

    # 构建 prompt
    prompt = ""
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        if role == 'user':
            prompt += f"user: {content}\n"
        elif role == 'assistant':
            prompt += f"assistant: {content}\n"

    prompt += "assistant: "

    # 生成回复
    response_text = generate_response(prompt)

    return jsonify({
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "DeepSeek-R1",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text.strip()
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    })


# 模型列表接口
@app.route('/v1/models', methods=['GET'])
def list_models():
    return jsonify({
        "object": "list",
        "data": [{
            "id": "DeepSeek-R1",
            "object": "model",
            "created": 1677610602,
            "owned_by": "deepseek"
        }]
    })


if __name__ == '__main__':
    port = 8000
    logger.info(f"start listening {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)