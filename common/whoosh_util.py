#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install whoosh
"""

import os
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, KEYWORD, DATETIME, NUMERIC
from whoosh.analysis import StemmingAnalyzer, RegexTokenizer
from whoosh.qparser import QueryParser, MultifieldParser, OrGroup

# 定义索引结构 - 这是核心
schema = Schema(
    # stored=True 表示存储原始值，搜索后可以获取
    title=TEXT(stored=True, analyzer=StemmingAnalyzer()),  # 英文词干提取
    content=TEXT(stored=True, analyzer=RegexTokenizer()),  # 正则分词
    path=ID(stored=True, unique=True),  # 唯一标识
    tags=KEYWORD(stored=True, commas=True, lowercase=True),  # 逗号分隔的关键词
    created_at=DATETIME(stored=True, sortable=True),  # 可排序时间
    views=NUMERIC(stored=True, sortable=True)  # 可排序数字
)

# 创建索引目录
index_dir = "search_index"
if not os.path.exists(index_dir):
    os.mkdir(index_dir)
    ix = create_in(index_dir, schema)
    print(f"索引已创建在: {index_dir}")
else:
    ix = open_dir(index_dir)
    print(f"索引已打开: {index_dir}")


def add_doc():
    from datetime import datetime

    # 获取写入器
    writer = ix.writer()

    # 添加文档
    documents = [
        {
            "title": "Python 入门教程",
            "content": "Python 是一种高级编程语言，适合初学者学习人工智能和数据分析。",
            "path": "/doc/python-intro",
            "tags": "编程,python,入门",
            "created_at": datetime(2024, 1, 10),
            "views": 1500
        },
        {
            "title": "人工智能基础",
            "content": "AI 包括机器学习、深度学习和自然语言处理等技术。",
            "path": "/doc/ai-basics",
            "tags": "人工智能,机器学习,深度学习",
            "created_at": datetime(2024, 1, 15),
            "views": 3200
        },
        {
            "title": "全文搜索技术",
            "content": "Whoosh 是 Python 的轻量级全文搜索引擎，易于使用。",
            "path": "/doc/fulltext-search",
            "tags": "搜索,whoosh,python",
            "created_at": datetime(2024, 1, 20),
            "views": 800
        }
    ]

    for doc in documents:
        # 使用 update_document 可以更新（根据唯一字段）
        writer.update_document(**doc)
        # 或者使用 add_document 仅添加
        # writer.add_document(**doc)

    # 提交到索引
    writer.commit()
    print(f"已索引 {len(documents)} 篇文档")


def basic_search(search_query, field="content"):
    """简单搜索示例"""
    with ix.searcher() as searcher:
        # 创建查询解析器
        parser = QueryParser(field, ix.schema)

        # 解析查询字符串
        query = parser.parse(search_query)
        print(f"解析后的查询: {query}")

        # 执行搜索
        results = searcher.search(query, limit=10)
        print(f"找到 {len(results)} 个结果:")

        # 显示结果
        for i, hit in enumerate(results, 1):
            print(f"\n{i}. 评分: {hit.score:.3f}")
            print(f"   标题: {hit['title']}")
            print(f"   路径: {hit['path']}")
            print(f"   摘要: {hit.highlights('content', top=3)}")  # 高亮匹配片段

        return results


def advanced_search():
    """高级搜索示例"""
    with ix.searcher() as searcher:

        # 1. 多字段搜索
        print("=== 多字段搜索 ===")
        m_parser = MultifieldParser(["title", "content", "tags"], ix.schema, group=OrGroup)
        query = m_parser.parse("python OR 人工智能")
        results = searcher.search(query)
        for r in results:
            print(f"{r['title']} - 标签: {r['tags']}")

        # 2. 分页
        print("\n=== 分页示例 ===")
        PAGE_SIZE = 2
        query = QueryParser("content", ix.schema).parse("技术")
        results = searcher.search_page(query, 1, PAGE_SIZE)  # 第1页，每页2条

        print(f"第 {results.pagenum} 页，共 {results.pagecount} 页")
        for r in results:
            print(f"- {r['title']}")

        # 3. 排序
        print("\n=== 按浏览量排序 ===")
        query = QueryParser("content", ix.schema).parse("技术")
        results = searcher.search(query, sortedby="views", reverse=True)  # 按浏览量降序
        for r in results:
            print(f"{r['title']} - 浏览量: {r['views']}")

        # 4. 筛选
        print("\n=== 筛选（浏览量>1000） ===")
        from whoosh.query import NumericRange
        from whoosh.query import And

        content_query = QueryParser("content", ix.schema).parse("技术")
        views_query = NumericRange("views", 1000, None)  # views >= 1000
        combined_query = And([content_query, views_query])

        results = searcher.search(combined_query)
        for r in results:
            print(f"{r['title']} - 浏览量: {r['views']}")


def highlight_results():
    """搜索结果高亮"""
    with ix.searcher() as searcher:
        parser = QueryParser("content", ix.schema)
        query = parser.parse("编程 语言")

        # 自定义高亮格式
        from whoosh.highlight import HtmlFormatter, ContextFragmenter

        results = searcher.search(query)

        # HTML 格式高亮
        html_formatter = HtmlFormatter(tagname="b", classname="highlight", between="...")
        fragmenter = ContextFragmenter(maxchars=200, surround=50)

        for hit in results:
            print(f"\n标题: {hit['title']}")

            # 获取高亮片段
            fragments = hit.highlights(
                "content",
                top=2,  # 最多2个片段
                minscore=20,  # 最小评分
                fragmenter=fragmenter,
                formatter=html_formatter
            )

            if fragments:
                print(f"相关片段: {fragments}")
            else:
                print("无高亮片段")


def index_maintenance():
    """索引维护操作"""

    # 1. 合并索引段（优化性能）
    ix = open_dir("search_index")
    writer = ix.writer()
    writer.commit(optimize=True)  # 合并小段为更大段
    print("索引已优化")

    # 2. 删除文档
    writer = ix.writer()
    writer.delete_by_term("path", "/doc/python-intro")  # 根据唯一字段删除
    writer.commit()
    print("文档已删除")

    # 3. 统计信息
    print(f"\n索引统计:")
    print(f"文档数: {ix.doc_count()}")

    # 4. 备份
    import shutil
    backup_dir = "search_index_backup"
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    shutil.copytree("search_index", backup_dir)
    print(f"索引已备份到: {backup_dir}")