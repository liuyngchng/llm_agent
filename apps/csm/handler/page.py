#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面处理器 — 对标 Go 版本 internal/handler/page.go
"""
import logging
from flask import render_template, request
from apps.csm.handler.auth import get_auth_uid, get_auth_role, get_token_str

logger = logging.getLogger(__name__)


class PageHandler:
    """页面处理器"""

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def index(self):
        """聊天主页面"""
        uid = get_auth_uid()
        role = get_auth_role()
        token = get_token_str()

        return render_template("csm_index.html",
            sys_name=self.cfg["sys"]["name"],
            uid=uid,
            role=role,
            token=token,
            app_source="csm",
            greeting=self.cfg["sys"].get("greeting", ""),
            arg1=self.cfg.get("arg1", ""),
            arg2=self.cfg.get("arg2", ""),
            arg3=self.cfg.get("arg3", ""),
        )

    def vdb_index(self):
        """知识库管理页面"""
        uid = get_auth_uid()
        role = get_auth_role()
        token = get_token_str()

        return render_template("vdb_index.html",
            sys_name=self.cfg["sys"]["name"],
            uid=uid,
            role=role,
            token=token,
            app_source="csm",
            vdb_status="",
        )

    def user_api_index(self):
        """API 用户管理页面"""
        uid = get_auth_uid()
        token = get_token_str()

        return render_template("user_api.html",
            sys_name=self.cfg["sys"]["name"],
            uid=uid,
            token=token,
        )

    def config_index(self):
        """系统配置页面"""
        uid = get_auth_uid()
        role = get_auth_role()
        token = get_token_str()

        return render_template("config.html",
            sys_name=self.cfg["sys"]["name"],
            uid=uid,
            role=role,
            token=token,
        )