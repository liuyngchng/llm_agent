#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from langchain_community.vectorstores import ElasticVectorSearch
from langchain_openai import OpenAIEmbeddings


if __name__ == "__main__":
    embedding = OpenAIEmbeddings()
    elastic_host = "http://127.0.0.1"
    elasticsearch_url = f"https://username:password@{elastic_host}:9200"
    elastic_vector_search = ElasticVectorSearch(
        elasticsearch_url=elasticsearch_url,
        index_name="test_index",
        embedding=embedding
    )
    batch_docs = []
    ElasticVectorSearch.from_documents(batch_docs, embedding, elasticsearch_url=elasticsearch_url, index_name="test_index")
