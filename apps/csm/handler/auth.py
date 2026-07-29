#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证处理器 — 对标 Go 版本 internal/handler/auth.go
HMAC token 认证，支持登录/注销/中间件。
"""
import hashlib
import hmac
import base64
import json
import logging
import threading
import time
from flask import request, jsonify, redirect, session
from functools import wraps

logger = logging.getLogger(__name__)

# HMAC 签名密钥（生产环境应从配置读取）
TOKEN_SECRET = b"go_to_chat_secret_2026"
# token 有效期 2 小时
TOKEN_TTL = 2 * 3600


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def generate_token(user_name: str, role: int, expiry: int = None) -> str:
    """生成 HMAC 签名 token，格式: base64(user_name|role|expiry|hmac_signature)"""
    if expiry is None:
        expiry = int(time.time()) + TOKEN_TTL
    payload = f"{user_name}|{role}|{expiry}"
    sig = hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]
    full = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(full.encode()).decode()


def parse_token(token_str: str) -> dict:
    """解析并验证 token，返回 user dict 或 None"""
    try:
        data = base64.urlsafe_b64decode(token_str.encode()).decode()
        parts = data.split("|")
        if len(parts) != 4:
            return None

        user_name = parts[0]
        role = int(parts[1])
        expiry = int(parts[2])
        sig = parts[3]

        # 检查过期
        if time.time() > expiry:
            return None

        # 验证签名
        payload = f"{user_name}|{role}|{expiry}"
        expected_sig = hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None

        return {"user_name": user_name, "role": role}
    except Exception:
        return None


def extract_token() -> str:
    """从请求中提取 token：优先 URL 参数 t，其次 Authorization header"""
    t = request.args.get("t")
    if t:
        return t
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


class AuthHandler:
    """认证处理器"""

    def __init__(self, cfg: dict, store):
        self.cfg = cfg
        self.store = store
        self.online_agents = {}  # user_name -> login_time
        self._agents_lock = threading.Lock()

    def login_page(self):
        """登录页面（对标 Go LoginPage）"""
        from flask import render_template
        return render_template("login.html",
            default_user="user0",
            default_pwd="user0",
            error_msg="",
        )

    def login(self):
        """处理登录请求"""
        data = request.get_json(silent=True) or request.form
        user_name = data.get("user_name", "").strip()
        user_pwd = data.get("user_pwd", "").strip()

        if not user_name or not user_pwd:
            return jsonify({"error": "用户名和密码不能为空"}), 400

        md5_pwd = _md5(user_pwd)
        user = self.store.get_user_by_login(user_name, md5_pwd)
        if not user:
            return jsonify({"error": "用户名或密码错误"}), 401

        expiry = int(time.time()) + TOKEN_TTL
        token = generate_token(user["user_name"], user["role"], expiry)

        # 如果是客服座席，加入在线列表
        if user["role"] == 2:  # RoleAgent
            with self._agents_lock:
                self.online_agents[user["user_name"]] = time.time()

        return jsonify({
            "status": "ok",
            "token": token,
            "user_name": user["user_name"],
            "role": user["role"],
        })

    def logout(self):
        """处理注销"""
        token_str = extract_token()
        if token_str:
            user = parse_token(token_str)
            if user:
                with self._agents_lock:
                    self.online_agents.pop(user["user_name"], None)
        return jsonify({"status": "ok"})

    def me(self):
        """返回当前登录用户信息"""
        token_str = extract_token()
        if not token_str:
            return jsonify({"error": "未登录"}), 401

        user = parse_token(token_str)
        if not user:
            return jsonify({"error": "token 无效或已过期"}), 401

        return jsonify({
            "user_name": user["user_name"],
            "role": user["role"],
        })

    def get_online_agents(self):
        """获取在线座席列表"""
        agents = []
        with self._agents_lock:
            now = time.time()
            expired = []
            for name, login_time in self.online_agents.items():
                if now - login_time > TOKEN_TTL:
                    expired.append(name)
                    continue
                user = self.store.get_user_by_name(name)
                note = user["note"] if user else ""
                agents.append({
                    "user_name": name,
                    "login_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(login_time)),
                    "note": note,
                })
            for name in expired:
                del self.online_agents[name]

        return jsonify({"agents": agents})

    # ============================================================
    # 中间件
    # ============================================================

    def require_auth(self, f):
        """认证中间件：验证 token"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            token_str = extract_token()
            if not token_str:
                return redirect("/login")

            user = parse_token(token_str)
            if not user:
                return redirect("/login")

            # 注入用户信息到 request context
            request._csm_user = user
            request._csm_token = token_str
            return f(*args, **kwargs)
        return wrapper

    def require_api_auth(self, f):
        """API 认证中间件：受 sys.api_auth 开关控制"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 始终尝试提取 token
            token_str = extract_token()
            if token_str:
                user = parse_token(token_str)
                if user:
                    request._csm_user = user
                    request._csm_token = token_str

            # 接口认证关闭时跳过
            if not self.cfg["sys"].get("api_auth", True):
                return f(*args, **kwargs)

            # 接口认证开启时，必须提供有效 token
            if not hasattr(request, "_csm_user") or not request._csm_user:
                return jsonify({"error": "未提供认证 token"}), 401

            return f(*args, **kwargs)
        return wrapper

    def require_admin(self, f):
        """管理员中间件"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = getattr(request, "_csm_user", None)
            if not user or user.get("role") != 1:  # RoleAdmin
                return jsonify({"error": "仅管理员可访问"}), 403
            return f(*args, **kwargs)
        return wrapper


def get_auth_uid() -> str:
    """从认证上下文中获取用户名"""
    user = getattr(request, "_csm_user", None)
    if user:
        return user.get("user_name", "default")
    return "default"


def get_auth_role() -> int:
    """从认证上下文中获取角色"""
    user = getattr(request, "_csm_user", None)
    if user:
        return user.get("role", 0)
    return 0


def get_token_str() -> str:
    """从 context 提取原始 token 字符串"""
    return getattr(request, "_csm_token", "")