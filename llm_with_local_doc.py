#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM

import logging.config

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)


def req_with_vector_db(question: str) -> str:
    """
    加载本地矢量数据库文件, 调用 LLM API, 进行 RAG, 输出结果
    """
    embedding_model = "../bge-large-zh-v1.5"
    api_url = "http://127.0.0.1:11434"
    api_key = "12345"
    faiss_index = "./faiss_index"

    # llm_name = "llama3.1:8b"
    # llm_name = "llama3.2:3b-text-q5_K_M"
    llm_name = "deepseek-r1:7b"
    remote_llm_name = "deepseek-r1"
    # for test purpose only, read index from local file
    logger.info("embedding_model: {}".format(embedding_model))
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model, cache_folder='./bge-cache')
    logger.info("try to load index from local file")
    loaded_index = FAISS.load_local(faiss_index, embeddings,
                                    allow_dangerous_deserialization=True)
    # loaded_index = SQLiteVSS.create_connection(db_file="/sqlite/vss.db")
    logger.info("load index from local file finish")

    # 创建远程 Ollama API代理
    logger.info("get remote llm agent")
    # 可调用无需 api_key 的model
    llm = OllamaLLM(model=llm_name, base_url=api_url)
    doc = loaded_index.similarity_search_with_relevance_scores(question)
    [documents[i] for i in doc[0]]
    logger.info("retrieved doc is: ".format(doc))
    # 调用需要 api_key 的 model
    # llm = ChatOpenAI(api_key=api_key, base_url=api_url, http_client=httpx.Client(verify=False), model=remote_llm_name)
    # 创建检索问答链
    logger.info("build retrieval")
    system_prompt = (
        "根据提供的背景信息回答问题."
        "如果你不知道答案，就说你不知道."
        "回答内容要精炼，最多给出三句话."
        "Context: {context}"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(doc.as_retriever(), question_answer_chain)
    logger.info("invoke retrieval {} to uri {}".format(question, api_url))
    result = chain.invoke({"input": question})
    # 提问
    answer = result["result"]
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
