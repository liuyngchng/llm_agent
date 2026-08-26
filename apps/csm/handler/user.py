#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理处理器 — 对标 Go 版本 internal/handler/user.go
安全升级：使用 bcrypt 替代 MD5，密码由 handler 层验证。
"""
import logging
import time
from flask import request, jsonify

from apps.csm.crypto import hash_password, verify_password, validate_password
from apps.csm.handler.auth import get_auth_uid, generate_token, parse_token
from apps.csm.handler.auth import TOKEN_TTL

logger = logging.getLogger(__name__)


class UserHandler:
    """用户管理处理器"""

    def __init__(self, store):
        self.store = store

    # ============================================================
    # 用户管理（admin only）
    # ============================================================

    def list_users(self):
        """获取所有用户 GET /api/users"""
        users = self.store.list_users()
        if not users:
            users = []
        # 不返回密码
        result = [{"uid": u["uid"], "user_name": u["user_name"],
                    "role": u["role"], "note": u["note"]} for u in users]
        return jsonify({"data": result})

    def create_user(self):
        """创建用户 POST /api/users"""
        data = request.get_json(silent=True) or {}
        user_name = data.get("user_name", "").strip()
        user_pwd = data.get("user_pwd", "").strip()
        role = data.get("role", 0)
        note = data.get("note", "")

        if not user_name or not user_pwd:
            return jsonify({"error": "用户名和密码不能为空"}), 400

        # 验证密码复杂度
        try:
            validate_password(user_pwd)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # 使用 bcrypt 哈希密码
        pwd_hash = hash_password(user_pwd)
        try:
            self.store.create_user(user_name, pwd_hash, role, note)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": f"创建用户失败: {e}"}), 400

    def delete_user(self, user_name: str):
        """删除用户 DELETE /api/users/<name>"""
        if not user_name:
            return jsonify({"error": "用户名不能为空"}), 400

        # 不允许删除自己
        current_user = get_auth_uid()
        if user_name == current_user:
            return jsonify({"error": "不能删除自己"}), 400

        self.store.delete_user_by_name(user_name)
        return jsonify({"status": "ok"})

    def reset_user_pwd(self, user_name: str):
        """重置用户密码 PUT /api/users/<name>/reset-pwd"""
        data = request.get_json(silent=True) or {}
        user_pwd = data.get("user_pwd", "").strip()

        if not user_pwd:
            return jsonify({"error": "密码不能为空"}), 400

        # 验证密码复杂度
        try:
            validate_password(user_pwd)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # 使用 bcrypt 哈希密码
        pwd_hash = hash_password(user_pwd)
        self.store.reset_password(user_name, pwd_hash)
        return jsonify({"status": "ok"})

    # ============================================================
    # 修改密码（所有用户）
    # ============================================================

    def change_password(self):
        """修改自己的密码 PUT /api/user/password"""
        user_name = get_auth_uid()
        data = request.get_json(silent=True) or {}
        old_pwd = data.get("old_pwd", "")
        new_pwd = data.get("new_pwd", "")

        if not new_pwd:
            return jsonify({"error": "新密码不能为空"}), 400

        # 验证新密码复杂度
        try:
            validate_password(new_pwd)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # 先从数据库取得当前用户，验证旧密码
        user = self.store.get_user_by_name(user_name)
        if not user:
            return jsonify({"error": "获取用户信息失败"}), 500

        if not verify_password(old_pwd, user["user_pwd"]):
            return jsonify({"error": "旧密码不正确"}), 400

        # 使用 bcrypt 哈希新密码
        new_pwd_hash = hash_password(new_pwd)

        if self.store.update_password(user_name, new_pwd_hash):
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "修改密码失败"}), 400

    # ============================================================
    # 用户自助注册
    # ============================================================

    def register(self):
        """用户自助注册 POST /api/register"""
        data = request.get_json(silent=True) or {}
        user_name = data.get("user_name", "").strip()
        user_pwd = data.get("user_pwd", "").strip()

        if not user_name or not user_pwd:
            return jsonify({"error": "用户名和密码不能为空"}), 400

        # 验证密码复杂度
        try:
            validate_password(user_pwd)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # 检查用户名是否已存在
        existing = self.store.get_user_by_name(user_name)
        if existing:
            return jsonify({"error": "用户名已被占用"}), 409

        pwd_hash = hash_password(user_pwd)
        try:
            self.store.create_user(user_name, pwd_hash, 0, "自行注册")  # RoleNormal
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": f"注册失败: {e}"}), 500

    # ============================================================
    # API Token 管理
    # ============================================================

    def list_my_tokens(self):
        """查看我的 API token GET /api/user/tokens"""
        user_name = get_auth_uid()
        tokens = self.store.get_user_api_tokens(user_name)
        if not tokens:
            tokens = []

        now = time.time()
        result = []
        for t in tokens:
            expires_at = t["expires_at"]
            # 转换 datetime 或 string 到 timestamp
            if hasattr(expires_at, "timestamp"):
                exp_ts = expires_at.timestamp()
            else:
                exp_ts = time.mktime(time.strptime(str(expires_at), "%Y-%m-%d %H:%M:%S"))

            result.append({
                "id": t["id"],
                "token_preview": t["token_preview"],
                "expires_at": str(t["expires_at"]),
                "expiring_soon": (exp_ts - now) < 600,
                "create_time": str(t["created_at"]),
            })

        return jsonify({"data": result})

    def generate_token(self):
        """生成新的 API token POST /api/user/token"""
        user_name = get_auth_uid()
        user = getattr(request, "_csm_user", None)
        role = 3  # RoleAPI
        if user:
            role = user.get("role", 3)

        expiry = int(time.time()) + TOKEN_TTL
        token = generate_token(user_name, role, expiry)

        # 保存到数据库
        preview = token[:16]
        expiry_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry))
        self.store.save_api_token(user_name, preview, expiry_str)

        return jsonify({
            "status": "ok",
            "token": token,
            "expires_at": expiry_str,
        })

    # ============================================================
    # API 调用日志
    # ============================================================

    def my_call_logs(self):
        """查看 API 调用记录 GET /api/user/call-logs"""
        user_name = get_auth_uid()
        logs = self.store.get_user_api_call_logs(user_name)
        if not logs:
            logs = []
        return jsonify({"data": logs})