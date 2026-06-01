#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
LLM API Adapter: 将兼容 OpenAI 的大语言模型 API 转换为兼容 Anthropic 的 API
供 Claude Code 等 Anthropic 客户端使用
"""
import logging.config
import json
import os
import time
import uuid
import re

import requests
from flask import Flask, request, Response, stream_with_context, jsonify

from common.sys_init import init_yml_cfg

app = Flask(__name__)

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

my_cfg = init_yml_cfg()
llm_api_uri = my_cfg['api']['llm_api_uri'].rstrip('/')
llm_api_key = my_cfg['api']['llm_api_key']
llm_model_name = my_cfg['api']['llm_model_name']

ANTHROPIC_VERSION = "2023-06-01"

FINISH_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}


def make_json_response(data, status=200, headers=None):
    """统一创建 JSON 响应，正确处理 UTF-8 编码"""
    response_data = json.dumps(data, ensure_ascii=False, indent=None, separators=(',', ':'))
    logger.info(f"json_response_data_first_500_chars: {response_data[:500]}")
    logger.info(f"json_response_data_repr_first_200: {repr(response_data[:200])}")
    response_headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-cache'
    }
    if headers:
        response_headers.update(headers)

    return Response(
        response_data.encode('utf-8'),  # 显式编码为 UTF-8 字节
        status=status,
        headers=response_headers
    )


def anthropic_to_openai_messages(anthropic_messages, system_prompt=None):
    """将 Anthropic messages 转换为 OpenAI messages 格式"""
    openai_messages = []

    if system_prompt:
        if isinstance(system_prompt, list):
            system_text = ""
            for block in system_prompt:
                if block.get("type") == "text":
                    system_text += block.get("text", "")
            openai_messages.append({"role": "system", "content": system_text})
        else:
            openai_messages.append({"role": "system", "content": system_prompt})

    for msg in anthropic_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            openai_content = _convert_anthropic_content_to_openai(content)
            openai_messages.append({"role": "user", "content": openai_content})
        elif role == "assistant":
            openai_content = _convert_anthropic_assistant_content_to_openai(content)
            openai_messages.append({"role": "assistant", "content": openai_content})

    return openai_messages


def _convert_anthropic_content_to_openai(content):
    """转换 Anthropic user content 为 OpenAI 格式"""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return str(content)

    text_parts = []
    image_parts = []

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type", "")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "image":
            source = block.get("source", {})
            media_type = source.get("media_type", "image/png")
            data = source.get("data", "")
            image_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{data}"}
            })
        elif block_type == "tool_result":
            tool_use_id = block.get("tool_use_id", "")
            tool_content = block.get("content", "")
            if isinstance(tool_content, list):
                tool_text = "".join(b.get("text", "") for b in tool_content if b.get("type") == "text")
            else:
                tool_text = str(tool_content)
            text_parts.append(f"[Tool Result id={tool_use_id}]: {tool_text}")

    if image_parts and not text_parts:
        return image_parts
    if image_parts and text_parts:
        result = [{"type": "text", "text": "\n".join(text_parts)}]
        result.extend(image_parts)
        return result
    return "\n".join(text_parts)


def _convert_anthropic_assistant_content_to_openai(content):
    """转换 Anthropic assistant content 为 OpenAI 格式"""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return str(content)

    text_parts = []
    tool_calls = []

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type", "")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "tool_use":
            tool_id = block.get("id", "")
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})
            tool_calls.append({
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_input, ensure_ascii=False)
                }
            })

    if tool_calls:
        result = ""
        if text_parts:
            result = "\n".join(text_parts)
        return result if result else ""

    return "\n".join(text_parts)


def anthropic_to_openai_request(anthropic_data):
    """将 Anthropic Messages API 请求转换为 OpenAI Chat Completions 请求"""
    anthropic_model = anthropic_data.get("model", llm_model_name)
    system_prompt = anthropic_data.get("system")
    anthropic_messages = anthropic_data.get("messages", [])
    max_tokens = anthropic_data.get("max_tokens", 4096)
    temperature = anthropic_data.get("temperature", 0.7)
    stream = anthropic_data.get("stream", False)
    stop_sequences = anthropic_data.get("stop_sequences")
    top_p = anthropic_data.get("top_p")
    top_k = anthropic_data.get("top_k")

    openai_messages = anthropic_to_openai_messages(anthropic_messages, system_prompt)

    openai_request = {
        "model": llm_model_name,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }

    if stop_sequences:
        openai_request["stop"] = stop_sequences
    if top_p is not None:
        openai_request["top_p"] = top_p

    return openai_request, anthropic_model


def openai_to_anthropic_response(openai_response, anthropic_model, request_id=None):
    """将 OpenAI Chat Completions 响应转换为 Anthropic Messages 响应"""
    msg_id = request_id or f"msg_{uuid.uuid4().hex[:12]}"
    created = openai_response.get("created", int(time.time()))

    choice = openai_response.get("choices", [{}])[0]
    message = choice.get("message", {})
    content_text = message.get("content", "")
    logger.info(f"raw_content_from_upstream: {content_text}")
    logger.info(f"raw_content_type: {type(content_text)}")
    logger.info(f"raw_content_repr: {repr(content_text)}")
    finish_reason = choice.get("finish_reason", "stop")
    stop_reason = FINISH_REASON_MAP.get(finish_reason, "end_turn")

    usage = openai_response.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    content_blocks = []
    if content_text:
        content_blocks.append({"type": "text", "text": content_text})

    tool_calls = message.get("tool_calls", [])
    for tc in tool_calls:
        func = tc.get("function", {})
        tool_input = {}
        try:
            tool_input = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            tool_input = {"arguments": func.get("arguments", "")}
        content_blocks.append({
            "type": "tool_use",
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "input": tool_input
        })

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "model": anthropic_model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
    }


def generate_anthropic_sse(openai_stream_response, anthropic_model):
    """将 OpenAI SSE 流式响应转换为 Anthropic SSE 流式响应"""
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    timestamp = int(time.time())
    content_index = 0
    content_block_started = False
    input_tokens = 0
    output_tokens = 0
    accumulated_text = ""
    finish_reason = None

    # message_start
    start_event = {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": anthropic_model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}
        }
    }
    yield (f"event: message_start\ndata: {json.dumps(start_event, ensure_ascii=False)}\n\n").encode('utf-8')

    for line in openai_stream_response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue

        data_str = line[6:]
        if data_str.strip() == "[DONE]":
            break

        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        usage = chunk.get("usage")
        if usage:
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            continue

        choices = chunk.get("choices", [])
        if not choices:
            continue

        choice = choices[0]
        delta = choice.get("delta", {})
        chunk_finish = choice.get("finish_reason")

        if delta.get("role") and not content_block_started:
            pass
            continue

        text = delta.get("content", "")
        if text:
            logger.debug(f"SSE text chunk: {repr(text)}")
            if not content_block_started:
                content_block_started = True
                # content_block_start
                cbs_event = {
                    "type": "content_block_start",
                    "index": content_index,
                    "content_block": {"type": "text", "text": ""}
                }
                yield (f"event: content_block_start\ndata: {json.dumps(cbs_event, ensure_ascii=False)}\n\n").encode('utf-8')

            accumulated_text += text
            # content_block_delta
            cbd_event = {
                "type": "content_block_delta",
                "index": content_index,
                "delta": {"type": "text_delta", "text": text}
            }
            yield (f"event: content_block_delta\ndata: {json.dumps(cbd_event, ensure_ascii=False)}\n\n").encode('utf-8')

        if chunk_finish:
            finish_reason = chunk_finish

    if content_block_started:
        # content_block_stop
        cbs_end = {
            "type": "content_block_stop",
            "index": content_index
        }
        yield (f"event: content_block_stop\ndata: {json.dumps(cbs_end)}\n\n").encode('utf-8')

    anthropic_stop = FINISH_REASON_MAP.get(finish_reason, "end_turn") if finish_reason else "end_turn"

    # message_delta
    msg_delta = {
        "type": "message_delta",
        "delta": {
            "stop_reason": anthropic_stop,
            "stop_sequence": None
        },
        "usage": {"output_tokens": output_tokens}
    }
    yield (f"event: message_delta\ndata: {json.dumps(msg_delta)}\n\n").encode('utf-8')

    # message_stop
    msg_stop = {"type": "message_stop"}
    yield (f"event: message_stop\ndata: {json.dumps(msg_stop)}\n\n").encode('utf-8')


def verify_api_key(auth_header):
    """验证 Anthropic x-api-key 头"""
    if not llm_api_key:
        return True
    if not auth_header:
        return False
    return auth_header == llm_api_key


def extract_api_key():
    """从请求头中提取 API key，支持 x-api-key 和 Authorization: Bearer 两种方式"""
    # 优先检查 x-api-key
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return api_key

    # 检查 Authorization: Bearer
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]  # 去掉 "Bearer " 前缀

    return ""

def require_auth(f):
    def decorated(*args, **kwargs):
        api_key = extract_api_key()

        if not verify_api_key(api_key):
            logger.warning(
                f"Invalid API key attempt. Expected: {llm_api_key[:20]}..., Got: {api_key[:20] if api_key else 'None'}...")
            return make_json_response(
                {
                    "type": "error",
                    "error": {
                        "type": "authentication_error",
                        "message": "invalid api key"
                    }
                },
                status=401
            )
        return f(*args, **kwargs)

    decorated.__name__ = f.__name__
    return decorated


@app.route('/v1/messages', methods=['POST'])
@require_auth
def create_message():
    start_time = time.time()
    logger.debug(f"Request headers: {dict(request.headers)}")
    data = request.json
    logger.debug(f"Request body: {json.dumps(data, ensure_ascii=False)[:500]}")
    if not data:
        return make_json_response(
            {
                "type": "error",
                "error": {"type": "invalid_request_error", "message": "Request body is required"}
            },
            status=400
        )

    messages = data.get("messages", [])
    if not messages or not isinstance(messages, list):
        return make_json_response(
            {
                "type": "error",
                "error": {"type": "invalid_request_error", "message": "messages must be a non-empty list"}
            },
            status=400
        )

    stream = data.get("stream", False)

    try:
        openai_request, anthropic_model = anthropic_to_openai_request(data)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_api_key}"
        }

        logger.info(f"Forwarding to {llm_api_uri}/chat/completions, model={llm_model_name}, stream={stream}")

        if stream:
            logger.debug("stream request")
            openai_request["stream"] = True
            upstream_response = requests.post(
                f"{llm_api_uri}/chat/completions",
                headers=headers,
                json=openai_request,
                timeout=300,
                stream=True,
                verify=False
            )

            if upstream_response.status_code != 200:
                logger.error(f"Upstream error: {upstream_response.status_code} - {upstream_response.text}")
                return make_json_response(
                    {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": f"Upstream API returned {upstream_response.status_code}"
                        }
                    },
                    status=502
                )

            def generate():
                yield from generate_anthropic_sse(upstream_response, anthropic_model)

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "x-request-id": f"msg_{uuid.uuid4().hex[:12]}"
                }
            )
        else:
            logger.debug("not_stream_request")
            upstream_response = requests.post(
                f"{llm_api_uri}/chat/completions",
                headers=headers,
                json=openai_request,
                timeout=300,
                verify=False
            )

            if upstream_response.status_code != 200:
                logger.error(f"Upstream error: {upstream_response.status_code} - {upstream_response.text}")
                return make_json_response(
                    {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": f"Upstream API returned {upstream_response.status_code}"
                        }
                    },
                    status=502
                )

            openai_response = upstream_response.json()
            anthropic_response = openai_to_anthropic_response(openai_response, anthropic_model)

            processing_time = time.time() - start_time
            logger.info(f"Request processed in {processing_time:.2f}s, stream=False")

            return make_json_response(
                anthropic_response,
                headers={"x-request-id": anthropic_response["id"]}
            )

    except requests.exceptions.Timeout:
        logger.error("Upstream API timeout")
        return make_json_response(
            {
                "type": "error",
                "error": {"type": "timeout_error", "message": "Upstream API timeout"}
            },
            status=504
        )
    except Exception as e:
        logger.exception("Unexpected error")
        return make_json_response(
            {
                "type": "error",
                "error": {"type": "internal_error", "message": str(e)}
            },
            status=500
        )


@app.route('/v1/models', methods=['GET'])
@require_auth
def list_models():
    """返回模型列表（Anthropic 格式）"""
    models_data = {
        "data": [
            {
                "id": llm_model_name,
                "type": "model",
                "display_name": llm_model_name,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ],
        "has_more": False,
        "first_id": llm_model_name,
        "last_id": llm_model_name
    }
    return make_json_response(models_data)


@app.route('/v1/models/<model_id>', methods=['GET'])
@require_auth
def get_model(model_id):
    """获取单个模型信息"""
    return make_json_response({
        "id": model_id,
        "type": "model",
        "display_name": model_id,
        "created_at": "2024-01-01T00:00:00Z"
    })


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "adapter": "openai-to-anthropic",
        "upstream_model": llm_model_name,
        "upstream_uri": llm_api_uri,
        "timestamp": int(time.time())
    })


@app.route('/', methods=['GET'])
def welcome():
    return make_json_response({
        "status": 200,
        "msg": "LLM API Adapter - OpenAI to Anthropic API converter",
        "upstream_model": llm_model_name,
        "upstream_uri": llm_api_uri,
        "anthropic_api_version": ANTHROPIC_VERSION,
        "endpoints": {
            "messages": "/v1/messages",
            "models": "/v1/models",
            "health": "/health"
        },
        "timestamp": int(time.time())
    })

@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception("Unhandled exception")
    return make_json_response(
        {
            "type": "error",
            "error": {"type": "internal_error", "message": str(e)}
        },
        status=500
    )

if __name__ == '__main__':
    logger.info("init")
    port = 16001
    if len(__import__('sys').argv) > 1:
        try:
            port = int(__import__('sys').argv[1])
        except ValueError:
            pass

    # _base_dir = os.path.dirname(os.path.abspath(__file__))
    # _cert_dir = os.path.join(_base_dir, '../../common/cert')
    # cert_file = os.path.join(_cert_dir, 'srv.crt')
    # key_file = os.path.join(_cert_dir, 'srv.key')
    # logger.info(f"Cert: {cert_file}, Key: {key_file}")
    # app.run(host='0.0.0.0', port=port, threaded=True, ssl_context=(cert_file, key_file))
    logger.info(f"LLM API Adapter, listening_port={port}, upstream={llm_api_uri}, model={llm_model_name}")

    app.run(host='0.0.0.0', port=port, threaded=True)
