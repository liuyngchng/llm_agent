#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from semantic_search import get_vector_db

import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)
model_name = "deepseek-r1:7b"
api_url = "http://127.0.0.1:11434"


def req_with_vector_db(question: str) -> str:
    logger.info("load index from local file finish")
    docs_with_scores = get_vector_db().similarity_search_with_relevance_scores(question, k=2)

    # 输出结果和相关性分数
    # for doc, score in docs_with_scores:
    #     print(f"[相关度：{score:.2f}] {doc.page_content[:200]}...")
    # 构建增强提示
    template = """基于以下上下文：
            {context}
            
            回答：{question}"""
    prompt = ChatPromptTemplate.from_template(template)

    model = ChatOllama(model=model_name, base_url=api_url)
    chain = prompt | model
    logger.info("submit user question in LLM: {}".format(question))
    response = chain.invoke({
        "context": "\n\n".join([doc.page_content for doc, score in docs_with_scores]),
        "question": question
    })
    # 提问
    answer = response.content
    logger.info("answer is {}".format(answer))
    return answer


def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    my_question = "户内拆改迁移服务该怎么做?"
    logger.info("invoke question: {}".format(my_question))
    answer = req_with_vector_db(my_question)
    logger.info("answer is {}".format(answer))


if __name__ == '__main__':
    test_req()
