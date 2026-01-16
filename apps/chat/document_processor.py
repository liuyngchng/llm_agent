# !/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import hashlib
import pickle
import json
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

# 向量数据库相关
try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("注意: chromadb 未安装，向量搜索功能将不可用")

# 文本分块和嵌入
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.embeddings import OpenAIEmbeddings

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("注意: langchain 未安装，请安装: pip install langchain")

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """大文档处理类"""

    def __init__(self, upload_folder: str, embedding_model: str = "text-embedding-ada-002"):
        """
        初始化文档处理器

        Args:
            upload_folder: 上传文件目录
            embedding_model: 嵌入模型名称
        """
        self.upload_folder = upload_folder
        self.embedding_model = embedding_model

        # 创建向量存储目录
        self.vector_store_dir = os.path.join(upload_folder, "vector_stores")
        os.makedirs(self.vector_store_dir, exist_ok=True)

        # 创建文档缓存目录
        self.cache_dir = os.path.join(upload_folder, "document_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        # 初始化向量数据库
        self.chroma_client = None
        self.vector_store = {}

        if CHROMA_AVAILABLE and LANGCHAIN_AVAILABLE:
            self._init_vector_db()

    def _init_vector_db(self):
        """初始化向量数据库"""
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=self.vector_store_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info("向量数据库初始化成功")
        except Exception as e:
            logger.error(f"初始化向量数据库失败: {e}")
            self.chroma_client = None

    @staticmethod
    def _get_document_hash(filepath: str) -> str:
        """计算文档哈希值，用于标识文档"""
        with open(filepath, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash

    def _split_document(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """将文档分割成块"""
        if not LANGCHAIN_AVAILABLE:
            # 简单的文本分割作为后备方案
            return self._simple_text_split(text, chunk_size, chunk_overlap)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )
        return text_splitter.split_text(text)

    @staticmethod
    def _simple_text_split(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """简单的文本分割方法"""
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size
            if end >= text_length:
                chunks.append(text[start:])
                break

            # 尽量在句末或段落末分割
            split_pos = text.rfind('\n\n', start, end)
            if split_pos == -1:
                split_pos = text.rfind('\n', start, end)
            if split_pos == -1:
                split_pos = text.rfind('。', start, end)
            if split_pos == -1:
                split_pos = text.rfind('！', start, end)
            if split_pos == -1:
                split_pos = text.rfind('？', start, end)
            if split_pos == -1 or split_pos < start + chunk_size // 2:
                split_pos = end

            chunks.append(text[start:split_pos])
            start = split_pos - chunk_overlap if split_pos - chunk_overlap > start else split_pos

        return chunks

    def _create_document_cache(self, file_hash: str, metadata: Dict[str, Any]) -> str:
        """创建文档缓存"""
        cache_file = os.path.join(self.cache_dir, f"{file_hash}.json")
        cache_data = {
            "metadata": metadata,
            "processed_time": datetime.now().isoformat(),
            "chunks": [],  # 存储分块信息
        }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        return cache_file

    def process_large_document(self, filepath: str, filename: str, max_pages_per_chunk: int = 20) -> Dict[str, Any]:
        """
        处理大文档

        Args:
            filepath: 文件路径
            filename: 文件名
            max_pages_per_chunk: 每个块的最大页数

        Returns:
            处理结果字典
        """
        file_hash = self._get_document_hash(filepath)
        logger.info(f"开始处理文档: {filename}, 哈希: {file_hash}")

        # 检查是否已处理过
        cache_file = os.path.join(self.cache_dir, f"{file_hash}.json")
        if os.path.exists(cache_file):
            logger.info(f"文档已处理过，从缓存加载: {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 元数据
        metadata = {
            "filename": filename,
            "file_hash": file_hash,
            "file_size": os.path.getsize(filepath),
            "created_time": datetime.now().isoformat()
        }

        try:
            # 分页读取Word文档（需要修改docx_md_util）
            from common.docx_md_util import convert_docx_to_md_by_pages

            # 分页转换为Markdown
            md_files = convert_docx_to_md_by_pages(filepath, max_pages_per_chunk)

            chunks = []
            for i, md_file in enumerate(md_files):
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                chunk_info = {
                    "chunk_id": i + 1,
                    "page_range": f"{(i * max_pages_per_chunk) + 1}-{(i + 1) * max_pages_per_chunk}",
                    "content": content[:2000],  # 只存储预览
                    "full_content_path": md_file,  # 存储完整内容的路径
                    "length": len(content)
                }
                chunks.append(chunk_info)

                # 将分块存储到向量数据库
                if self.chroma_client and LANGCHAIN_AVAILABLE:
                    self._store_chunk_in_vector_db(file_hash, content, chunk_info)

            # 创建缓存
            cache_data = {
                "metadata": metadata,
                "processed_time": datetime.now().isoformat(),
                "chunks": chunks,
                "total_chunks": len(chunks),
                "vectorized": self.chroma_client is not None
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.info(f"文档处理完成，共 {len(chunks)} 个分块")
            return cache_data

        except Exception as e:
            logger.error(f"处理文档失败: {e}")
            return {
                "error": str(e),
                "metadata": metadata
            }

    def _store_chunk_in_vector_db(self, doc_hash: str, content: str, chunk_info: Dict[str, Any]):
        """将分块存储到向量数据库"""
        try:
            collection_name = f"doc_{doc_hash}"

            # 获取或创建集合
            try:
                collection = self.chroma_client.get_collection(name=collection_name)
            except:
                collection = self.chroma_client.create_collection(name=collection_name)

            # 生成嵌入向量
            embeddings = OpenAIEmbeddings(model=self.embedding_model)
            embedding = embeddings.embed_query(content[:2000])  # 只嵌入前2000字符

            # 添加到集合
            collection.add(
                embeddings=[embedding],
                documents=[content[:5000]],  # 存储前5000字符
                metadatas=[{
                    "chunk_id": chunk_info["chunk_id"],
                    "page_range": chunk_info["page_range"],
                    "doc_hash": doc_hash,
                    "timestamp": datetime.now().isoformat()
                }],
                ids=[f"chunk_{chunk_info['chunk_id']}"]
            )

            logger.info(f"分块 {chunk_info['chunk_id']} 已向量化存储")

        except Exception as e:
            logger.error(f"存储到向量数据库失败: {e}")

    def search_relevant_chunks(self, doc_hash: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        搜索与查询相关的文档分块

        Args:
            doc_hash: 文档哈希
            query: 查询文本
            top_k: 返回最相关的K个结果

        Returns:
            相关分块列表
        """
        if not self.chroma_client or not LANGCHAIN_AVAILABLE:
            return []

        try:
            collection_name = f"doc_{doc_hash}"
            collection = self.chroma_client.get_collection(name=collection_name)

            # 生成查询的嵌入向量
            embeddings = OpenAIEmbeddings(model=self.embedding_model)
            query_embedding = embeddings.embed_query(query)

            # 搜索相似分块
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            relevant_chunks = []
            for i in range(len(results['ids'][0])):
                chunk_id = results['ids'][0][i]
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0

                relevant_chunks.append({
                    "chunk_id": chunk_id,
                    "content": results['documents'][0][i],
                    "metadata": metadata,
                    "similarity": 1 - distance if distance else 0,
                    "distance": distance
                })

            return relevant_chunks

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []

    def get_chunk_full_content(self, doc_hash: str, chunk_id: int) -> Optional[str]:
        """获取分块的完整内容"""
        cache_file = os.path.join(self.cache_dir, f"{doc_hash}.json")

        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            for chunk in cache_data.get("chunks", []):
                if chunk.get("chunk_id") == chunk_id:
                    full_content_path = chunk.get("full_content_path")
                    if full_content_path and os.path.exists(full_content_path):
                        with open(full_content_path, 'r', encoding='utf-8') as f:
                            return f.read()

            return None

        except Exception as e:
            logger.error(f"获取分块内容失败: {e}")
            return None