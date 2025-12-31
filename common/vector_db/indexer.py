#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
向量化索引构建
"""
import os
import threading
import time
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

import chromadb
from langchain_community.document_loaders import (
    TextLoader, UnstructuredPDFLoader, UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from tqdm import tqdm

from .types import (
    VectorDBConfig, EmbeddingConfig, IndexingConfig,
    DocumentChunk, TaskProgress, VectorDBInfo
)
from .embedder import EmbeddingClient
from .utils import validate_file_path, ensure_directory, get_file_extension

logger = logging.getLogger(__name__)


class DocumentLoader:
    """文档加载器"""

    # 支持的文件类型和对应的加载器
    LOADER_MAPPING = {
        'txt': TextLoader,
        'pdf': UnstructuredPDFLoader,
        'docx': UnstructuredWordDocumentLoader,
        'doc': UnstructuredWordDocumentLoader,
    }

    @classmethod
    def load_document(cls, file_path: str, encoding: str = 'utf-8') -> List[Document]:
        """
        加载文档

        Args:
            file_path: 文档路径
            encoding: 文件编码

        Returns:
            Document列表
        """
        if not validate_file_path(file_path):
            raise FileNotFoundError(f"文件不存在或不可读: {file_path}")

        # 获取文件扩展名
        ext = get_file_extension(file_path)

        if ext not in cls.LOADER_MAPPING:
            raise ValueError(f"不支持的文件类型: {ext}")

        # 加载文档
        try:
            loader_class = cls.LOADER_MAPPING[ext]
            if ext == 'txt':
                loader = loader_class(file_path, encoding=encoding)
            else:
                loader = loader_class(file_path)

            documents = loader.load()

            # 确保每个文档都有source元数据
            for doc in documents:
                if 'source' not in doc.metadata:
                    doc.metadata['source'] = file_path

            logger.info(f"成功加载文档: {file_path}, 文档数: {len(documents)}")
            return documents

        except Exception as e:
            logger.error(f"加载文档失败: {file_path}, 错误: {e}")
            raise


class DocumentIndexer:
    """文档索引器"""

    def __init__(
            self,
            vector_db_config: VectorDBConfig,
            embedding_config: EmbeddingConfig,
            indexing_config: Optional[IndexingConfig] = None
    ):
        self.vector_db_config = vector_db_config
        self.embedding_config = embedding_config
        self.indexing_config = indexing_config or IndexingConfig()

        # 确保向量库目录存在
        ensure_directory(vector_db_config.path)

        # 客户端
        self._embedding_client: Optional[EmbeddingClient] = None
        self._chroma_client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None

        # 进度回调
        self.progress_callback: Optional[callable] = None

    @property
    def embedding_client(self) -> EmbeddingClient:
        """获取嵌入客户端"""
        if self._embedding_client is None:
            from .embedder import create_embedding_client
            self._embedding_client = create_embedding_client(self.embedding_config)
        return self._embedding_client

    @property
    def chroma_client(self) -> chromadb.PersistentClient:
        """获取Chroma客户端"""
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(
                path=self.vector_db_config.path,
                settings=chromadb.Settings(
                    **self.vector_db_config.to_chroma_settings()
                )
            )
        return self._chroma_client

    @property
    def collection(self) -> chromadb.Collection:
        """获取或创建集合"""
        if self._collection is None:
            self._collection = self.chroma_client.get_or_create_collection(
                name=self.vector_db_config.collection_name,
                embedding_function=self.embedding_client.embedder,
                metadata={"hnsw:space": self.vector_db_config.distance_metric.value}
            )
        return self._collection

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档为块"""
        logger.info(f"开始分割文档，文档数: {len(documents)}")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.indexing_config.chunk_size,
            chunk_overlap=self.indexing_config.chunk_overlap,
            separators=self.indexing_config.separators,
            keep_separator=self.indexing_config.keep_separator
        )

        chunks = text_splitter.split_documents(documents)
        logger.info(f"文档分割完成，块数: {len(chunks)}")

        return chunks

    def index_document(
            self,
            file_path: str,
            task_id: Optional[int] = None,
            task_callback: Optional[callable] = None
    ) -> VectorDBInfo:
        """
        索引单个文档

        Args:
            file_path: 文档路径
            task_id: 任务ID（用于进度跟踪）
            task_callback: 进度回调函数

        Returns:
            向量库信息
        """
        self.progress_callback = task_callback

        try:
            # 更新进度
            self._update_progress(task_id, "开始加载文档", 0)

            # 加载文档
            documents = DocumentLoader.load_document(file_path)

            # 更新进度
            self._update_progress(task_id, f"文档加载完成，共 {len(documents)} 个片段", 10)

            # 分割文档
            self._update_progress(task_id, "开始分割文本", 20)
            chunks = self.split_documents(documents)

            # 准备数据
            self._update_progress(task_id, f"开始向量化 {len(chunks)} 个文本块", 30)

            # 批量插入
            total_chunks = len(chunks)
            completed = 0

            # 准备批量数据
            all_ids = []
            all_documents = []
            all_metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{os.path.basename(chunk.metadata['source'])}_{i}"
                all_ids.append(chunk_id)
                all_documents.append(chunk.page_content)
                all_metadatas.append(chunk.metadata)

            # 批量处理
            batch_size = self.indexing_config.batch_size
            with tqdm(total=total_chunks, desc="向量化进度", unit="chunk") as pbar:
                for i in range(0, total_chunks, batch_size):
                    end_idx = min(i + batch_size, total_chunks)

                    # 检查任务是否被取消
                    if task_id and self._is_task_cancelled(task_id):
                        self._update_progress(task_id, "任务已被用户取消", 100)
                        raise InterruptedError("任务被取消")

                    try:
                        # 批量插入
                        self.collection.upsert(
                            ids=all_ids[i:end_idx],
                            documents=all_documents[i:end_idx],
                            metadatas=all_metadatas[i:end_idx]
                        )

                        completed = end_idx
                        percent = 30 + (completed / total_chunks) * 60

                        # 更新进度
                        self._update_progress(
                            task_id,
                            f"已处理 {completed}/{total_chunks} 个文本块",
                            percent
                        )

                        pbar.update(end_idx - i)

                    except Exception as e:
                        logger.error(f"处理批次 {i}-{end_idx} 失败: {e}")
                        self._update_progress(
                            task_id,
                            f"处理批次 {i}-{end_idx} 时出错: {str(e)}",
                            percent
                        )
                        raise

            # 完成
            self._update_progress(task_id, f"文档索引完成，共处理 {total_chunks} 个文本块", 100)

            # 返回向量库信息
            return self.get_vector_db_info()

        except Exception as e:
            logger.error(f"索引文档失败: {file_path}, 错误: {e}")
            self._update_progress(task_id, f"处理失败: {str(e)}", 0)
            raise

    def index_documents_batch(
            self,
            file_paths: List[str],
            task_id: Optional[int] = None,
            task_callback: Optional[callable] = None
    ) -> VectorDBInfo:
        """
        批量索引文档

        Args:
            file_paths: 文档路径列表
            task_id: 任务ID
            task_callback: 进度回调

        Returns:
            向量库信息
        """
        self.progress_callback = task_callback

        total_files = len(file_paths)
        completed_files = 0

        self._update_progress(task_id, f"开始批量处理 {total_files} 个文档", 0)

        for i, file_path in enumerate(file_paths):
            try:
                # 计算当前进度
                base_percent = (completed_files / total_files) * 100
                self._update_progress(
                    task_id,
                    f"正在处理第 {i + 1}/{total_files} 个文档: {os.path.basename(file_path)}",
                    base_percent
                )

                # 索引单个文档
                self.index_document(file_path, task_id, task_callback)
                completed_files += 1

            except Exception as e:
                logger.error(f"处理文档失败: {file_path}, 错误: {e}")
                # 继续处理其他文档
                continue

        # 完成
        self._update_progress(
            task_id,
            f"批量处理完成，成功处理 {completed_files}/{total_files} 个文档",
            100
        )

        return self.get_vector_db_info()

    def get_vector_db_info(self) -> VectorDBInfo:
        """获取向量库信息"""
        try:
            collection = self.collection
            count = collection.count()

            # 获取所有元数据中的source
            results = collection.get(include=["metadatas"])
            sources = set()
            if results['metadatas']:
                for metadata in results['metadatas']:
                    if 'source' in metadata:
                        sources.add(metadata['source'])

            return VectorDBInfo(
                path=self.vector_db_config.path,
                collection_name=self.vector_db_config.collection_name,
                total_chunks=count,
                sources=list(sources),
                last_updated=time.time()
            )

        except Exception as e:
            logger.error(f"获取向量库信息失败: {e}")
            return VectorDBInfo(
                path=self.vector_db_config.path,
                collection_name=self.vector_db_config.collection_name
            )

    def _update_progress(self, task_id: Optional[int], text: str, percent: float):
        """更新进度"""
        if self.progress_callback and task_id:
            try:
                self.progress_callback(task_id, text, percent)
            except Exception as e:
                logger.error(f"调用进度回调失败: {e}")

        logger.info(f"任务进度: {text} ({percent:.1f}%)")

    def _is_task_cancelled(self, task_id: int) -> bool:
        """检查任务是否被取消"""
        try:
            # 这里需要根据你的具体实现来检查任务状态
            # 例如从数据库或全局状态中检查
            from common.bp_vdb import is_task_cancelled
            return is_task_cancelled(task_id)
        except ImportError:
            logger.debug("未找到任务取消检查模块")
            return False
        except Exception as e:
            logger.error(f"检查任务状态失败: {e}")
            return False

    def close(self):
        """关闭资源"""
        if self._embedding_client:
            self._embedding_client.close()
            self._embedding_client = None

        self._chroma_client = None
        self._collection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()