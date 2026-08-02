#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 元数据存储 — 对标 Go 版本 internal/store/sqlite.go
支持所有 CRUD 操作：知识库、文件、用户、API Token、日志、智能体、工作流、FAQ、系统配置。
"""
import json
import os
import sqlite3
import threading
import time
import hashlib
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================

# 默认智能体系统提示词（工作流引擎使用，{{sys.xxx}} 变量语法）
# 对标 Go: defaultAgentPrompt
DEFAULT_AGENT_PROMPT = """你是专业的对话机器人，负责解答客户咨询。你必须基于以下知识库信息回答用户问题。
如果知识库中没有相关信息，请引导用户转接人工客服。

今日日期：{{sys.cur_date}}（星期{{sys.cur_week}}）

知识库内容：
---
{{sys.kb_context}}
---

历史对话：
{{sys.history}}

用户问题：{{sys.user_query}}

请用亲切、专业的中文回答："""

# 默认聊天提示词模板（简单聊天模式使用，{xxx} 变量语法）
# 对标 Go: defaultChatPrompt
DEFAULT_CHAT_PROMPT = """你是专业的对话机器人，负责解答客户咨询。你必须基于以下知识库信息回答用户问题。
如果知识库中没有相关信息，请引导用户转接人工客服。

今日日期：{cur_date}（星期{cur_week}）

知识库内容：
---
{context}
---

历史对话：
{history}

用户问题：{question}

请用亲切、专业的中文回答："""


# ============================================================
# SQLiteStore
# ============================================================

class SQLiteStore:
    """SQLite 元数据存储，对标 Go 的 MetaStore 接口"""

    def __init__(self, db_path: str):
        self._lock = threading.Lock()
        self.db_path = db_path
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库文件 {db_path} 不存在，请从 cfg.db.template 复制")

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()
        self._seed_users()
        self._seed_default_agent()

    def close(self):
        self.conn.close()

    # ============================================================
    # 数据库迁移
    # ============================================================

    def _migrate(self):
        schema = """
        CREATE TABLE IF NOT EXISTS vdb_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            uid TEXT NOT NULL DEFAULT '',
            is_public INTEGER NOT NULL DEFAULT 0,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS vdb_file_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            uid TEXT NOT NULL DEFAULT '',
            vdb_id INTEGER NOT NULL,
            task_id TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL DEFAULT '',
            percent REAL NOT NULL DEFAULT 0,
            process_info TEXT NOT NULL DEFAULT '',
            file_md5 TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prompt_template (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            uid INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sys_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL UNIQUE,
            config_value TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL UNIQUE,
            user_pwd TEXT NOT NULL DEFAULT '',
            role INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            token_preview TEXT NOT NULL DEFAULT '',
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            api_path TEXT NOT NULL DEFAULT '',
            method TEXT NOT NULL DEFAULT '',
            request_body TEXT NOT NULL DEFAULT '',
            response_body TEXT NOT NULL DEFAULT '',
            status_code INTEGER NOT NULL DEFAULT 200,
            error_msg TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agent_def (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            system_prompt TEXT NOT NULL DEFAULT '',
            model_name TEXT NOT NULL DEFAULT '',
            temperature REAL,
            top_p REAL,
            max_tokens INTEGER,
            vdb_ids TEXT NOT NULL DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_def (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            classifier TEXT NOT NULL DEFAULT '',
            nodes TEXT NOT NULL DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS faq_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            answer TEXT NOT NULL,
            source_file TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS faq_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            embedding TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entry_id) REFERENCES faq_entries(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_vdb_info_uid ON vdb_info(uid);
        CREATE INDEX IF NOT EXISTS idx_vdb_file_info_vdb_id ON vdb_file_info(vdb_id);
        CREATE INDEX IF NOT EXISTS idx_sys_config_key ON sys_config(config_key);
        CREATE INDEX IF NOT EXISTS idx_users_name ON users(user_name);
        CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_name);
        CREATE INDEX IF NOT EXISTS idx_api_call_log_user ON api_call_log(user_name);
        CREATE INDEX IF NOT EXISTS idx_faq_questions_entry ON faq_questions(entry_id);
        """
        self.conn.executescript(schema)
        self.conn.commit()

    # ============================================================
    # 种子数据
    # ============================================================

    def _seed_users(self):
        count = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count > 0:
            return

        builtin_users = [
            ("user0", 0, "内置普通用户"),
            ("user1", 0, "内置普通用户"),
            ("admin", 1, "内置管理员"),
            ("person0", 2, "内置客服座席"),
            ("person1", 2, "内置客服座席"),
            ("api0", 3, "内置API调用用户"),
        ]
        for name, role, note in builtin_users:
            pwd = self._md5(name)
            self.conn.execute(
                "INSERT INTO users (user_name, user_pwd, role, note) VALUES (?, ?, ?, ?)",
                (name, pwd, role, note),
            )
        self.conn.commit()
        logger.info("种子用户已创建")

    def _seed_default_agent(self):
        count = self.conn.execute("SELECT COUNT(*) FROM agent_def").fetchone()[0]
        if count > 0:
            return
        self.conn.execute(
            "INSERT INTO agent_def (name, description, system_prompt, vdb_ids) VALUES (?, ?, ?, '[]')",
            ("通用客服", "默认智能体，负责解答客户咨询", DEFAULT_AGENT_PROMPT),
        )
        self.conn.commit()

    @staticmethod
    def _md5(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()

    # ============================================================
    # 知识库 (vdb_info) CRUD
    # ============================================================

    def create_vdb(self, name: str, uid: str, is_public: bool) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO vdb_info (name, uid, is_public) VALUES (?, ?, ?)",
                (name, uid, 1 if is_public else 0),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_vdb_by_id(self, id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, uid, is_public, is_default, created_at FROM vdb_info WHERE id = ?",
            (id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_user_vdbs(self, uid: str) -> list:
        rows = self.conn.execute(
            "SELECT id, name, uid, is_public, is_default, created_at FROM vdb_info WHERE uid = ? ORDER BY created_at DESC",
            (uid,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_public_vdbs(self, exclude_uid: str) -> list:
        rows = self.conn.execute(
            "SELECT id, name, uid, is_public, is_default, created_at FROM vdb_info WHERE is_public = 1 AND uid != ? ORDER BY created_at DESC",
            (exclude_uid,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete_vdb(self, id: int):
        with self._lock:
            self.conn.execute("DELETE FROM vdb_file_info WHERE vdb_id = ?", (id,))
            self.conn.execute("DELETE FROM vdb_info WHERE id = ?", (id,))
            self.conn.commit()

    def set_default_vdb(self, id: int, uid: str):
        with self._lock:
            self.conn.execute("UPDATE vdb_info SET is_default = 0 WHERE uid = ?", (uid,))
            self.conn.execute("UPDATE vdb_info SET is_default = 1 WHERE id = ? AND uid = ?", (id, uid))
            self.conn.commit()

    def check_vdb_name_exists(self, name: str, uid: str) -> bool:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM vdb_info WHERE name = ? AND uid = ?", (name, uid),
        ).fetchone()
        return row[0] > 0

    def get_default_vdb_id(self, uid: str) -> Optional[int]:
        row = self.conn.execute(
            "SELECT id FROM vdb_info WHERE uid = ? AND is_default = 1 LIMIT 1", (uid,),
        ).fetchone()
        return row[0] if row else None

    # ============================================================
    # 文件 (vdb_file_info) CRUD
    # ============================================================

    def create_file_info(self, name: str, uid: str, vdb_id: int, task_id: str,
                         file_path: str, file_md5: str) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO vdb_file_info (name, uid, vdb_id, task_id, file_path, percent, process_info, file_md5) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
                (name, uid, vdb_id, task_id, file_path, "文件已上传，等待处理", file_md5),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_files_by_vdb_id(self, vdb_id: int) -> list:
        rows = self.conn.execute(
            "SELECT id, name, uid, vdb_id, task_id, file_path, percent, process_info, file_md5, created_at "
            "FROM vdb_file_info WHERE vdb_id = ? ORDER BY created_at DESC", (vdb_id,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_file_by_id(self, id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, uid, vdb_id, task_id, file_path, percent, process_info, file_md5, created_at "
            "FROM vdb_file_info WHERE id = ?", (id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_unprocessed_files(self) -> list:
        rows = self.conn.execute(
            "SELECT id, name, uid, vdb_id, task_id, file_path, percent, process_info, file_md5, created_at "
            "FROM vdb_file_info WHERE percent != 100 ORDER BY created_at ASC",
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_file_progress(self, id: int, percent: float, info: str):
        self.conn.execute(
            "UPDATE vdb_file_info SET percent = ?, process_info = ? WHERE id = ?",
            (percent, info, id),
        )
        self.conn.commit()

    def delete_file(self, id: int):
        self.conn.execute("DELETE FROM vdb_file_info WHERE id = ?", (id,))
        self.conn.commit()

    def check_file_md5_exists(self, vdb_id: int, md5: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, uid, vdb_id, task_id, file_path, percent, process_info, file_md5, created_at "
            "FROM vdb_file_info WHERE vdb_id = ? AND file_md5 = ?", (vdb_id, md5),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    # ============================================================
    # 提示词模板
    # ============================================================

    def get_prompt(self, name: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM prompt_template WHERE name = ?", (name,),
        ).fetchone()
        return row[0] if row else None

    def upsert_prompt(self, name: str, value: str, uid: int = 0):
        with self._lock:
            self.conn.execute(
                "INSERT INTO prompt_template (name, value, uid) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value, uid = excluded.uid",
                (name, value, uid),
            )
            self.conn.commit()

    # ============================================================
    # 用户 (users)
    # ============================================================

    def get_user_by_login(self, user_name: str, md5_pwd: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT uid, user_name, user_pwd, role, note FROM users WHERE user_name = ? AND user_pwd = ?",
            (user_name, md5_pwd),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_user_by_name(self, user_name: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT uid, user_name, user_pwd, role, note FROM users WHERE user_name = ?",
            (user_name,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_users(self) -> list:
        rows = self.conn.execute(
            "SELECT uid, user_name, user_pwd, role, note FROM users ORDER BY uid",
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def create_user(self, user_name: str, user_pwd: str, role: int, note: str = ""):
        with self._lock:
            self.conn.execute(
                "INSERT INTO users (user_name, user_pwd, role, note) VALUES (?, ?, ?, ?)",
                (user_name, user_pwd, role, note),
            )
            self.conn.commit()

    def delete_user_by_name(self, user_name: str):
        self.conn.execute("DELETE FROM users WHERE user_name = ?", (user_name,))
        self.conn.commit()

    def reset_password(self, user_name: str, md5_pwd: str):
        self.conn.execute(
            "UPDATE users SET user_pwd = ? WHERE user_name = ?", (md5_pwd, user_name),
        )
        self.conn.commit()

    def update_password(self, user_name: str, old_md5_pwd: str, new_md5_pwd: str) -> bool:
        cur = self.conn.execute(
            "UPDATE users SET user_pwd = ? WHERE user_name = ? AND user_pwd = ?",
            (new_md5_pwd, user_name, old_md5_pwd),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ============================================================
    # API Token
    # ============================================================

    def save_api_token(self, user_name: str, token_preview: str, expires_at: str):
        self.conn.execute(
            "INSERT INTO api_tokens (user_name, token_preview, expires_at) VALUES (?, ?, ?)",
            (user_name, token_preview, expires_at),
        )
        self.conn.commit()

    def get_user_api_tokens(self, user_name: str) -> list:
        rows = self.conn.execute(
            "SELECT id, user_name, token_preview, expires_at, created_at "
            "FROM api_tokens WHERE user_name = ? AND expires_at > datetime('now') "
            "ORDER BY created_at DESC", (user_name,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ============================================================
    # API 调用日志
    # ============================================================

    def save_api_call_log(self, user_name: str, api_path: str, method: str,
                          req_body: str, resp_body: str, status_code: int, error_msg: str):
        self.conn.execute(
            "INSERT INTO api_call_log (user_name, api_path, method, request_body, response_body, status_code, error_msg) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_name, api_path, method, req_body, resp_body, status_code, error_msg),
        )
        self.conn.commit()

    def get_user_api_call_logs(self, user_name: str, limit: int = 100) -> list:
        rows = self.conn.execute(
            "SELECT id, user_name, api_path, method, request_body, response_body, status_code, error_msg, created_at "
            "FROM api_call_log WHERE user_name = ? ORDER BY created_at DESC LIMIT ?",
            (user_name, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ============================================================
    # Agent (agent_def) CRUD
    # ============================================================

    def create_agent(self, name: str, description: str = "", system_prompt: str = "",
                     model_name: str = "", temperature=None, top_p=None,
                     max_tokens=None, vdb_ids: str = "[]") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO agent_def (name, description, system_prompt, model_name, temperature, top_p, max_tokens, vdb_ids) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, description, system_prompt, model_name, temperature, top_p, max_tokens, vdb_ids),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_agent(self, id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, description, system_prompt, model_name, temperature, top_p, max_tokens, vdb_ids, created_at, updated_at "
            "FROM agent_def WHERE id = ?", (id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_agents(self) -> list:
        rows = self.conn.execute(
            "SELECT id, name, description, system_prompt, model_name, temperature, top_p, max_tokens, vdb_ids, created_at, updated_at "
            "FROM agent_def ORDER BY id",
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_agent(self, id: int, name: str = None, description: str = None,
                     system_prompt: str = None, model_name: str = None,
                     temperature=None, top_p=None, max_tokens=None, vdb_ids: str = None):
        with self._lock:
            fields = []
            values = []
            if name is not None:
                fields.append("name = ?")
                values.append(name)
            if description is not None:
                fields.append("description = ?")
                values.append(description)
            if system_prompt is not None:
                fields.append("system_prompt = ?")
                values.append(system_prompt)
            if model_name is not None:
                fields.append("model_name = ?")
                values.append(model_name)
            if temperature is not None:
                fields.append("temperature = ?")
                values.append(temperature)
            if top_p is not None:
                fields.append("top_p = ?")
                values.append(top_p)
            if max_tokens is not None:
                fields.append("max_tokens = ?")
                values.append(max_tokens)
            if vdb_ids is not None:
                fields.append("vdb_ids = ?")
                values.append(vdb_ids)
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(id)
            self.conn.execute(
                f"UPDATE agent_def SET {', '.join(fields)} WHERE id = ?", values,
            )
            self.conn.commit()

    def delete_agent(self, id: int):
        self.conn.execute("DELETE FROM agent_def WHERE id = ?", (id,))
        self.conn.commit()

    # ============================================================
    # Workflow (workflow_def) CRUD
    # ============================================================

    def create_workflow(self, name: str, description: str = "",
                        classifier: dict = None, nodes: list = None) -> int:
        with self._lock:
            classifier_json = json.dumps(classifier) if classifier else ""
            nodes_json = json.dumps(nodes) if nodes else "[]"
            cur = self.conn.execute(
                "INSERT INTO workflow_def (name, description, classifier, nodes) VALUES (?, ?, ?, ?)",
                (name, description, classifier_json, nodes_json),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_workflow(self, id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, description, classifier, nodes, created_at, updated_at FROM workflow_def WHERE id = ?",
            (id,),
        ).fetchone()
        if not row:
            return None
        result = self._row_to_dict(row)
        if result["classifier"]:
            try:
                result["classifier"] = json.loads(result["classifier"])
            except json.JSONDecodeError:
                result["classifier"] = None
        if result["nodes"]:
            try:
                result["nodes"] = json.loads(result["nodes"])
            except json.JSONDecodeError:
                result["nodes"] = []
        return result

    def list_workflows(self) -> list:
        rows = self.conn.execute(
            "SELECT id, name, description, classifier, nodes, created_at, updated_at FROM workflow_def ORDER BY id",
        ).fetchall()
        result = []
        for row in rows:
            d = self._row_to_dict(row)
            if d["classifier"]:
                try:
                    d["classifier"] = json.loads(d["classifier"])
                except json.JSONDecodeError:
                    d["classifier"] = None
            if d["nodes"]:
                try:
                    d["nodes"] = json.loads(d["nodes"])
                except json.JSONDecodeError:
                    d["nodes"] = []
            result.append(d)
        return result

    def update_workflow(self, id: int, name: str = None, description: str = None,
                        classifier: dict = None, nodes: list = None):
        with self._lock:
            fields = []
            values = []
            if name is not None:
                fields.append("name = ?")
                values.append(name)
            if description is not None:
                fields.append("description = ?")
                values.append(description)
            if classifier is not None:
                fields.append("classifier = ?")
                values.append(json.dumps(classifier))
            if nodes is not None:
                fields.append("nodes = ?")
                values.append(json.dumps(nodes))
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(id)
            self.conn.execute(
                f"UPDATE workflow_def SET {', '.join(fields)} WHERE id = ?", values,
            )
            self.conn.commit()

    def delete_workflow(self, id: int):
        self.conn.execute("DELETE FROM workflow_def WHERE id = ?", (id,))
        self.conn.commit()

    # ============================================================
    # FAQ 条目管理
    # ============================================================

    def create_faq_entry(self, answer: str, source_file: str = "") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO faq_entries (answer, source_file) VALUES (?, ?)",
                (answer, source_file),
            )
            self.conn.commit()
            return cur.lastrowid

    def create_faq_question(self, entry_id: int, question: str, embedding_json: str = "") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO faq_questions (entry_id, question, embedding) VALUES (?, ?, ?)",
                (entry_id, question, embedding_json),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_faq_entries(self) -> list:
        rows = self.conn.execute(
            "SELECT id, answer, source_file, created_at FROM faq_entries ORDER BY id",
        ).fetchall()
        entries = []
        for row in rows:
            entry = self._row_to_dict(row)
            entry["questions"] = self.get_faq_questions_by_entry_id(entry["id"])
            entries.append(entry)
        return entries

    def get_faq_questions_by_entry_id(self, entry_id: int) -> list:
        rows = self.conn.execute(
            "SELECT id, entry_id, question, created_at FROM faq_questions WHERE entry_id = ? ORDER BY id",
            (entry_id,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows] if rows else []

    def get_all_faq_questions_with_embedding(self) -> list:
        rows = self.conn.execute(
            "SELECT id, entry_id, question, embedding FROM faq_questions",
        ).fetchall()
        result = []
        for row in rows:
            d = self._row_to_dict(row)
            if d["embedding"]:
                try:
                    d["embedding"] = json.loads(d["embedding"])
                except json.JSONDecodeError:
                    continue
            else:
                d["embedding"] = []
            result.append(d)
        return result

    def delete_faq_entry(self, id: int):
        with self._lock:
            self.conn.execute("DELETE FROM faq_questions WHERE entry_id = ?", (id,))
            self.conn.execute("DELETE FROM faq_entries WHERE id = ?", (id,))
            self.conn.commit()

    def update_faq_entry(self, id: int, answer: str):
        self.conn.execute("UPDATE faq_entries SET answer = ? WHERE id = ?", (answer, id))
        self.conn.commit()

    def delete_faq_questions_by_entry_id(self, entry_id: int):
        self.conn.execute("DELETE FROM faq_questions WHERE entry_id = ?", (entry_id,))
        self.conn.commit()

    def clear_all_faq(self):
        with self._lock:
            self.conn.execute("DELETE FROM faq_questions")
            self.conn.execute("DELETE FROM faq_entries")
            self.conn.commit()

    # ============================================================
    # 系统配置 (sys_config)
    # ============================================================

    def get_config(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT config_value FROM sys_config WHERE config_key = ?", (key,),
        ).fetchone()
        return row[0] if row else None

    def set_config(self, key: str, value: str, description: str = ""):
        with self._lock:
            self.conn.execute(
                "INSERT INTO sys_config (config_key, config_value, description) VALUES (?, ?, ?) "
                "ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value, "
                "description = CASE WHEN excluded.description != '' THEN excluded.description ELSE description END, "
                "updated_at = CURRENT_TIMESTAMP",
                (key, value, description),
            )
            self.conn.commit()

    def get_all_configs(self) -> dict:
        rows = self.conn.execute("SELECT config_key, config_value FROM sys_config").fetchall()
        return {r[0]: r[1] for r in rows}

    def seed_default_configs(self, sys_name: str, sys_auth: str):
        count = self.conn.execute("SELECT COUNT(*) FROM sys_config").fetchone()[0]
        if count > 0:
            return

        defaults = [
            ("sys.name", sys_name, "系统名称"),
            ("sys.auth", sys_auth, "是否启用认证 (true/false)"),
            ("sys.api_auth", "true", "是否启用接口认证 (true/false)"),
            ("kb.chunk_size", "300", "文本分片大小（字符数）"),
            ("kb.chunk_overlap", "80", "文本分片重叠大小（字符数）"),
            ("kb.top_k", "3", "检索返回条数"),
            ("kb.score_threshold", "0.1", "检索相似度阈值"),
            ("kb.rerank_enabled", "false", "是否启用 Rerank 重排序"),
            ("kb.rerank_retrieve_n", "15", "Rerank 预检索条数"),
            ("llm.temperature", "0.7", "LLM 温度参数 (0-2)"),
            ("llm.top_p", "0.9", "LLM Top-P 采样参数 (0-1)"),
            ("llm.max_tokens", "2048", "LLM 最大生成 Token 数"),
            ("faq.match_threshold", "0.85", "FAQ 匹配阈值 (0~1)"),
        ]
        for key, value, desc in defaults:
            self.set_config(key, value, desc)
        logger.info("默认系统配置已初始化")

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row) if row else None