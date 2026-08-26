#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证处理器 — 对标 Go 版本 internal/handler/auth.go
HMAC token 认证，支持登录/注销/中间件。
安全升级：bcrypt 密码、全 HMAC 签名、token 黑名单、登录限流、httpOnly Cookie。
"""
import hmac
import hashlib
import base64
import logging
import threading
import time
from datetime import datetime
from flask import request, jsonify, redirect
from functools import wraps

from apps.csm.crypto import verify_password, validate_password

logger = logging.getLogger(__name__)

# HMAC 签名密钥（生产环境应从配置读取）
TOKEN_SECRET = b"go_to_chat_secret_2026"
# token 有效期 2 小时
TOKEN_TTL = 2 * 3600

# Cookie 名称
COOKIE_AUTH_TOKEN = "auth_token"

# 登录限流配置
LOGIN_MAX_FAILURES = 5               # IP 最多连续失败次数
LOGIN_LOCK_DURATION = 15 * 60        # 锁定时长（秒）
LOGIN_FAILURES_CLEANUP = 15 * 60     # 过期失败记录清理间隔（秒）


def _init_secret(token_secret: str):
    """初始化 token 签名密钥（集群模式下在启动时调用一次）"""
    global TOKEN_SECRET
    if token_secret:
        TOKEN_SECRET = token_secret.encode()


def generate_token(user_name: str, role: int, expiry: int = None) -> str:
    """生成 HMAC 签名 token，格式: base64(user_name|role|expiry|full_hmac_signature)"""
    if expiry is None:
        expiry = int(time.time()) + TOKEN_TTL
    payload = f"{user_name}|{role}|{expiry}"
    sig = hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    full = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(full.encode()).decode()


def parse_token(token_str: str) -> dict:
    """解析并验证 token，返回 user dict 或 None"""
    if not token_str:
        return None

    # 检查 token 是否在黑名单中（已注销）
    if token_str in _token_blacklist:
        return None

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
        expected_sig = hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        return {"user_name": user_name, "role": role}
    except Exception:
        return None


def extract_token() -> str:
    """从请求中提取 token：优先 Cookie，其次 URL 参数 t，最后 Authorization header"""
    # Cookie（浏览器用户）
    token = request.cookies.get(COOKIE_AUTH_TOKEN)
    if token:
        return token
    # URL 参数
    t = request.args.get("t")
    if t:
        return t
    # Authorization header（API 用户 / 第三方调用）
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


# ============================================================
# Token 黑名单（内存，后台定时清理）
# ============================================================

_token_blacklist = {}  # signature -> expiry (timestamp)
_blacklist_lock = threading.Lock()
_cleanup_started = False
_cleanup_lock = threading.Lock()


def _blacklist_token(token_str: str):
    """将 token 的签名加入黑名单，使其立即失效"""
    try:
        data = base64.urlsafe_b64decode(token_str.encode()).decode()
        parts = data.split("|")
        if len(parts) == 4:
            expiry = int(parts[2])
            with _blacklist_lock:
                _token_blacklist[parts[3]] = expiry
            _ensure_cleanup_started()
    except Exception:
        pass


def _ensure_cleanup_started():
    global _cleanup_started
    with _cleanup_lock:
        if not _cleanup_started:
            _cleanup_started = True
            t = threading.Thread(target=_cleanup_loop, daemon=True)
            t.start()


def _cleanup_loop():
    """后台清理过期的黑名单条目"""
    while True:
        time.sleep(10 * 60)  # 每 10 分钟
        now = time.time()
        with _blacklist_lock:
            expired = [k for k, v in _token_blacklist.items() if now > v]
            for k in expired:
                del _token_blacklist[k]


# ============================================================
# 登录限流（IP 级别）
# ============================================================

_login_failures = {}  # IP -> {"count": int, "locked_until": float}
_login_failures_lock = threading.Lock()
_login_cleanup_started = False
_login_cleanup_lock = threading.Lock()


def _client_ip() -> str:
    """从请求中提取客户端 IP"""
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.remote_addr or "unknown"


def _is_login_locked(ip: str) -> bool:
    with _login_failures_lock:
        rec = _login_failures.get(ip)
        if not rec:
            return False
        return rec["count"] >= LOGIN_MAX_FAILURES and time.time() < rec["locked_until"]


def _record_login_failure(ip: str):
    with _login_failures_lock:
        rec = _login_failures.get(ip)
        if not rec:
            rec = {"count": 0, "locked_until": 0}
            _login_failures[ip] = rec
        rec["count"] += 1
        if rec["count"] >= LOGIN_MAX_FAILURES:
            rec["locked_until"] = time.time() + LOGIN_LOCK_DURATION
    _ensure_login_cleanup_started()


def _clear_login_failures(ip: str):
    with _login_failures_lock:
        _login_failures.pop(ip, None)


def _ensure_login_cleanup_started():
    global _login_cleanup_started
    with _login_cleanup_lock:
        if not _login_cleanup_started:
            _login_cleanup_started = True
            t = threading.Thread(target=_login_cleanup_loop, daemon=True)
            t.start()


def _login_cleanup_loop():
    while True:
        time.sleep(LOGIN_FAILURES_CLEANUP)
        now = time.time()
        with _login_failures_lock:
            expired = [
                k for k, v in _login_failures.items()
                if now > v["locked_until"] and v["count"] >= LOGIN_MAX_FAILURES
            ]
            for k in expired:
                del _login_failures[k]


# ============================================================
# Cookie 辅助函数
# ============================================================

def _set_auth_cookie(response, token: str, max_age: int):
    """设置 httpOnly + Secure(仅HTTPS) + SameSite=Strict 的认证 Cookie"""
    secure = request.headers.get("X-Forwarded-Proto") == "https" \
        or request.headers.get("X-Forwarded-Scheme") == "https" \
        or request.scheme == "https"
    response.set_cookie(
        COOKIE_AUTH_TOKEN,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/",
    )


def _clear_auth_cookie(response):
    """清除认证 Cookie"""
    response.delete_cookie(COOKIE_AUTH_TOKEN, path="/")


# ============================================================
# AuthHandler
# ============================================================

class AuthHandler:
    """认证处理器"""

    def __init__(self, cfg: dict, store):
        self.cfg = cfg
        self.store = store
        self.online_agents = {}  # user_name -> login_time
        self._agents_lock = threading.Lock()

        # 初始化 HMAC 密钥
        token_secret = cfg.get("server", {}).get("token_secret", "")
        if token_secret:
            _init_secret(token_secret)

    def login_page(self):
        """登录页面（对标 Go LoginPage）"""
        from flask import render_template
        debug = self.cfg.get("server", {}).get("debug", False)
        return render_template("login.html",
            error_msg="",
            debug=debug,
        )

    def register_page(self):
        """注册页面"""
        from flask import render_template, request
        msg = request.args.get("msg", "")
        return render_template("register.html", msg=msg)

    def login(self):
        """处理登录请求"""
        data = request.get_json(silent=True) or request.form
        user_name = data.get("user_name", "").strip()
        user_pwd = data.get("user_pwd", "").strip()

        if not user_name or not user_pwd:
            return jsonify({"error": "用户名和密码不能为空"}), 400

        client_ip = _client_ip()

        # 登录限流：检查是否被锁定
        if _is_login_locked(client_ip):
            return jsonify({"error": "登录失败次数过多，请稍后再试"}), 429

        # 按用户名查询用户
        user = self.store.get_user_by_login(user_name)

        # 使用 bcrypt 验证密码
        if not user or not verify_password(user_pwd, user["user_pwd"]):
            _record_login_failure(client_ip)
            return jsonify({"error": "用户名或密码错误"}), 401

        # 登录成功，清除失败记录
        _clear_login_failures(client_ip)

        # 检查密码是否过期
        pwd_expires_at = user.get("pwd_expires_at", "")
        if pwd_expires_at:
            try:
                expires_dt = datetime.fromisoformat(pwd_expires_at)
                if datetime.now() > expires_dt:
                    return jsonify({"error": "密码已过期，请联系管理员重置"}), 403
            except (ValueError, TypeError):
                pass
        must_change_pwd = bool(pwd_expires_at)

        # admin 实例：仅管理员可登录
        role = self.cfg["server"].get("role", "all")
        if role == "admin" and user["role"] != 1:  # RoleAdmin
            return jsonify({"error": "此账号无法访问管理后台"}), 403

        expiry = int(time.time()) + TOKEN_TTL
        token = generate_token(user["user_name"], user["role"], expiry)

        # 如果是客服座席，加入在线列表
        if user["role"] == 2:  # RoleAgent
            with self._agents_lock:
                self.online_agents[user["user_name"]] = time.time()

        response = jsonify({
            "status": "ok",
            "token": token,
            "user_name": user["user_name"],
            "role": user["role"],
            "must_change_pwd": must_change_pwd,
        })

        # 设置 httpOnly Cookie
        _set_auth_cookie(response, token, TOKEN_TTL)

        return response

    def logout(self):
        """处理注销"""
        token_str = extract_token()
        if token_str:
            user = parse_token(token_str)
            if user:
                with self._agents_lock:
                    self.online_agents.pop(user["user_name"], None)
            # 将 token 签名加入黑名单，使其立即失效
            _blacklist_token(token_str)

        response = jsonify({"status": "ok"})
        _clear_auth_cookie(response)
        return response

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