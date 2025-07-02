#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pip install docx2txt python-docx
通过调用远程的 embedding API，将本地文档向量化，形成矢量数据库文件，用于进行向量检索
for OpenAI compatible remote API
通过将大文档分为多个批次，实现实时查看向量化进度，对于大批量文档的向量化比较友好
"""
import httpx
import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader, UnstructuredPDFLoader, UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
import logging.config
from openai import OpenAI
from sys_init import init_yml_cfg
from tqdm import tqdm
from typing import List


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

model="bge-m3"
# model="bce-base"

class RemoteEmbeddings(Embeddings):  # 适配器类
    """
    远程分词客户端
    """
    def __init__(self, client):
        self.client = client

    def embed_documents(self, texts: str):
        return [self._get_embedding(t) for t in texts]

    def embed_query(self, text:str ):
        return self._get_embedding(text)

    def _get_embedding(self, text: str):
        resp = self.client.embeddings.create(model=model, input=text)
        return resp.data[0].embedding


def process_doc(documents: list[Document], vector_db: str, sys_cfg:dict,
                chunk_size=300, chunk_overlap=80, batch_size=10) -> None:
    """
    :param documents: 文档列表
    :param vector_db: 向量数据库文件路径
    :param sys_cfg: 系统配置信息
    :param chunk_size: 文档切分块大小
    :param chunk_overlap: 文档切分块重叠大小
    :param batch_size: 批量处理大小
    :return: None
    """
    logger.info(f"loaded {len(documents)} documents, files_name_list_as_following")
    for doc in documents:
        logger.info(f"file:{doc.metadata['source']}")
    logger.info("split_doc")
    # separators = ['\n\n', '。', '！', '？', '；', '...', '、', '，']
    separators = ['。', '！', '？', '；', '...', '、', '，']
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        keep_separator=False
    )
    doc_list = text_splitter.split_documents(documents)
    with open('chunks.txt', 'w', encoding='utf-8') as f:
        for i, chunk in enumerate(doc_list):
            f.write(f"Chunk {i}, Source: {chunk.metadata['source']}\n")
            f.write(chunk.page_content)
            f.write("\n" + "-" * 50 + "\n")
    logger.info(f"split_doc_finished")
    client = build_client(sys_cfg)
    logger.info(f"init_client_with_config: {sys_cfg}")
    embeddings = RemoteEmbeddings(client)
    len_doc_list = len(doc_list)
    if len_doc_list  == 0:
        logger.error("no_doc_need_process_err")
        return
    logger.info(f"开始向量化处理（批量大小={batch_size}）doc_list, {len_doc_list}")
    vectorstore = None

    pbar = tqdm(total=len(doc_list), desc="文档向量化进度", unit="chunk")
    for i in range(0, len_doc_list, batch_size):
        batch = doc_list[i:i + batch_size]
        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            batch_store = FAISS.from_documents(batch, embeddings)
            vectorstore.merge_from(batch_store)
        pbar.update(len(batch))
        # info = str(pbar)
        # logger.info(info)
        # tqdm.write()
        # pbar.update(1)
    pbar.close()
    logger.info(f"向量数据库构建完成，保存到 {vector_db}")
    # vectorstore = FAISS.from_documents(doc_list, embeddings)
    # logger.info(f"vector_store_finished, save_vector_to_local {vector_db}")
    vectorstore.save_local(vector_db)
    logger.info(f"save_vector_to_local {vector_db}")

def build_client(sys_cfg: dict):
    """
    :param sys_cfg: system configuration info.
    :return: the client
    """
    return OpenAI(
        base_url= sys_cfg['llm_api_uri'],   # "https://myhost/v1",
        api_key= sys_cfg['llm_api_key'],    # "sk-xxxxx",
        http_client=httpx.Client(verify=False),
    )

def load_vector_db(vector_db: str, sys_cfg: dict):
    """
    :param vector_db: the vector db file
    :param sys_cfg: system configuration info.
    :return: the vector db
    """
    client = build_client(sys_cfg)
    embeddings = RemoteEmbeddings(client)
    return FAISS.load_local(vector_db, embeddings, allow_dangerous_deserialization=True)

def search_similar_text(query: str, score_threshold: float, vector_db, sys_cfg: dict, top_k=3):
    """
    :param query: the query text
    :param score_threshold: the score threshold
    :param vector_db: the vector db file
    :param sys_cfg: system configuration info.
    :param top_k: the top k results
    :return: the results
    """
    db = load_vector_db(vector_db, sys_cfg)
    return db.similarity_search_with_relevance_scores(query,k= top_k, score_threshold = score_threshold)


def vector_txt_file(txt_file: str, vector_db_dir: str, sys_cfg:dict, chunk_size=300, chunk_overlap=80):
    """
    :param txt_file: a single txt file
    :param vector_db_dir: the directory to save the vector db
    :param sys_cfg: system configuration info.
    """
    if not os.path.isfile(txt_file):
        raise FileNotFoundError(f"file_not_found_err, {txt_file}")
    logger.info(f"start_load_txt_doc {txt_file}")
    loader = TextLoader(txt_file, encoding='utf8')
    docs = loader.load()
    process_doc(docs, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)

def vector_pdf_file(pdf_file: str, vector_db_dir: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80):
    """
    :param pdf_file: a single pdf file
    :param vector_db_dir: the directory to save the vector db
    :param sys_cfg: system configuration info.
    :param chunk_size: the chunk size
    :param chunk_overlap: the chunk overlap
    """
    if not os.path.isfile(pdf_file):
        raise FileNotFoundError(f"file_not_found_err, {pdf_file}")
    logger.info(f"start_load_pdf_doc {pdf_file}")
    loader = UnstructuredPDFLoader(pdf_file, encoding='utf8')
    docs = loader.load()
    process_doc(docs, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)

def vector_txt_dir(txt_dir: str, vector_db_dir: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80):  # 修改函数
    """
    :param txt_dir: a directory with all txt file
    :param vector_db_dir: the directory to save the vector db
    :param sys_cfg: system configuration info.
    :param chunk_size: the chunk size
    :param chunk_overlap: the chunk overlap
    """
    if not os.path.isdir(txt_dir):
        raise FileNotFoundError(f"txt_dir_not_found_err, {txt_dir}")
    logger.info(f"start_load_txt_dir: {txt_dir}")
    loader = DirectoryLoader(
        path=txt_dir,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf8'},
        silent_errors=True
    )
    documents = loader.load()
    process_doc(documents, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)

def vector_pdf_dir(pdf_dir: str, vector_db_dir: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80):
    """
    :param pdf_dir: a directory with all pdf file
    :param vector_db_dir: the directory to save the vector db
    :param sys_cfg: system configuration info.
    :param chunk_size: the chunk size
    :param chunk_overlap: the chunk overlap
    """
    if not os.path.isdir(pdf_dir):
        raise FileNotFoundError(f"dir_not_found_err, {pdf_dir}")
    # 加载知识库文件
    logger.info(f"start_load_pdf_dir {pdf_dir}")
    loader = DirectoryLoader(
        path=pdf_dir,
        recursive=True,
        load_hidden=False,
        loader_cls=UnstructuredPDFLoader,
        glob="**/*.pdf"
    )
    documents = loader.load()
    process_doc(documents, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)

def vector_docx_file(docx_file: str, vector_db_dir: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80):
    """
    :param docx_file: a single docx file
    :param vector_db_dir: the directory to save the vector db
    :param sys_cfg: system configuration info.
    :param chunk_size: the chunk size
    :param chunk_overlap: the chunk overlap
    处理单个DOCX文档
    """
    if not os.path.isfile(docx_file):
        raise FileNotFoundError(f"file_not_found_err, {docx_file}")
    logger.info(f"start_load_docx_file {docx_file}")
    loader = UnstructuredWordDocumentLoader(docx_file)
    docs = loader.load()
    process_doc(docs, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)


def vector_docx_dir(docx_dir: str, vector_db_dir: str, sys_cfg: dict, chunk_size=300, chunk_overlap=80) -> None:
    """
    :param docx_dir: a directory with all docx file
    :param vector_db_dir: the directory to save the vector db
    :param sys_cfg: system configuration info.
    :param chunk_size: the chunk size
    :param chunk_overlap: the chunk overlap
    """
    if not os.path.isdir(docx_dir):
        raise FileNotFoundError(f"dir_not_found_err, {docx_dir}")
    try:
        logger.info(f"开始加载DOCX文件，目录: {docx_dir}")
        # 初始化文档加载器
        loader = DirectoryLoader(
            path=docx_dir,
            recursive=True,
            glob="**/*.docx",
            # loader_cls=Docx2txtLoader, # type: ignore
            loader_cls=UnstructuredWordDocumentLoader,
            silent_errors=False
        )
        # 加载文档
        documents: List[Document] = loader.load()
        if not documents:
            logger.warning(f"目录中没有找到任何DOCX文件: {docx_dir}")
            return
        logger.info(f"成功加载 {len(documents)} 个文档")
        # 处理文档
        process_doc(documents, vector_db_dir, sys_cfg, chunk_size, chunk_overlap)
    except Exception as e:
        logger.error(f"处理DOCX文件时发生错误: {str(e)}")
        raise

def search_txt(txt: str, vector_db_dir: str, score_threshold: float,
        sys_cfg: dict, txt_num: int) -> str:
    """
    :param txt: the query text
    :param vector_db_dir: the directory to save the vector db
    :param score_threshold: the score threshold
    :param sys_cfg: system configuration info.
    :param txt_num: the number of txt to return
    :return: the results
    """
    search_results = search_similar_text(txt, score_threshold, vector_db_dir, sys_cfg, txt_num)
    all_txt = ""
    for s_r in search_results:
        s_r_txt = s_r[0].page_content.replace("\n", "")
        if "......................." in s_r_txt:
            continue
        # logger.info(f"s_r_txt: {s_r_txt}, score: {s_r[1]}, from_file: {s_r[0].metadata['source']}")
        all_txt += s_r_txt + "\n"
    return all_txt

if __name__ == "__main__":
    os.environ["NO_PROXY"] = "*"  # 禁用代理
    my_cfg = init_yml_cfg()
    my_vector_db_dir = "./faiss_oa_vector"
    # vector_txt_file("/home/rd/doc/文档生成/knowledge_base/1.txt", my_vector_db_dir, my_cfg['api'])
    # vector_txt_dir("/home/rd/doc/文档生成/knowledge_base", my_vector_db_dir, my_cfg['api'])
    # vector_pdf_file("/home/rd/doc/文档生成/knowledge_base/1.pdf", my_vector_db_dir, my_cfg['api'])
    # vector_pdf_dir("/home/rd/doc/文档生成/knowledge_base", my_vector_db_dir, my_cfg['api'])
    # vector_docx_file("/home/rd/doc/文档生成/docx_test/2.docx", my_vector_db_dir, my_cfg['api'])
    vector_docx_dir("/home/rd/doc/文档生成/docx_test", my_vector_db_dir, my_cfg['api'])
    # q = "危化品车辆监控涉及哪些内容"
    q = "阀门控制单元"
    logger.info(f"start_search: {q}")
    results = search_txt(q, my_vector_db_dir, 0.25, my_cfg['api'], 3)
    logger.info(f"result:\n{results}")
