#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聊天处理器 — 对标 Go 版本 internal/handler/chat.go
SSE 流式返回，支持 FAQ 匹配、知识库检索和工作流引擎。
"""
import json
import logging
import time
from datetime import datetime
from flask import Response, request, jsonify, stream_with_context

from apps.csm.handler.auth import get_auth_uid
from apps.csm.chat_agent import LLMClient
from apps.csm.store import DEFAULT_CHAT_PROMPT
from apps.csm.engine import (
    WorkflowEngine, classify_with_details, resolve_template,
    format_history, get_weekday_cn,
)

logger = logging.getLogger(__name__)


class ChatHandler:
    """聊天处理器（对标 Go internal/handler/chat.go）"""

    def __init__(self, cfg: dict, kb_manager, session_mgr, store,
                 faq_handler=None, workflow_engine: WorkflowEngine = None,
                 csm_engine=None):
        self.cfg = cfg
        self.kb_mgr = kb_manager
        self.session_mgr = session_mgr
        self.store = store
        self.faq_handler = faq_handler
        self.engine = workflow_engine
        self.csm_engine = csm_engine

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

    def _resolve_uid(self, data: dict) -> str:
        """根据 api_auth 开关决定使用哪个 UID（对标 Go resolveUID）"""
        api_auth = self.cfg["sys"].get("api_auth", True)
        if api_auth:
            return get_auth_uid()
        # API 认证关闭时，优先使用请求中的 uid
        req_uid = (data.get("uid") or "").strip()
        if req_uid:
            return req_uid
        return get_auth_uid()

    def chat_sync(self):
        """同步聊天接口 POST /api/chat/sync（对标 Go ChatHandler.ChatSync）"""
        data = request.get_json(silent=True) or {}
        msg = (data.get("msg") or "").strip()
        uid = self._resolve_uid(data)

        if not msg:
            return jsonify({"error": "消息不能为空"}), 400

        work_mode = self.cfg["sys"].get("work_mode", 0)
        if work_mode == 1:  # CSM
            return self._chat_sync_csm(uid, msg)
        elif work_mode == 2:  # Dynamic
            return self._chat_sync_dynamic(uid, msg)
        else:  # KB
            return self._chat_sync_kb(uid, msg)

    def _chat_sync_kb(self, uid: str, msg: str):
        """知识库问答模式同步版本"""
        history = self.session_mgr.get_history(uid)
        history_str = self.session_mgr.format_history(history)

        faq_threshold = self.cfg.get("faq", {}).get("match_threshold", 0.85)
        if self.faq_handler and self.faq_handler.get_faq_count() > 0:
            faq_answer, faq_score = self.faq_handler.match_faq(msg, faq_threshold)
            if faq_answer:
                self.session_mgr.add_message(uid, "user", msg)
                self.session_mgr.add_message(uid, "assistant", faq_answer)
                return jsonify({"answer": faq_answer, "source": "faq", "score": faq_score})

        cur_date = datetime.now().strftime("%Y-%m-%d")
        cur_week = get_weekday_cn(datetime.now().weekday())
        context_str = self.kb_mgr.search_all_kbs(
            msg, uid,
            self.cfg["kb"].get("top_k", 3),
            self.cfg["kb"].get("score_threshold", 0.1),
        )

        prompt_template = self._get_prompt_template()
        system_prompt = prompt_template.replace("{context}", context_str or "")
        system_prompt = system_prompt.replace("{history}", history_str)
        system_prompt = system_prompt.replace("{question}", msg)
        system_prompt = system_prompt.replace("{cur_date}", cur_date)
        system_prompt = system_prompt.replace("{cur_week}", cur_week)

        self.session_mgr.add_message(uid, "user", msg)
        try:
            answer = self._llm_client.chat(system_prompt, msg)
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            return jsonify({"error": f"LLM 调用失败: {e}"}), 500

        self.session_mgr.add_message(uid, "assistant", answer)
        return jsonify({"answer": answer, "source": "kb"})

    def _chat_sync_csm(self, uid: str, msg: str):
        """CSM 工作流同步版本"""
        history = self.session_mgr.get_history(uid)
        self.session_mgr.add_message(uid, "user", msg)

        full_output = ""
        try:
            events = self.csm_engine.execute_stream_csm(0, msg, uid, history)
            for evt in events:
                if evt.type == "chunk":
                    full_output += evt.content
                elif evt.type == "error":
                    raise Exception(evt.content)
                elif evt.type == "done":
                    break
        except Exception as e:
            logger.error("CSM 工作流执行失败: %s", e)
            return jsonify({"error": f"工作流执行失败: {e}"}), 500

        self.session_mgr.add_message(uid, "assistant", full_output)
        return jsonify({"answer": full_output, "source": "csm"})

    def _chat_sync_dynamic(self, uid: str, msg: str):
        """动态工作流同步版本"""
        history = self.session_mgr.get_history(uid)
        workflow_id = self.cfg["sys"].get("default_workflow_id", 0)
        self.session_mgr.add_message(uid, "user", msg)

        workflow = self.store.get_workflow(workflow_id) if workflow_id > 0 else None
        if not workflow:
            return jsonify({"error": f"工作流 {workflow_id} 不存在"}), 500

        full_output = ""
        try:
            events = self.engine.execute_stream(workflow, history, uid, msg)
            for evt in events:
                if evt.type == "chunk":
                    full_output += evt.content
                elif evt.type == "error":
                    raise Exception(evt.content)
                elif evt.type == "done":
                    break
        except Exception as e:
            logger.error("工作流执行失败: %s", e)
            return jsonify({"error": f"工作流执行失败: {e}"}), 500

        self.session_mgr.add_message(uid, "assistant", full_output)
        return jsonify({"answer": full_output, "source": "dynamic"})

    def chat(self):
        """处理聊天请求，SSE 流式返回（对标 Go ChatHandler.Chat）"""
        data = request.get_json(silent=True) or {}
        msg = (data.get("msg") or "").strip()
        uid = self._resolve_uid(data)

        if not msg:
            return jsonify({"error": "消息不能为空"}), 400

        # 根据系统配置的工作模式决定聊天路径
        work_mode = self.cfg["sys"].get("work_mode", 0)
        if work_mode == 1:  # CSM
            return self._chat_with_csm(uid, msg)
        elif work_mode == 2:  # Dynamic
            return self._chat_with_dynamic(uid, msg)
        else:  # KB
            return self._chat_with_kb(uid, msg)

    def _chat_with_kb(self, uid: str, msg: str):
        """知识库问答模式 — FAQ 匹配 → 知识库检索 → LLM 对话（对标 Go chatWithKB）"""
        history = self.session_mgr.get_history(uid)
        history_str = self.session_mgr.format_history(history)

        faq_threshold = self.cfg.get("faq", {}).get("match_threshold", 0.85)
        if self.faq_handler and self.faq_handler.get_faq_count() > 0:
            faq_answer, faq_score = self.faq_handler.match_faq(msg, faq_threshold)
            if faq_answer:
                logger.info("faq-matched: uid=%s, query=%s, score=%.4f",
                            uid, msg[:50], faq_score)

                def generate_faq():
                    self.session_mgr.add_message(uid, "user", msg)
                    yield "data: \n\n"
                    yield f"data: {faq_answer}\n\n"
                    yield "data: [DONE]\n\n"
                    self.session_mgr.add_message(uid, "assistant", faq_answer)

                return Response(
                    stream_with_context(generate_faq()),
                    mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

        cur_date = datetime.now().strftime("%Y-%m-%d")
        cur_week = get_weekday_cn(datetime.now().weekday())
        context_str = self.kb_mgr.search_all_kbs(
            msg, uid,
            self.cfg["kb"].get("top_k", 3),
            self.cfg["kb"].get("score_threshold", 0.1),
        )

        prompt_template = self._get_prompt_template()
        system_prompt = prompt_template.replace("{context}", context_str or "")
        system_prompt = system_prompt.replace("{history}", history_str)
        system_prompt = system_prompt.replace("{question}", msg)
        system_prompt = system_prompt.replace("{cur_date}", cur_date)
        system_prompt = system_prompt.replace("{cur_week}", cur_week)

        logger.info("chat: uid=%s, query=%s, contextLen=%d",
                    uid, msg[:50], len(context_str))

        self.session_mgr.add_message(uid, "user", msg)

        def generate():
            yield "data: \n\n"

            full_response = ""
            try:
                for chunk in self._llm_client.chat_stream(system_prompt, msg):
                    full_response += chunk
                    yield f"data: {chunk}\n\n"
            except Exception as e:
                logger.error("LLM 错误: %s", e)
                yield f"data: [错误] {e}\n\n"

            yield "data: [DONE]\n\n"

            if full_response:
                self.session_mgr.add_message(uid, "assistant", full_response)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def _chat_with_csm(self, uid: str, msg: str):
        """CSM 硬编码工作流模式（对标 Go chatWithCSMWorkflow）"""
        history = self.session_mgr.get_history(uid)

        logger.info("workflow-chat-csm: uid=%s, query=%s",
                    uid, msg[:50])

        self.session_mgr.add_message(uid, "user", msg)

        def generate():
            yield "data: \n\n"

            full_output = ""
            try:
                events = self.csm_engine.execute_stream_csm(0, msg, uid, history)
                for evt in events:
                    if evt.type == "progress":
                        yield f"data: [步骤 {evt.step}/{evt.total}] {evt.agent}\n\n"
                    elif evt.type == "chunk":
                        full_output += evt.content
                        yield f"data: {evt.content}\n\n"
                    elif evt.type == "error":
                        yield f"data: [错误] {evt.content}\n\n"
                    elif evt.type == "done":
                        break
            except Exception as e:
                logger.error("workflow 执行错误: %s", e)
                yield f"data: [错误] {e}\n\n"

            yield "data: [DONE]\n\n"

            if full_output:
                self.session_mgr.add_message(uid, "assistant", full_output)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def _chat_with_dynamic(self, uid: str, msg: str):
        """动态加载数据库工作流配置模式（对标 Go chatWithDynamicWorkflow）"""
        history = self.session_mgr.get_history(uid)

        workflow_id = self.cfg["sys"].get("default_workflow_id", 0)
        logger.info("workflow-chat-dynamic: uid=%s, workflow=%d, query=%s",
                    uid, workflow_id, msg[:50])

        self.session_mgr.add_message(uid, "user", msg)

        def generate():
            yield "data: \n\n"

            full_output = ""
            try:
                workflow = self.store.get_workflow(workflow_id) if workflow_id > 0 else None
                if not workflow:
                    yield f"data: [错误] 工作流 {workflow_id} 不存在\n\n"
                else:
                    events = self.engine.execute_stream(workflow, history, uid, msg)
                    for evt in events:
                        if evt.type == "progress":
                            yield f"data: [步骤 {evt.step}/{evt.total}] {evt.agent}\n\n"
                        elif evt.type == "chunk":
                            full_output += evt.content
                            yield f"data: {evt.content}\n\n"
                        elif evt.type == "error":
                            yield f"data: [错误] {evt.content}\n\n"
                        elif evt.type == "done":
                            break
            except Exception as e:
                logger.error("workflow 执行错误: %s", e)
                yield f"data: [错误] {e}\n\n"

            yield "data: [DONE]\n\n"

            if full_output:
                self.session_mgr.add_message(uid, "assistant", full_output)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def history(self):
        """获取当前用户的历史消息 GET /api/chat/history"""
        uid = get_auth_uid()
        history = self.session_mgr.get_history(uid)
        return jsonify({"data": history})

    def clear(self):
        """清空会话（对标 Go ChatHandler.Clear）"""
        uid = get_auth_uid()
        self.session_mgr.clear(uid)
        return jsonify({"status": "ok"})

    # ============================================================
    # 意图分类测试接口（对标 Go TestClassifier）
    # ============================================================

    def test_classifier(self):
        """意图分类测试接口 POST /api/classifier/test"""
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        workflow_id = data.get("workflow_id", 0)

        if not text:
            return jsonify({"error": "参数错误: text 不能为空"}), 400
        if workflow_id <= 0:
            return jsonify({"error": "workflow_id 不能为空"}), 400

        workflow = self.store.get_workflow(workflow_id)
        if not workflow:
            return jsonify({"error": "工作流不存在"}), 404

        classifier_cfg = workflow.get("classifier")
        if not classifier_cfg or not classifier_cfg.get("categories"):
            return jsonify({"error": "该工作流没有配置意图分类器"}), 400

        # 执行分类
        emb_client = self.engine.emb_client if self.engine else None
        ft_predictor = self.engine.ft_predictor if self.engine else None

        tiers, final = classify_with_details(
            classifier_cfg, text,
            self._llm_client, emb_client, ft_predictor,
        )

        total_ms = sum(t.elapsed for t in tiers)

        return jsonify({
            "tiers": [t.to_dict() for t in tiers],
            "final": final,
            "total_ms": total_ms,
        })
