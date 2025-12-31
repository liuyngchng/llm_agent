#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
向量库管理功能
"""
import os
import shutil
import threading
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
import logging
from pathlib import Path

import chromadb

from .types import (
    VectorDBConfig, EmbeddingConfig, VectorDBInfo,
    TaskProgress, SearchResult
)
from .indexer import DocumentIndexer
from .searcher import VectorSearcher
from .utils import validate_file_path, get_file_hash

logger = logging.getLogger(__name__)


class VectorDBManager:
    """向量数据库管理器"""

    def __init__(
            self,
            vector_db_config: VectorDBConfig,
            embedding_config: EmbeddingConfig
    ):
        self.vector_db_config = vector_db_config
        self.embedding_config = embedding_config

        # 任务管理
        self._tasks: Dict[int, TaskProgress] = {}
        self._task_lock = threading.Lock()

        # 索引器和搜索器实例
        self._indexer: Optional[DocumentIndexer] = None
        self._searcher: Optional[VectorSearcher] = None

        logger.info(f"向量库管理器初始化: {vector_db_config.path}")

    @property
    def indexer(self) -> DocumentIndexer:
        """获取文档索引器"""
        if self._indexer is None:
            from .indexer import DocumentIndexer
            self._indexer = DocumentIndexer(
                vector_db_config=self.vector_db_config,
                embedding_config=self.embedding_config
            )
        return self._indexer

    @property
    def searcher(self) -> VectorSearcher:
        """获取向量搜索器"""
        if self._searcher is None:
            from .searcher import VectorSearcher
            self._searcher = VectorSearcher(
                vector_db_config=self.vector_db_config,
                embedding_config=self.embedding_config
            )
        return self._searcher

    def add_document(
            self,
            file_path: str,
            task_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        添加文档到向量库

        Args:
            file_path: 文档路径
            task_id: 任务ID

        Returns:
            (成功标志, 消息)
        """
        if not validate_file_path(file_path):
            return False, f"文件不存在或不可读: {file_path}"

        if task_id is None:
            task_id = int(time.time() * 1000)

        try:
            # 更新任务状态
            self._update_task(task_id, "开始添加文档", 0)

            # 索引文档
            db_info = self.indexer.index_document(
                file_path=file_path,
                task_id=task_id,
                task_callback=self._task_callback
            )

            # 完成
            self._update_task(
                task_id,
                f"文档添加完成，共 {db_info.total_chunks} 个文本块",
                100,
                "completed"
            )

            return True, f"成功添加文档: {os.path.basename(file_path)}"

        except Exception as e:
            error_msg = f"添加文档失败: {str(e)}"
            logger.error(f"{error_msg}, 文件: {file_path}")
            self._update_task(task_id, error_msg, 0, "failed")
            return False, error_msg

    def update_document(
            self,
            old_file_path: str,
            new_file_path: str,
            task_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        更新文档（先删除旧文档，再添加新文档）

        Args:
            old_file_path: 旧文档路径
            new_file_path: 新文档路径
            task_id: 任务ID

        Returns:
            (成功标志, 消息)
        """
        if task_id is None:
            task_id = int(time.time() * 1000)

        try:
            # 开始更新
            self._update_task(task_id, "开始更新文档", 0)

            # 删除旧文档
            self._update_task(task_id, "删除旧版本文档", 20)
            delete_success = self.delete_document(old_file_path)

            if not delete_success:
                self._update_task(task_id, "删除旧文档失败", 0, "failed")
                return False, "删除旧文档失败"

            # 添加新文档
            self._update_task(task_id, "添加新版本文档", 50)
            add_success, message = self.add_document(new_file_path, task_id)

            if not add_success:
                self._update_task(task_id, f"添加新文档失败: {message}", 0, "failed")
                return False, f"添加新文档失败: {message}"

            # 完成
            self._update_task(task_id, "文档更新完成", 100, "completed")
            return True, "文档更新成功"

        except Exception as e:
            error_msg = f"更新文档失败: {str(e)}"
            logger.error(f"{error_msg}, 旧文件: {old_file_path}, 新文件: {new_file_path}")
            self._update_task(task_id, error_msg, 0, "failed")
            return False, error_msg

    def delete_document(self, file_path: str) -> bool:
        """
        从向量库中删除文档

        Args:
            file_path: 文档路径

        Returns:
            是否成功
        """
        if not validate_file_path(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return False

        try:
            # 获取绝对路径用于匹配
            abs_path = os.path.abspath(file_path)

            # 获取集合
            collection = self.searcher.collection

            # 查询匹配的文档块
            results = collection.get(where={"source": abs_path})

            if not results['ids']:
                logger.warning(f"未找到文档: {abs_path}")
                return False

            # 删除所有匹配的块
            collection.delete(ids=results['ids'])

            logger.info(f"成功删除文档: {abs_path}, 块数: {len(results['ids'])}")
            return True

        except Exception as e:
            logger.error(f"删除文档失败: {file_path}, 错误: {e}")
            return False

    def search(
            self,
            query: str,
            score_threshold: float = 0.5,
            top_k: int = 3,
            filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索文档

        Args:
            query: 查询文本
            score_threshold: 相似度阈值
            top_k: 返回数量
            filter_conditions: 过滤条件

        Returns:
            搜索结果列表
        """
        try:
            from .types import SearchConfig

            search_config = SearchConfig(
                score_threshold=score_threshold,
                top_k=top_k,
                filter_conditions=filter_conditions
            )

            results = self.searcher.search(query, search_config)

            # 转换为字典列表
            return [result.to_dict() for result in results]

        except Exception as e:
            logger.error(f"搜索失败: '{query[:30]}...', 错误: {e}")
            return []

    def search_text(
            self,
            query: str,
            score_threshold: float = 0.5,
            top_k: int = 3
    ) -> str:
        """
        搜索并返回拼接的文本

        Args:
            query: 查询文本
            score_threshold: 相似度阈值
            top_k: 返回数量

        Returns:
            拼接的文本结果
        """
        return self.searcher.search_with_text(
            query=query,
            score_threshold=score_threshold,
            top_k=top_k
        )

    def get_database_info(self) -> VectorDBInfo:
        """获取数据库信息"""
        return self.indexer.get_vector_db_info()

    def list_documents(self) -> List[str]:
        """列出向量库中的所有文档"""
        try:
            collection = self.searcher.collection

            # 获取所有元数据
            results = collection.get(include=["metadatas"])

            # 提取唯一的source
            sources = set()
            if results.get('metadatas'):
                for metadata in results['metadatas']:
                    if 'source' in metadata:
                        sources.add(metadata['source'])

            return list(sources)

        except Exception as e:
            logger.error(f"列出文档失败: {e}")
            return []

    def get_document_chunks(self, file_path: str) -> List[Dict[str, Any]]:
        """获取文档的所有块"""
        if not validate_file_path(file_path):
            return []

        try:
            abs_path = os.path.abspath(file_path)
            collection = self.searcher.collection

            # 查询匹配的块
            results = collection.get(
                where={"source": abs_path},
                include=["documents", "metadatas"]
            )

            chunks = []
            for i in range(len(results['ids'])):
                chunk = {
                    "id": results['ids'][i],
                    "content": results['documents'][i],
                    "metadata": results['metadatas'][i] if results.get('metadatas') else {}
                }
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"获取文档块失败: {file_path}, 错误: {e}")
            return []

    def cleanup(self, days_old: int = 30) -> int:
        """
        清理旧任务

        Args:
            days_old: 清理多少天前的任务

        Returns:
            清理的任务数
        """
        with self._task_lock:
            current_time = time.time()
            cutoff_time = current_time - (days_old * 24 * 3600)

            # 找出需要清理的任务
            tasks_to_remove = [
                task_id for task_id, progress in self._tasks.items()
                if progress.timestamp < cutoff_time
            ]

            # 清理任务
            for task_id in tasks_to_remove:
                del self._tasks[task_id]

            logger.info(f"清理了 {len(tasks_to_remove)} 个旧任务")
            return len(tasks_to_remove)

    def backup(self, backup_path: str) -> bool:
        """
        备份向量数据库

        Args:
            backup_path: 备份路径

        Returns:
            是否成功
        """
        try:
            source_path = Path(self.vector_db_config.path)
            target_path = Path(backup_path)

            if not source_path.exists():
                logger.error(f"源目录不存在: {source_path}")
                return False

            # 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 复制目录
            if target_path.exists():
                shutil.rmtree(target_path)

            shutil.copytree(source_path, target_path)

            logger.info(f"向量库备份成功: {source_path} -> {target_path}")
            return True

        except Exception as e:
            logger.error(f"备份向量库失败: {e}")
            return False

    def restore(self, backup_path: str) -> bool:
        """
        从备份恢复向量数据库

        Args:
            backup_path: 备份路径

        Returns:
            是否成功
        """
        try:
            source_path = Path(backup_path)
            target_path = Path(self.vector_db_config.path)

            if not source_path.exists():
                logger.error(f"备份目录不存在: {source_path}")
                return False

            # 关闭现有连接
            self.close()

            # 删除现有目录
            if target_path.exists():
                shutil.rmtree(target_path)

            # 恢复备份
            shutil.copytree(source_path, target_path)

            logger.info(f"向量库恢复成功: {source_path} -> {target_path}")
            return True

        except Exception as e:
            logger.error(f"恢复向量库失败: {e}")
            return False

    def _task_callback(self, task_id: int, text: str, percent: float):
        """任务回调函数"""
        self._update_task(task_id, text, percent)

    def _update_task(
            self,
            task_id: int,
            text: str,
            percent: float,
            status: str = "running"
    ):
        """更新任务状态"""
        with self._task_lock:
            if task_id not in self._tasks:
                self._tasks[task_id] = TaskProgress(
                    task_id=task_id,
                    text=text,
                    percent=percent,
                    status=status
                )
            else:
                self._tasks[task_id].text = text
                self._tasks[task_id].percent = percent
                self._tasks[task_id].status = status
                self._tasks[task_id].timestamp = time.time()

    def get_task_progress(self, task_id: int) -> Optional[TaskProgress]:
        """获取任务进度"""
        with self._task_lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        with self._task_lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = "cancelled"
                self._tasks[task_id].text = "任务已被用户取消"
                return True
        return False

    def close(self):
        """关闭所有资源"""
        if self._indexer:
            self._indexer.close()
            self._indexer = None

        if self._searcher:
            self._searcher.close()
            self._searcher = None

        logger.info("向量库管理器已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()