#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def embed(model, documents):
    """

    embedding document
    """

    # 示例文档
    print(documents)

    # 生成嵌入向量
    doc_embeddings = model.encode(documents)
    create_index = faiss.IndexFlatL2(doc_embeddings.shape[1])
    create_index.add(np.array(doc_embeddings).astype('float32'))
    # 保存索引到文件
    faiss.write_index(create_index, "my_index.faiss")


# 检索函数
def search(embed_model, documents, query, k=2):
    """
    search key words in embedding index
    :param embed_model:
    :param documents:
    :param query:
    :param k:
    :return:
    """
    loaded_index = faiss.read_index("my_index.faiss")
    query_embedding = embed_model.encode([query])
    distances, indices = loaded_index.search(query_embedding, k)
    return [documents[i] for i in indices[0]]


if __name__ == "__main__":
    # 初始化模型
    # model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    my_model = SentenceTransformer("../bge-large-zh-v1.5")
    my_doc = [
        "深度学习需要大量计算资源",
        "Python支持多种编程范式",
        "FAISS是高效的相似度搜索库",
        "自然语言处理处理文本数据",
        "这条数据万面没有任何含义",
        "含义的意思就是没有任何含义"
    ]
    embed(my_model, my_doc)

    result = search(my_model, my_doc, "文本分析")
    print("search result is {}".format(result))
