#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
使用示例
"""
import logging
from vector_db import (
    create_vector_db_manager,
    VectorDBConfig,
    EmbeddingConfig,
    search,
    search_txt
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def my_advanced_example():
    """高级使用示例"""
    # 配置
    vector_db_path = "./vdb/test_db"
    embedding_model = "text-embedding-ada-002"
    api_key = "your-api-key"
    api_base = "https://api.openai.com/v1"

    # 创建管理器
    manager = create_vector_db_manager(
        vector_db_path=vector_db_path,
        embedding_model=embedding_model,
        api_key=api_key,
        api_base=api_base
    )

    try:
        # 1. 添加文档
        print("1. 添加文档...")
        success, message = manager.add_document("./example.txt")
        print(f"结果: {success}, 消息: {message}")

        # 2. 搜索文档
        print("\n2. 搜索文档...")
        results = manager.search(
            query="什么是人工智能？",
            score_threshold=0.5,
            top_k=3
        )

        for result in results:
            print(f"分数: {result['score']:.4f}")
            print(f"内容: {result['content'][:100]}...")
            print("-" * 50)

        # 3. 获取数据库信息
        print("\n3. 数据库信息...")
        info = manager.get_database_info()
        print(f"总块数: {info.total_chunks}")
        print(f"文档源: {info.sources}")

        # 4. 列出所有文档
        print("\n4. 所有文档...")
        documents = manager.list_documents()
        for doc in documents:
            print(f"- {doc}")

        # 5. 搜索文本
        print("\n5. 搜索文本...")
        text_result = manager.search_text(
            query="机器学习",
            score_threshold=0.3,
            top_k=2
        )
        print(f"文本结果:\n{text_result}")

    finally:
        # 关闭管理器
        manager.close()


def my_simple_example():
    """简单使用示例（向后兼容）"""
    vector_db_dir = "./vdb/test_db"
    embedding_model = "text-embedding-ada-002"
    api_key = "your-api-key"
    api_base = "https://api.openai.com/v1"

    # 使用快捷函数
    print("1. 使用search函数...")
    results = search(
        query="人工智能",
        vector_db_path=vector_db_dir,
        embedding_model=embedding_model,
        api_key=api_key,
        api_base=api_base,
        score_threshold=0.1,
        top_k=2
    )

    for result in results:
        print(f"分数: {result['score']}")
        print(f"内容: {result['content'][:50]}...")

    print("\n2. 使用search_txt函数...")
    text_result = search_txt(
        txt="机器学习",
        vector_db_path=vector_db_dir,
        embedding_model=embedding_model,
        api_key=api_key,
        api_base=api_base,
        score_threshold=0.1,
        txt_num=2
    )
    print(f"文本结果:\n{text_result}")


if __name__ == "__main__":
    print("=== 高级使用示例 ===")
    my_advanced_example()

    print("\n=== 简单使用示例 ===")
    my_simple_example()