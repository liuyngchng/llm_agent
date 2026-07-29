#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handler 包 — 对标 Go 版本 internal/handler/handler.go
聚合所有处理器。
"""
from apps.csm.handler.auth import AuthHandler
from apps.csm.handler.page import PageHandler
from apps.csm.handler.chat import ChatHandler
from apps.csm.handler.vdb import VdbHandler
from apps.csm.handler.config import ConfigHandler
from apps.csm.handler.user import UserHandler
from apps.csm.handler.agent import AgentHandler
from apps.csm.handler.workflow import WorkflowHandler
from apps.csm.handler.faq import FaqHandler


class Handler:
    """聚合所有处理器"""

    def __init__(self, cfg: dict, kb_manager, session_mgr, store,
                 embedding_client=None, llm_client=None):
        # FaqHandler 先创建，注入给 ChatHandler（对标 Go）
        faq_handler = FaqHandler(store, embedding_client)

        self.Page = PageHandler(cfg)
        self.Chat = ChatHandler(cfg, kb_manager, session_mgr, store, faq_handler)
        self.Vdb = VdbHandler(cfg, kb_manager, store)
        self.Config = ConfigHandler(cfg, store)
        self.Auth = AuthHandler(cfg, store)
        self.User = UserHandler(store)
        self.Agent = AgentHandler(store)
        self.Workflow = WorkflowHandler(store)
        self.Faq = faq_handler