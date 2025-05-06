#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将本地文档进行向量化，形成矢量数据库文件，用于 LLM 进行 RAG
    需要下载 nltk data
    git clone git@github.com/nltk/nltk_data.git
    进行分词
"""

from langchain_community.document_loaders import TextLoader, UnstructuredPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import DirectoryLoader
from langchain_core.documents import Document
from os import cpu_count
from os.path import exists

import logging.config
import re

embedding_model = "../bge-large-zh-v1.5"
vector_db_dir = "./faiss_index"

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def process_doc(documents: list[Document], embedding: str, vector_db: str, chunk_size=500, chunk_overlap=50) -> None:
    """
    process a Document list object, a common tools
    :param documents: A Document list
    :param embedding: A embedding model name
    :param vector_db: A vector db dir name
    :param chunk_size: A text chunk size of each batch
    :param chunk_overlap: text can be overlapped between chunks
    """
    logger.info(f"loaded {len(documents)} documents, files_name_list_as_following")
    cleaned_docs = []
    for doc in documents:
        cleaned_txt = clean_line_breaks(doc.page_content)
        cleaned_docs.append(Document(
            page_content=cleaned_txt,
            metadata = doc.metadata
        ))
    logger.info(f"local_file_cleaned")
    for doc in cleaned_docs:
        logger.info(f"{doc.page_content}")
    logger.info("split doc")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=['\n\n', '。', '！', '？', '；', '...']
    )
    texts = text_splitter.split_documents(cleaned_docs)
    logger.info(f"load_embedding_model: {embedding}")
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding,
        cache_folder='./bge-cache',
        model_kwargs={'device': 'cpu'}
    )
    logger.info("build_vector_db")
    # if exists(vector_db):
    #     db = FAISS.load_local(vector_db, embeddings, allow_dangerous_deserialization=True)
    #     db.add_documents(texts)
    # else:
    #     db = FAISS.from_documents(texts, embeddings)
    db = FAISS.from_documents(texts, embeddings)
    logger.info("localize_vector_db")
    db.save_local(vector_db)
    logger.info(f"localized_vector_db_file_dir {vector_db}")


def vector_pdf(pdf_file: str):
    """
    vector pdf file
    :param pdf_file: a pdf file full path
    """
    logger.info(f"load_local_file {pdf_file}")
    loader = UnstructuredPDFLoader(
        pdf_file,
        strategy="fast",        # 快捷模式
        # strategy="hi_res",      # hi_res模式下需要 YOLOX 模型分析版面
        # mode="paged",         # one document per page
        num_workers=4,          # multi-thread
    )
    docs = loader.load()
    logger.info(f"local_file_loaded")
    process_doc(docs, embedding_model, vector_db_dir)


def clean_line_breaks(text, line_width=30, threshold=0.8) -> str:
    """
    :param text: 原始文本
    :param line_width: 预估行宽（中文字符数）
    :param threshold: 换行阈值（0.8表示达到80%行宽则视为自动换行）
    """
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # 中文字符算1，忽略标点影响
        effective_len = len([c for c in line if '\u4e00' <= c <= '\u9fff'])
        if effective_len == 0:
            continue
        if effective_len >= line_width * threshold:
            cleaned.append(line.strip())
        else:
            cleaned.append(line + '\n')
    return ''.join(cleaned).replace('\n\n', '\n')

def vector_txt(txt_file: str):
    """
    vector a txt file.
    :param txt_file: a text file full path
    """
    logger.info(f"load_local_doc {txt_file}")
    loader = TextLoader(txt_file, encoding='utf8')
    docs = loader.load()
    # process_doc(docs)
    process_doc(docs, embedding_model, vector_db_dir)


def vector_pdf_dir(pdf_dir: str):
    """
    :param pdf_dir: a directory with all pdf file
    """

    # 加载知识库文件
    logger.info(f"load local file from {pdf_dir}")
    loader = DirectoryLoader(
        path=pdf_dir, recursive=True, load_hidden=False,
        loader_cls=UnstructuredPDFLoader, glob="**/*.pdf"
    )
    documents = loader.load()
    logger.info(f"loaded {len(documents)} documents")
    process_doc(documents, embedding_model, vector_db_dir)

def vector_txt_dir(pdf_dir: str):
    """
    :param pdf_dir: a directory with all pdf file
    """

    # 加载知识库文件
    logger.info(f"load local file from {pdf_dir}")
    loader = DirectoryLoader(
        path=pdf_dir, recursive=True, load_hidden=False,
        loader_cls=TextLoader, glob="**/*.txt"
    )
    docs = loader.load()
    logger.info(f"loaded {len(docs)} documents")
    process_doc(docs, embedding_model, vector_db_dir)


def get_vector_db(db_dir: str) -> FAISS:
    try:
        vector_db = FAISS.load_local(
            db_dir,
            HuggingFaceEmbeddings(model_name=embedding_model, model_kwargs={'device': 'cpu'}),
            allow_dangerous_deserialization=True
        )
        return vector_db
    except Exception as e:
        logger.error("load index failed: {}".format(e))
        raise e

def search(question: str, db_dir: str) -> list[tuple[Document, float]]:
    """
    search user questions in knowledge base,
    submit the search result and user msg to LLM, return the answer
    """
    logger.info(f"sim_search [{question}]")
    docs_with_scores = get_vector_db(db_dir).similarity_search_with_relevance_scores(question, k=5)
    # 输出结果和相关性分数
    # for related_doc, score in docs_with_scores:
    #     logger.debug(f"[相关度：{score:.2f}]\t{related_doc.page_content[:100]}...")
    return docs_with_scores



if __name__ == "__main__":
    """
    read the local document like txt, docx, pdf etc., and embedding the content 
    to a FAISS vector database.
    submit a msg about the local documents to the LLM, let LLM give a response
    that about the documents.
    """
    # os.putenv("CUDA_VISIBLE_DEVICES", "1")
    # a = os.environ.get("CUDA_VISIBLE_DEVICES")
    # print(a)
    # os.environ["CUDA_VISIBLE_DEVICES"] = 0
    # vector_txt("/home/rd/doc/文档生成/knowledge_base/1.txt")
    # vector_pdf_dir("/home/rd/doc/文档生成/knowledge_base")
    vector_txt_dir("/home/rd/doc/文档生成/knowledge_base")
    # vector_pdf("/home/rd/doc/文档生成/knowledge_base/1.pdf")
    result = search("分析本系统需遵循的国家合规性要求，包括但不限于网络安全法、等级保护要求、数据安全法，密码法，个人信息保护规范等", "faiss_index")
    logger.info(f"score:{result[0][1]}, \nsource_file:{result[0][0].metadata["source"]}, \ncontent: {result[0][0].page_content}")