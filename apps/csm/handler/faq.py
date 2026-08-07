#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAQ 管理处理器 — 对标 Go 版本 internal/handler/faq.go
支持 FAQ 条目的 CRUD、上传、向量匹配。
"""
import json
import logging
import math
from flask import request, jsonify

logger = logging.getLogger(__name__)

FAQ_TEMPLATE_CONTENT = """# FAQ 模板文件
# 格式说明：Q: 开头为问题（可多个 Q 对应同一个答案），A: 开头为答案
# 空行分隔不同的 FAQ 条目
#
# 用法：修改此文件后，在管理后台 → FAQ 管理 → 上传 FAQ 文件

Q: 如何重置密码？
Q: 忘记密码怎么办？
Q: 密码忘了
A: 您好，您可以在登录页面点击"忘记密码"，按照提示输入注册邮箱，系统会发送重置链接到您的邮箱。链接有效期为 24 小时，请及时操作。

Q: 支持哪些支付方式？
Q: 可以用微信支付吗？
Q: 能用支付宝吗？
Q: 是否支持银行卡付款？
A: 目前支持微信支付、支付宝、银联银行卡（储蓄卡及信用卡）以及 Apple Pay。单笔限额根据不同支付渠道略有差异，微信/支付宝单笔限额 50000 元，银行卡单笔限额 200000 元。

Q: 如何联系人工客服？
Q: 转人工
Q: 找客服
A: 您好，人工客服工作时间为周一至周五 9:00-18:00。您可以在公众号内回复"转人工"，或者拨打客服热线 400-XXX-XXXX。当前非工作时间，您可以先留言，我们会在下一个工作日与您联系。
"""


class FaqHandler:
    """FAQ 管理 API 处理器"""

    def __init__(self, store, embedding_client=None):
        self.store = store
        self.emb_client = embedding_client

    def list(self):
        """获取所有 FAQ 条目 GET /api/faq"""
        entries = self.store.get_faq_entries()
        if not entries:
            entries = []
        return jsonify({"data": entries})

    def match(self):
        """FAQ 独立匹配接口 POST /api/faq/match"""
        data = request.get_json(silent=True) or {}
        query = (data.get("query") or "").strip()

        if not query:
            return jsonify({"error": "query 不能为空"}), 400

        # 从配置中读取阈值
        threshold = 0.85
        cfg_val = self.store.get_config("faq.match_threshold")
        if cfg_val:
            try:
                threshold = float(cfg_val)
            except (ValueError, TypeError):
                pass

        answer, score = self.match_faq(query, threshold)
        matched = answer is not None
        return jsonify({
            "answer": answer or "",
            "score": score,
            "matched": matched,
        })

    def template(self):
        """下载 FAQ 模板文件 GET /api/faq/template"""
        from flask import Response
        return Response(
            FAQ_TEMPLATE_CONTENT,
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=faq_template.txt"},
        )

    def upload(self):
        """上传 FAQ 文件 POST /api/faq/upload"""
        if "file" not in request.files:
            return jsonify({"error": "请选择文件"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "请选择文件"}), 400

        name = file.filename.lower()
        if not name.endswith(".txt") and not name.endswith(".md"):
            return jsonify({"error": "仅支持 txt/md 格式的 FAQ 文件"}), 400

        content = file.read().decode("utf-8", errors="ignore")

        entries = self._parse_faq_content(content)
        if not entries:
            return jsonify({"error": "FAQ 文件内容为空或格式不正确"}), 400

        created = 0
        for entry in entries:
            try:
                self._create_faq_entry(entry["questions"], entry["answer"], file.filename)
                created += 1
            except Exception as e:
                logger.error("创建 FAQ 条目失败: %s", e)

        return jsonify({"status": "ok", "created": created, "total": len(entries)})

    def create(self):
        """创建单个 FAQ 条目 POST /api/faq"""
        data = request.get_json(silent=True) or {}
        questions = data.get("questions", [])
        answer = data.get("answer", "").strip()

        if not questions or not answer:
            return jsonify({"error": "问题和答案不能为空"}), 400

        self._create_faq_entry(questions, answer, "")
        return jsonify({"status": "ok"})

    def update(self, faq_id: int):
        """更新 FAQ 条目 PUT /api/faq/<id>"""
        if not faq_id:
            return jsonify({"error": "无效的 ID"}), 400

        data = request.get_json(silent=True) or {}
        questions = data.get("questions", [])
        answer = data.get("answer", "").strip()

        if not questions or not answer:
            return jsonify({"error": "问题和答案不能为空"}), 400

        # 更新答案
        self.store.update_faq_entry(faq_id, answer)

        # 删除旧问题，重新向量化
        self.store.delete_faq_questions_by_entry_id(faq_id)

        # 为新问题计算向量并入库
        if self.emb_client:
            for q in questions:
                q = q.strip()
                if not q:
                    continue
                try:
                    emb = self.emb_client.embed_single(q)
                    emb_json = json.dumps(emb)
                    self.store.create_faq_question(faq_id, q, emb_json)
                except Exception as e:
                    logger.warning("FAQ 问题向量化失败: question=%s, error=%s", q[:30], e)
        else:
            # 没有 embedding 客户端，只存问题不存向量
            for q in questions:
                q = q.strip()
                if q:
                    self.store.create_faq_question(faq_id, q, "")

        return jsonify({"status": "ok"})

    def delete(self, faq_id: int):
        """删除 FAQ 条目 DELETE /api/faq/<id>"""
        if not faq_id:
            return jsonify({"error": "无效的 ID"}), 400
        self.store.delete_faq_entry(faq_id)
        return jsonify({"status": "ok"})

    def clear_all(self):
        """清空所有 FAQ DELETE /api/faq"""
        self.store.clear_all_faq()
        return jsonify({"status": "ok"})

    # ============================================================
    # FAQ 匹配（供 chat 调用）
    # ============================================================

    def get_faq_count(self) -> int:
        """返回 FAQ 条目数量"""
        entries = self.store.get_faq_entries()
        return len(entries) if entries else 0

    def match_faq(self, query: str, threshold: float = 0.85):
        """匹配用户问题到 FAQ，返回 (答案, 分数) 或 (None, 0)"""
        if not self.emb_client:
            return None, 0

        questions = self.store.get_all_faq_questions_with_embedding()
        if not questions:
            return None, 0

        # 计算查询向量
        try:
            query_vec = self.emb_client.embed_single(query)
        except Exception as e:
            logger.error("FAQ 匹配: query embedding 失败: %s", e)
            return None, 0

        best_score = 0.0
        best_entry_id = None

        for q in questions:
            if not q.get("embedding"):
                continue
            score = self._cosine_similarity(query_vec, q["embedding"])
            if score > best_score:
                best_score = score
                best_entry_id = q["entry_id"]

        if best_score < threshold or best_entry_id is None:
            return None, best_score

        # 根据 entry_id 获取答案
        entries = self.store.get_faq_entries()
        for e in entries:
            if e["id"] == best_entry_id:
                return e["answer"], best_score

        return None, 0

    # ============================================================
    # 辅助函数
    # ============================================================

    def _create_faq_entry(self, questions: list, answer: str, source_file: str):
        entry_id = self.store.create_faq_entry(answer, source_file)

        if self.emb_client:
            for q in questions:
                q = q.strip()
                if not q:
                    continue
                try:
                    emb = self.emb_client.embed_single(q)
                    emb_json = json.dumps(emb)
                    self.store.create_faq_question(entry_id, q, emb_json)
                except Exception as e:
                    logger.warning("FAQ 问题向量化失败: question=%s, error=%s", q[:30], e)
        else:
            for q in questions:
                q = q.strip()
                if q:
                    self.store.create_faq_question(entry_id, q, "")

    @staticmethod
    def _parse_faq_content(content: str) -> list:
        """解析 FAQ 文件内容"""
        lines = content.replace("\r\n", "\n").split("\n")
        pairs = []
        current = None

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                if current and current.get("questions") and current.get("answer"):
                    pairs.append(current)
                    current = None
                continue

            upper = trimmed.upper()
            if upper.startswith("Q:") or upper.startswith("Q："):
                q = trimmed[2:].strip()
                if not q:
                    continue
                if current is None:
                    current = {"questions": [], "answer": ""}
                if current["answer"]:
                    pairs.append(current)
                    current = {"questions": [], "answer": ""}
                current["questions"].append(q)
            elif upper.startswith("A:") or upper.startswith("A："):
                a = trimmed[2:].strip()
                if current is None:
                    current = {"questions": [], "answer": ""}
                current["answer"] = a

        if current and current.get("questions") and current.get("answer"):
            pairs.append(current)

        return pairs

    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a)
        norm_b = sum(x * x for x in b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))