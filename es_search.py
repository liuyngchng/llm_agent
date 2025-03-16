#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langchain_community.vectorstores import ElasticVectorSearch
from langchain_openai import OpenAIEmbeddings

embedding = OpenAIEmbeddings()
elastic_host = "http://127.0.0.1"
elasticsearch_url = f"https://username:password@{elastic_host}:9200"
elastic_vector_search = ElasticVectorSearch(
    elasticsearch_url=elasticsearch_url,
    index_name="test_index",
    embedding=embedding
)
ElasticVectorSearch.from_documents(batch_docs, embedding, elasticsearch_url=elasticsearch_url, index_name="test_index")
