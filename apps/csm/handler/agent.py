#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Agent 管理处理器 — 对标 Go 版本 internal/handler/agent.go
"""
import json
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)


class AgentHandler:
    """AI Agent 管理处理器"""

    def __init__(self, store):
        self.store = store

    def list_public(self):
        """返回公开的 Agent 列表（仅 id + name）"""
        agents = self.store.list_agents()
        if not agents:
            agents = []
        result = [{"id": a["id"], "name": a["name"]} for a in agents]
        return jsonify({"data": result})

    def list(self):
        """管理员查看所有 Agent（完整信息）"""
        agents = self.store.list_agents()
        if not agents:
            agents = []
        return jsonify({"data": agents})

    def get(self, agent_id: int):
        """获取单个 Agent 详情"""
        agent = self.store.get_agent(agent_id)
        if not agent:
            return jsonify({"error": "智能体不存在"}), 404
        return jsonify({"data": agent})

    def create(self):
        """创建 Agent"""
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "名称不能为空"}), 400

        vdb_ids = data.get("vdb_ids", [])
        vdb_ids_json = json.dumps(vdb_ids)

        id = self.store.create_agent(
            name=name,
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            model_name=data.get("model_name", ""),
            temperature=data.get("temperature"),
            top_p=data.get("top_p"),
            max_tokens=data.get("max_tokens"),
            vdb_ids=vdb_ids_json,
        )
        return jsonify({"status": "ok", "id": id})

    def update(self, agent_id: int):
        """更新 Agent"""
        existing = self.store.get_agent(agent_id)
        if not existing:
            return jsonify({"error": "智能体不存在"}), 404

        data = request.get_json(silent=True) or {}

        vdb_ids = data.get("vdb_ids", None)
        vdb_ids_json = None
        if vdb_ids is not None:
            vdb_ids_json = json.dumps(vdb_ids)

        self.store.update_agent(
            agent_id,
            name=data.get("name"),
            description=data.get("description"),
            system_prompt=data.get("system_prompt"),
            model_name=data.get("model_name"),
            temperature=data.get("temperature"),
            top_p=data.get("top_p"),
            max_tokens=data.get("max_tokens"),
            vdb_ids=vdb_ids_json,
        )
        return jsonify({"status": "ok"})

    def delete(self, agent_id: int):
        """删除 Agent"""
        self.store.delete_agent(agent_id)
        return jsonify({"status": "ok"})