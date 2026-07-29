#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地向量存储 — 对标 Go 版本 internal/vdb/local.go
使用 SQLite 存储向量，内存缓存加速检索，余弦相似度检索。
"""
import math
import sqlite3
import threading
import os
import struct
import logging
from typing import Optional

logger = logging.getLogger(__name__)

VDB_DIR = "./vdb"
VECTORS_DB = "./vdb/vectors.db"


class LocalVectorStore:
    """本地 SQLite 向量存储"""

    def __init__(self, vdb_id: int):
        self.vdb_id = vdb_id
        self._lock = threading.RLock()
        self.dim = 0
        self.docs = []  # 内存缓存: list of dict

        os.makedirs(VDB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(VECTORS_DB, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._migrate()
        self._load_mem()

    def _migrate(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id      TEXT NOT NULL,
                vdb_id  INTEGER NOT NULL,
                content TEXT NOT NULL,
                vector  BLOB NOT NULL,
                source  TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (vdb_id, id)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vectors_vdb_id ON vectors(vdb_id)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vectors_source ON vectors(vdb_id, source)
        """)
        self.conn.commit()

    def _load_mem(self):
        rows = self.conn.execute(
            "SELECT id, content, vector, source FROM vectors WHERE vdb_id = ?",
            (self.vdb_id,),
        ).fetchall()
        self.docs = []
        for row in rows:
            vec = self._bytes_to_floats(row[2])
            self.docs.append({
                "id": row[0],
                "content": row[1],
                "vector": vec,
                "source": row[3],
            })
            if self.dim == 0 and vec:
                self.dim = len(vec)
        logger.debug("已加载 %d 条向量记录到内存, vdb_id=%d", len(self.docs), self.vdb_id)

    def ensure_collection(self, dimension: int):
        with self._lock:
            self.dim = dimension

    def insert(self, records: list) -> list:
        """批量插入向量记录，返回新插入的文档列表"""
        if not records:
            return []

        new_docs = []
        with self._lock:
            for r in records:
                vec_bytes = self._floats_to_bytes(r["vector"])
                source = r.get("metadata", {}).get("source", "")
                self.conn.execute(
                    "INSERT OR REPLACE INTO vectors (id, vdb_id, content, vector, source) VALUES (?, ?, ?, ?, ?)",
                    (r["id"], self.vdb_id, r["content"], vec_bytes, source),
                )

                doc = {
                    "id": r["id"],
                    "content": r["content"],
                    "vector": r["vector"],
                    "source": source,
                }
                new_docs.append(doc)

            self.conn.commit()

            # 更新内存缓存
            index = {d["id"]: i for i, d in enumerate(self.docs)}
            for nd in new_docs:
                if nd["id"] in index:
                    self.docs[index[nd["id"]]] = nd
                else:
                    self.docs.append(nd)
                    index[nd["id"]] = len(self.docs) - 1

            if self.dim == 0 and new_docs and new_docs[0]["vector"]:
                self.dim = len(new_docs[0]["vector"])

        return new_docs

    def search(self, query_vector: list[float], top_k: int, score_threshold: float) -> list:
        """余弦相似度检索"""
        with self._lock:
            docs = list(self.docs)

        if not docs:
            return []

        scored = []
        for doc in docs:
            if len(doc["vector"]) != len(query_vector):
                continue
            score = self._cosine_similarity(query_vector, doc["vector"])
            if score >= score_threshold:
                scored.append({
                    "id": doc["id"],
                    "content": doc["content"],
                    "metadata": {"source": doc["source"]},
                    "score": score,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete_by_ids(self, ids: list[str]):
        if not ids:
            return

        with self._lock:
            for id in ids:
                self.conn.execute(
                    "DELETE FROM vectors WHERE vdb_id = ? AND id = ?",
                    (self.vdb_id, id),
                )
            self.conn.commit()

            id_set = set(ids)
            self.docs = [d for d in self.docs if d["id"] not in id_set]

    def delete_by_source(self, source: str):
        with self._lock:
            self.conn.execute(
                "DELETE FROM vectors WHERE vdb_id = ? AND source = ?",
                (self.vdb_id, source),
            )
            self.conn.commit()
            self.docs = [d for d in self.docs if d["source"] != source]

    def purge(self):
        with self._lock:
            self.conn.execute("DELETE FROM vectors WHERE vdb_id = ?", (self.vdb_id,))
            self.conn.commit()
            self.docs = []

    def close(self):
        self.conn.close()

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _floats_to_bytes(floats: list[float]) -> bytes:
        return struct.pack(f"{len(floats)}d", *floats)

    @staticmethod
    def _bytes_to_floats(data: bytes) -> list[float]:
        count = len(data) // 8
        return list(struct.unpack(f"{count}d", data))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a)
        norm_b = sum(x * x for x in b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))