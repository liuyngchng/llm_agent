#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Agent 管理处理器 — 对标 Go 版本 internal/handler/agent.go
"""
import json
import logging
from flask import request, jsonify

from apps.csm.engine import get_system_vars, validate_template_vars

logger = logging.getLogger(__name__)


class AgentHandler:
    """AI Agent 管理处理器"""

    def __init__(self, store):
        self.store = store

    def list_system_vars(self):
        """返回系统变量列表 GET /api/system-vars（对标 Go ListSystemVars）"""
        return jsonify({"data": get_system_vars()})

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
        """创建 Agent（对标 Go Create，含 system_prompt 校验）"""
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "名称不能为空"}), 400

        system_prompt = data.get("system_prompt", "")
        if err := _validate_system_prompt(system_prompt):
            return jsonify({"error": err}), 400

        vdb_ids = data.get("vdb_ids", [])
        vdb_ids_json = json.dumps(vdb_ids)

        id = self.store.create_agent(
            name=name,
            description=data.get("description", ""),
            system_prompt=system_prompt,
            model_name=data.get("model_name", ""),
            temperature=data.get("temperature"),
            top_p=data.get("top_p"),
            max_tokens=data.get("max_tokens"),
            vdb_ids=vdb_ids_json,
        )
        return jsonify({"status": "ok", "id": id})

    def update(self, agent_id: int):
        """更新 Agent（对标 Go Update，含 system_prompt 校验）"""
        existing = self.store.get_agent(agent_id)
        if not existing:
            return jsonify({"error": "智能体不存在"}), 404

        data = request.get_json(silent=True) or {}

        system_prompt = data.get("system_prompt")
        if system_prompt is not None:
            if err := _validate_system_prompt(system_prompt):
                return jsonify({"error": err}), 400

        vdb_ids = data.get("vdb_ids", None)
        vdb_ids_json = None
        if vdb_ids is not None:
            vdb_ids_json = json.dumps(vdb_ids)

        self.store.update_agent(
            agent_id,
            name=data.get("name"),
            description=data.get("description"),
            system_prompt=system_prompt,
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


def _validate_system_prompt(prompt: str) -> str:
    """校验提示词中的系统变量引用，返回错误信息或空字符串"""
    if not prompt:
        return ""
    invalid = validate_template_vars(prompt)
    if invalid:
        logger.warning("agent system_prompt 被拒绝: 非法的系统变量: %s", invalid)
        return f"system_prompt 包含非法的系统变量：{'、'.join(invalid)}"
    return ""
