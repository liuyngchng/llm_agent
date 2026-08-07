#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话管理器 — 对标 Go 版本 internal/session/manager.go
内存中管理会话历史，支持自动清理过期会话。
"""
import threading
import time
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

MAX_HISTORY_ROUNDS = 5
SESSION_TIMEOUT = 1800  # 30 分钟
CLEANUP_INTERVAL = 600  # 10 分钟


class SessionManager:
    """会话管理器，thread-safe"""

    def __init__(self):
        self._lock = threading.Lock()
        # key: uid -> {"uid": str, "history": deque, "updated_at": float}
        self._sessions = {}
        self._start_cleanup()

    def get_history(self, uid: str) -> list:
        """获取会话历史"""
        with self._lock:
            entry = self._sessions.get(uid)
            if not entry:
                return []
            return list(entry["history"])

    def add_message(self, uid: str, role: str, content: str):
        """添加消息到会话历史"""
        with self._lock:
            if uid not in self._sessions:
                self._sessions[uid] = {
                    "uid": uid,
                    "history": deque(maxlen=MAX_HISTORY_ROUNDS * 2),
                }
            entry = self._sessions[uid]
            entry["history"].append({"role": role, "content": content})
            entry["updated_at"] = time.time()

    def clear(self, uid: str):
        """清空会话历史"""
        with self._lock:
            self._sessions.pop(uid, None)

    def format_history(self, messages: list) -> str:
        """格式化历史消息为字符串"""
        if not messages:
            return "（无历史对话）"

        lines = []
        for msg in messages:
            if msg["role"] == "user":
                lines.append(f"用户：{msg['content']}")
            else:
                lines.append(f"机器人：{msg['content']}")
        return "\n".join(lines)

    def _cleanup(self):
        """定期清理过期会话"""
        while True:
            time.sleep(CLEANUP_INTERVAL)
            now = time.time()
            with self._lock:
                expired = [
                    k for k, v in self._sessions.items()
                    if now - v.get("updated_at", 0) > SESSION_TIMEOUT
                ]
                for k in expired:
                    del self._sessions[k]
                if expired:
                    logger.debug("清理了 %d 个过期会话", len(expired))

    def _start_cleanup(self):
        t = threading.Thread(target=self._cleanup, daemon=True, name="session_cleanup")
        t.start()