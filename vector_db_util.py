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

import logging.config

embedding_model = "../bge-large-zh-v1.5"
vector_db = "./faiss_index"

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def process_doc(documents: list[Document]) -> None:
    """
    process a Document list object, a common tools
    :param documents: a Document list
    """
    logger.info(f"loaded {len(documents)} documents, files_name_list_as_following")
    for doc in documents:
        logger.info(f"{doc.page_content}")
    logger.info("split doc")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=['\n\n', '。', '！', '？', '；', '...']
    )
    texts = text_splitter.split_documents(documents)
    logger.info(f"load_embedding_model: {embedding_model}")
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        cache_folder='./bge-cache',
        model_kwargs={'device': 'cpu', 'num_threads': 4}
    )
    logger.info("build_vector_db")
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
    cleaned_docs = []
    for doc in docs:
        # 合并被换行符打断的句子
        text = doc.page_content.replace('\n', '')
        cleaned_docs.append(Document(page_content=text))
    logger.info(f"local_file_cleaned")
    process_doc(cleaned_docs)


def vector_txt(txt_file: str):
    """
    vector a txt file.
    :param txt_file: a text file full path
    """
    logger.info(f"load_local_doc {txt_file}")
    loader = TextLoader(txt_file, encoding='utf8')
    docs = loader.load()
    process_doc(docs)

def vector_pdf_dir(pdf_dir: str):
    """
    :param pdf_dir: a directory with all pdf file
    """

    # 加载知识库文件
    logger.info(f"load local file from {pdf_dir}")
    loader = DirectoryLoader(
        path=pdf_dir, recursive=True, load_hidden=False,
        loader_cls=TextLoader, glob="**/*.java"
    )
    documents = loader.load()
    logger.info("loaded {} documents, files_name_list_as_following".format(len(documents)))
    for doc in documents:
        #print(f"\t{doc.metadata['page_number']}\t{doc.page_content}")
        print(f"{doc.page_content}")

    # 将文档分割成块
    logger.info("split doc")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=10, separators=['。','\n\n'])
    texts = text_splitter.split_documents(documents)

    # 加载Embedding模型，进行自然语言处理
    logger.info(f"load embedding model: {embedding_model}")
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        cache_folder='./bge-cache',
        model_kwargs={'device': 'cpu'}
    )

    # 创建向量数据库
    logger.info("build vector db")
    db = FAISS.from_documents(texts, embeddings)
    logger.info("start_save_vector_db_to_local_txt_file")
    db.save_local(vector_db)
    logger.info("vector_db_saved_to_local_txt_file {}".format(vector_db))


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
    # vector_txt("./1.txt")
    vector_pdf("/home/rd/doc/文档生成/knowledge_base/1.pdf")
    # result = search("分析本系统需遵循的国家合规性要求，包括但不限于网络安全法、等级保护要求、数据安全法，密码法，个人信息保护规范等", "faiss_index")
    # logger.info(f"score:{result[0][1]}, \nsource_file:{result[0][0].metadata["source"]}, \ncontent: {result[0][0].page_content}")