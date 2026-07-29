#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库处理器 — 对标 Go 版本 internal/handler/vdb.go
"""
import json
import logging
import os
from flask import request, jsonify

from apps.csm.handler.auth import get_auth_uid

logger = logging.getLogger(__name__)


class VdbHandler:
    """知识库管理 API 处理器"""

    def __init__(self, cfg: dict, kb_manager, store):
        self.cfg = cfg
        self.kb_mgr = kb_manager
        self.store = store

    def my_list(self):
        """获取用户的知识库列表 GET /api/vdb"""
        uid = get_auth_uid()
        lst = self.kb_mgr.get_user_kbs(uid)
        if lst is None:
            lst = []
        return jsonify({"data": lst})

    def pub_list(self):
        """获取公开知识库列表 GET /api/vdb/pub"""
        uid = get_auth_uid()
        lst = self.kb_mgr.get_public_kbs(uid)
        if lst is None:
            lst = []
        return jsonify({"data": lst})

    def file_list(self, vdb_id: int):
        """获取知识库文件列表 GET /api/vdb/<id>/files"""
        files = self.kb_mgr.get_files(vdb_id)
        if files is None:
            files = []
        return jsonify({"data": files})

    def set_default(self, vdb_id: int):
        """设置默认知识库 PUT /api/vdb/<id>/default"""
        uid = get_auth_uid()
        self.kb_mgr.set_default_kb(vdb_id, uid)
        return jsonify({"status": "ok"})

    def create(self):
        """创建知识库 POST /api/vdb"""
        uid = get_auth_uid()
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        is_public = data.get("is_public", False)

        if not name:
            return jsonify({"error": "知识库名称不能为空"}), 400

        try:
            id = self.kb_mgr.create_kb(name, uid, is_public)
            return jsonify({"status": "ok", "id": id})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    def delete(self, vdb_id: int):
        """删除知识库 DELETE /api/vdb/<id>"""
        uid = get_auth_uid()
        try:
            self.kb_mgr.delete_kb(vdb_id, uid)
            return jsonify({"status": "ok"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 403

    def upload(self, vdb_id: int):
        """上传文件到知识库 POST /api/vdb/<id>/upload"""
        uid = get_auth_uid()

        if "file" not in request.files:
            return jsonify({"error": "请选择文件"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "请选择文件"}), 400

        # 检查文件类型
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = {".txt", ".md", ".pdf", ".docx", ".xlsx"}
        if ext not in allowed_exts:
            return jsonify({"error": "不支持的文件格式，支持: txt, md, pdf, docx, xlsx"}), 400

        file_data = file.read()
        try:
            finfo = self.kb_mgr.upload_file(vdb_id, uid, file.filename, file_data)
            return jsonify({"status": "ok", "file": finfo})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    def process_info(self, file_id: int):
        """获取文件处理进度 GET /api/vdb/file/<id>/progress"""
        finfo = self.store.get_file_by_id(file_id)
        if not finfo:
            return jsonify({"error": "文件不存在"}), 404
        return jsonify({"data": finfo})

    def search(self):
        """在知识库中检索 POST /api/vdb/search"""
        uid = get_auth_uid()
        data = request.get_json(silent=True) or {}
        query = data.get("query", "")
        vdb_id = data.get("vdb_id", 0)

        if not query or not vdb_id:
            return jsonify({"error": "参数错误"}), 400

        result = self.kb_mgr.search_in_kb(
            query, vdb_id, uid,
            self.cfg["kb"].get("top_k", 3),
            self.cfg["kb"].get("score_threshold", 0.1),
        )
        return jsonify({"data": result})

    def file_delete(self, file_id: int):
        """删除文件 DELETE /api/vdb/file/<id>"""
        uid = get_auth_uid()
        try:
            self.kb_mgr.delete_file(file_id, uid)
            return jsonify({"status": "ok"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 403