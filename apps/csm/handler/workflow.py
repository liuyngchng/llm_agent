#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流管理处理器 — 对标 Go 版本 internal/handler/workflow.go
"""
import json
import logging
from flask import request, jsonify

from apps.csm.engine import has_next_nodes, validate_workflow_graph, auto_detect_is_final

logger = logging.getLogger(__name__)


class WorkflowHandler:
    """工作流管理处理器"""

    def __init__(self, store):
        self.store = store

    def list_public(self):
        """返回公开的工作流列表（聊天页下拉用，不含节点详情）"""
        workflows = self.store.list_workflows()
        if not workflows:
            workflows = []

        result = []
        for w in workflows:
            result.append({
                "id": w["id"],
                "name": w["name"],
                "description": w["description"],
                "classifier": w.get("classifier"),
                "nodes": w.get("nodes", []),
            })
        return jsonify({"data": result})

    def list(self):
        """管理员获取所有工作流（完整节点）"""
        workflows = self.store.list_workflows()
        if not workflows:
            workflows = []
        return jsonify({"data": workflows})

    def get(self, workflow_id: int):
        """获取单个工作流"""
        workflow = self.store.get_workflow(workflow_id)
        if not workflow:
            return jsonify({"error": "工作流不存在"}), 404
        return jsonify({"data": workflow})

    def create(self):
        """创建工作流（对标 Go Create，含 DAG 验证）"""
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        nodes = data.get("nodes", [])

        if not name:
            return jsonify({"error": "名称不能为空"}), 400
        if not nodes:
            return jsonify({"error": "工作流至少需要一个节点"}), 400

        # DAG 模式：验证图结构
        if has_next_nodes(nodes):
            err = validate_workflow_graph(nodes)
            if err:
                return jsonify({"error": f"工作流图验证失败: {err}"}), 400
            # 自动检测 IsFinal：无下游节点的即为 sink
            auto_detect_is_final(nodes)
        else:
            # 线性模式：自动标记最后一个节点为 final
            nodes[-1]["is_final"] = True

        id = self.store.create_workflow(
            name=name,
            description=data.get("description", ""),
            classifier=data.get("classifier"),
            nodes=nodes,
        )
        return jsonify({"status": "ok", "id": id})

    def update(self, workflow_id: int):
        """更新工作流（对标 Go Update，含 DAG 验证）"""
        existing = self.store.get_workflow(workflow_id)
        if not existing:
            return jsonify({"error": "工作流不存在"}), 404

        data = request.get_json(silent=True) or {}
        nodes = data.get("nodes", [])

        if not nodes:
            return jsonify({"error": "工作流至少需要一个节点"}), 400

        # DAG 模式：验证图结构
        if has_next_nodes(nodes):
            err = validate_workflow_graph(nodes)
            if err:
                return jsonify({"error": f"工作流图验证失败: {err}"}), 400
            # 自动检测 IsFinal：无下游节点的即为 sink
            auto_detect_is_final(nodes)
        else:
            # 线性模式：自动标记最后一个节点为 final，其余为 false
            for i, node in enumerate(nodes):
                node["is_final"] = (i == len(nodes) - 1)

        self.store.update_workflow(
            workflow_id,
            name=data.get("name"),
            description=data.get("description"),
            classifier=data.get("classifier"),
            nodes=nodes,
        )
        return jsonify({"status": "ok"})

    def delete(self, workflow_id: int):
        """删除工作流"""
        self.store.delete_workflow(workflow_id)
        return jsonify({"status": "ok"})
