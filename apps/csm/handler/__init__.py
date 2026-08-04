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
from apps.csm.engine import WorkflowEngine, FastTextPredictor
from apps.csm.csm_engine import CsmEngine


class Handler:
    """聚合所有处理器"""

    def __init__(self, cfg: dict, kb_manager, session_mgr, store,
                 embedding_client=None, llm_client=None):
        # FaqHandler 先创建，注入给 ChatHandler（对标 Go）
        faq_handler = FaqHandler(store, embedding_client)

        # 工作流引擎（对标 Go: engine.NewEngine）
        ft_predictor = FastTextPredictor()
        workflow_engine = WorkflowEngine(
            cfg, kb_manager, store,
            emb_client=embedding_client,
            ft_predictor=ft_predictor,
        )

        # CSM 硬编码引擎（对标 Go: engine.csm.go，共享 fastText 预测器）
        csm_engine = CsmEngine(
            cfg, kb_manager, store,
            emb_client=embedding_client,
            ft_predictor=ft_predictor,
        )

        self.Page = PageHandler(cfg)
        self.Chat = ChatHandler(cfg, kb_manager, session_mgr, store, faq_handler, workflow_engine, csm_engine)
        self.Vdb = VdbHandler(cfg, kb_manager, store)
        self.Config = ConfigHandler(cfg, store, workflow_engine)
        self.Auth = AuthHandler(cfg, store)
        self.User = UserHandler(store)
        self.Agent = AgentHandler(store)
        self.Workflow = WorkflowHandler(store)
        self.Faq = faq_handler