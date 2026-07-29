#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聊天处理器 — 对标 Go 版本 internal/handler/chat.go
SSE 流式返回，支持 FAQ 匹配和知识库检索。
"""
import json
import logging
import time
from datetime import datetime
from flask import Response, request, jsonify, stream_with_context

from apps.csm.handler.auth import get_auth_uid
from apps.csm.chat_agent import LLMClient
from apps.csm.store import DEFAULT_CHAT_PROMPT

logger = logging.getLogger(__name__)

WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"]


class ChatHandler:
    """聊天处理器"""

    def __init__(self, cfg: dict, kb_manager, session_mgr, store):
        self.cfg = cfg
        self.kb_mgr = kb_manager
        self.session_mgr = session_mgr
        self.store = store
        self._llm_client = None

    def _get_llm_client(self) -> LLMClient:
        if not self._llm_client:
            api = self.cfg["api"]
            llm = self.cfg.get("llm", {})
            self._llm_client = LLMClient(
                api["llm_api_uri"],
                api["llm_api_key"],
                api["llm_model_name"],
                temperature=llm.get("temperature", 0.7),
                top_p=llm.get("top_p", 0.9),
                max_tokens=llm.get("max_tokens", 2048),
            )
        return self._llm_client

    def _get_prompt_template(self) -> str:
        """从数据库获取提示词模板"""
        prompt = self.store.get_prompt("chat_msg")
        if prompt:
            return prompt
        return DEFAULT_CHAT_PROMPT

    def chat(self):
        """处理聊天请求，SSE 流式返回"""
        uid = get_auth_uid()
        msg = request.form.get("msg", "").strip()
        session_id = request.form.get("session_id", "")
        if not session_id:
            session_id = "default"

        if not msg:
            return jsonify({"error": "消息不能为空"}), 400

        # 设置 SSE 头
        def generate():
            # 获取历史
            history = self.session_mgr.get_history(uid, session_id)
            history_str = self.session_mgr.format_history(history)

            # 获取知识库上下文
            cur_date = datetime.now().strftime("%Y-%m-%d")
            cur_week = WEEKDAYS[datetime.now().weekday()]
            context_str = self.kb_mgr.search_all_kbs(
                msg, uid,
                self.cfg["kb"].get("top_k", 3),
                self.cfg["kb"].get("score_threshold", 0.1),
            )

            # 构建提示词
            prompt_template = self._get_prompt_template()
            system_prompt = prompt_template.replace("{context}", context_str or "")
            system_prompt = system_prompt.replace("{history}", history_str)
            system_prompt = system_prompt.replace("{question}", msg)
            system_prompt = system_prompt.replace("{cur_date}", cur_date)
            system_prompt = system_prompt.replace("{cur_week}", cur_week)

            logger.info("chat: uid=%s, session=%s, query=%s, contextLen=%d",
                        uid, session_id, msg[:50], len(context_str))

            # 保存用户消息
            self.session_mgr.add_message(uid, session_id, "user", msg)

            # 发送初始事件
            yield "data: \n\n"

            # 调用 LLM 流式
            full_response = ""
            try:
                llm = self._get_llm_client()
                for chunk in llm.chat_stream(system_prompt, msg):
                    full_response += chunk
                    yield f"data: {chunk}\n\n"
            except Exception as e:
                logger.error("LLM 错误: %s", e)
                yield f"data: [错误] {e}\n\n"

            # 发送结束标记
            yield "data: [DONE]\n\n"

            # 保存助手回复
            if full_response:
                self.session_mgr.add_message(uid, session_id, "assistant", full_response)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def clear(self):
        """清空会话"""
        uid = get_auth_uid()
        session_id = request.form.get("session_id", "")
        if not session_id:
            session_id = "default"

        self.session_mgr.clear(uid, session_id)
        return jsonify({"status": "ok"})