#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
适配器模块 - 用于兼容旧代码
"""
import os
import logging
from typing import Optional, Dict, Any, List

from vector_db import create_vector_db_manager

logger = logging.getLogger(__name__)


class VDBAdapter:
    """向量数据库适配器（兼容旧接口）"""

    @staticmethod
    def search(
            query: str,
            score_threshold: float,
            vector_db: str,
            llm_cfg: Dict[str, Any],
            top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        兼容旧search函数

        Args:
            query: 查询文本
            score_threshold: 相似度阈值
            vector_db: 向量数据库路径
            llm_cfg: LLM配置字典
            top_k: 返回数量

        Returns:
            搜索结果列表
        """
        try:
            manager = create_vector_db_manager(
                vector_db_path=vector_db,
                embedding_model=llm_cfg.get('embedding_model_name', ''),
                api_key=llm_cfg.get('embedding_api_key', ''),
                api_base=llm_cfg.get('embedding_api_uri', '')
            )

            return manager.search(query, score_threshold, top_k)

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    @staticmethod
    def search_txt(
            txt: str,
            vector_db_dir: str,
            score_threshold: float,
            llm_cfg: Dict[str, Any],
            txt_num: int
    ) -> str:
        """
        兼容旧search_txt函数

        Args:
            txt: 查询文本
            vector_db_dir: 向量数据库目录
            score_threshold: 相似度阈值
            llm_cfg: LLM配置字典
            txt_num: 返回文本数量

        Returns:
            拼接的文本结果
        """
        try:
            manager = create_vector_db_manager(
                vector_db_path=vector_db_dir,
                embedding_model=llm_cfg.get('embedding_model_name', ''),
                api_key=llm_cfg.get('embedding_api_key', ''),
                api_base=llm_cfg.get('embedding_api_uri', '')
            )

            return manager.search_text(txt, score_threshold, txt_num)

        except Exception as e:
            logger.error(f"文本搜索失败: {e}")
            return ""

    @staticmethod
    def vector_file(
            file_id: int,
            file_name: str,
            vector_db: str,
            llm_cfg: Dict[str, Any],
            chunk_size: int = 300,
            chunk_overlap: int = 80,
            batch_size: int = 10,
            separators: Optional[List[str]] = None
    ) -> bool:
        """
        兼容旧vector_file函数

        Args:
            file_id: 文件ID
            file_name: 文件名
            vector_db: 向量数据库路径
            llm_cfg: LLM配置字典
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            batch_size: 批处理大小
            separators: 分隔符列表

        Returns:
            是否成功
        """
        try:
            from vector_db import VectorDBConfig, EmbeddingConfig, IndexingConfig

            # 创建配置
            vector_db_config = VectorDBConfig(path=vector_db)
            embedding_config = EmbeddingConfig(
                model_name=llm_cfg.get('embedding_model_name', ''),
                api_key=llm_cfg.get('embedding_api_key', ''),
                api_base=llm_cfg.get('embedding_api_uri', '')
            )

            indexing_config = IndexingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
                separators=separators or ['。', '！', '？', '；', '...', '、', '，']
            )

            # 创建索引器
            from vector_db.indexer import DocumentIndexer
            indexer = DocumentIndexer(
                vector_db_config=vector_db_config,
                embedding_config=embedding_config,
                indexing_config=indexing_config
            )

            # 定义进度回调
            def progress_callback(task_id: int, text: str, percent: float):
                # 这里可以调用你的 VdbMeta.update_vdb_file_process_info
                try:
                    from common.vdb_meta_util import VdbMeta
                    VdbMeta.update_vdb_file_process_info(task_id, text, percent)
                except ImportError:
                    logger.info(f"任务 {task_id}: {text} ({percent}%)")

            # 索引文档
            indexer.index_document(
                file_path=file_name,
                task_id=file_id,
                task_callback=progress_callback
            )

            return True

        except Exception as e:
            logger.error(f"向量化文件失败: {e}")
            return False


# 导出兼容函数
def search(
        query: str,
        score_threshold: float,
        vector_db: str,
        llm_cfg: Dict[str, Any],
        top_k: int = 3
) -> List[Dict[str, Any]]:
    """兼容旧search函数"""
    return VDBAdapter.search(query, score_threshold, vector_db, llm_cfg, top_k)


def search_txt(
        txt: str,
        vector_db_dir: str,
        score_threshold: float,
        llm_cfg: Dict[str, Any],
        txt_num: int
) -> str:
    """兼容旧search_txt函数"""
    return VDBAdapter.search_txt(txt, vector_db_dir, score_threshold, llm_cfg, txt_num)


def vector_file(
        file_id: int,
        file_name: str,
        vector_db: str,
        llm_cfg: Dict[str, Any],
        chunk_size: int = 300,
        chunk_overlap: int = 80,
        batch_size: int = 10,
        separators: Optional[List[str]] = None
) -> bool:
    """兼容旧vector_file函数"""
    return VDBAdapter.vector_file(
        file_id, file_name, vector_db, llm_cfg,
        chunk_size, chunk_overlap, batch_size, separators
    )


def load_vdb(vector_db: str, llm_cfg: Dict[str, Any]) -> Optional[Any]:
    """
    兼容旧load_vdb函数

    注意: 新架构中不再需要这个函数，返回None以保持兼容性
    """
    logger.warning("load_vdb函数已过时，请使用新的VectorDBManager接口")
    return None


# 导出所有兼容函数
__all__ = [
    "search",
    "search_txt",
    "vector_file",
    "load_vdb",
    "VDBAdapter"
]