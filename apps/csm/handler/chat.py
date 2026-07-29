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
    """聊天处理器（对标 Go internal/handler/chat.go）"""

    def __init__(self, cfg: dict, kb_manager, session_mgr, store, faq_handler=None):
        self.cfg = cfg
        self.kb_mgr = kb_manager
        self.session_mgr = session_mgr
        self.store = store
        self.faq_handler = faq_handler

        # 即刻创建 LLM 客户端（对标 Go：NewChatHandler 中 llmClient := llm.New(...)）
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

    def _get_prompt_template(self) -> str:
        """从数据库获取提示词模板（对标 Go getPromptTemplate）"""
        prompt = self.store.get_prompt("chat_msg")
        if prompt:
            return prompt
        return DEFAULT_CHAT_PROMPT

    def chat(self):
        """处理聊天请求，SSE 流式返回（对标 Go ChatHandler.Chat）"""
        # JSON 请求体解析（对标 Go c.ShouldBindJSON(&req)）
        data = request.get_json(silent=True) or {}
        msg = (data.get("msg") or "").strip()
        session_id = data.get("session_id") or "default"
        workflow_id = data.get("workflow_id", 0)
        uid = get_auth_uid()

        if not msg:
            return jsonify({"error": "消息不能为空"}), 400

        # 如果指定了 workflow_id，走工作流引擎
        if workflow_id > 0:
            return self._chat_with_workflow(uid, session_id, workflow_id, msg)

        # 获取历史
        history = self.session_mgr.get_history(uid, session_id)
        history_str = self.session_mgr.format_history(history)

        # FAQ 匹配（对标 Go chat.go 中的 faq 匹配逻辑）
        faq_threshold = self.cfg.get("faq", {}).get("match_threshold", 0.85)
        if self.faq_handler and self.faq_handler.get_faq_count() > 0:
            faq_answer, faq_score = self.faq_handler.match_faq(msg, faq_threshold)
            if faq_answer:
                logger.info("faq-matched: uid=%s, query=%s, score=%.4f",
                            uid, msg[:50], faq_score)

                def generate_faq():
                    self.session_mgr.add_message(uid, session_id, "user", msg)
                    yield "data: \n\n"
                    yield f"data: {faq_answer}\n\n"
                    yield "data: [DONE]\n\n"
                    self.session_mgr.add_message(uid, session_id, "assistant", faq_answer)

                return Response(
                    stream_with_context(generate_faq()),
                    mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

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

        def generate():
            # 发送初始事件（对标 Go: fmt.Fprintf(c.Writer, "data: \n\n")）
            yield "data: \n\n"

            # 调用 LLM 流式
            full_response = ""
            try:
                for chunk in self._llm_client.chat_stream(system_prompt, msg):
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

    def _chat_with_workflow(self, uid: str, session_id: str, workflow_id: int, msg: str):
        """工作流引擎模式（对标 Go chatWithWorkflow）"""
        logger.warning("workflow-chat 暂未完整实现: uid=%s, session=%s, workflow=%d, query=%s",
                       uid, session_id, workflow_id, msg[:50])

        # 获取历史
        history = self.session_mgr.get_history(uid, session_id)
        history_str = self.session_mgr.format_history(history)

        # 保存用户消息
        self.session_mgr.add_message(uid, session_id, "user", msg)

        def generate():
            yield "data: \n\n"
            yield "data: [提示] 工作流引擎功能暂未实现，请使用默认聊天模式\n\n"
            yield "data: [DONE]\n\n"

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
        """清空会话（对标 Go ChatHandler.Clear，JSON 请求体）"""
        data = request.get_json(silent=True) or {}
        uid = get_auth_uid()
        session_id = data.get("session_id") or "default"

        self.session_mgr.clear(uid, session_id)
        return jsonify({"status": "ok"})
