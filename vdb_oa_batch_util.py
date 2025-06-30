#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通过调用远程的 embedding API，将本地文档向量化，形成矢量数据库文件，用于进行向量检索
for OpenAI compatible remote API
"""
import httpx
import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader, UnstructuredPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
import logging.config
from openai import OpenAI
from sys_init import init_yml_cfg
from tqdm import tqdm


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class RemoteEmbeddings(Embeddings):  # 适配器类
    def __init__(self, client):
        self.client = client

    def embed_documents(self, texts):
        return [self._get_embedding(t) for t in texts]

    def embed_query(self, text):
        return self._get_embedding(text)

    def _get_embedding(self, text):
        resp = self.client.embeddings.create(model="bge-m3", input=text)
        return resp.data[0].embedding


def process_doc(documents: list[Document], vector_db: str, sys_cfg:dict,
                chunk_size=500, chunk_overlap=50, batch_size=10) -> None:
    logger.info(f"loaded {len(documents)} documents, files_name_list_as_following")
    for doc in documents:
        logger.info(f"file:{doc.metadata['source']}")
    logger.info("split_doc")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=['\n\n', '。', '！', '？', '；', '...']
    )
    doc_list = text_splitter.split_documents(documents)
    logger.info(f"split_doc_finished")
    client = build_client(sys_cfg)
    logger.info(f"init_client_with_config: {sys_cfg}")
    embeddings = RemoteEmbeddings(client)
    logger.info(f"开始向量化处理（批量大小={batch_size}）")
    vectorstore = None

    pbar = tqdm(total=len(doc_list), desc="向量化进度", unit="chunk")
    for i in range(0, len(doc_list), batch_size):
        batch = doc_list[i:i + batch_size]
        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            batch_store = FAISS.from_documents(batch, embeddings)
            vectorstore.merge_from(batch_store)
        pbar.update(len(batch))
        logger.info(f"已处理 {min(i + batch_size, len(doc_list))}/{len(doc_list)} 文本块")
    pbar.close()
    logger.info(f"向量数据库构建完成，保存到 {vector_db}")
    # vectorstore = FAISS.from_documents(doc_list, embeddings)
    # logger.info(f"vector_store_finished, save_vector_to_local {vector_db}")
    vectorstore.save_local(vector_db)
    logger.info(f"save_vector_to_local {vector_db}")

def build_client(sys_cfg: dict):
    return OpenAI(
        base_url= sys_cfg['llm_api_uri'],   # "https://myhost/v1",
        api_key= sys_cfg['llm_api_key'],    # "sk-xxxxx",
        http_client=httpx.Client(verify=False),
    )

def load_vector_db(vector_db: str, sys_cfg: dict):
    client = build_client(sys_cfg)
    embeddings = RemoteEmbeddings(client)
    return FAISS.load_local(vector_db, embeddings, allow_dangerous_deserialization=True)

def search_similar_text(query: str, score_threshold: float, vector_db, sys_cfg: dict, top_k=3):
    db = load_vector_db(vector_db, sys_cfg)
    return db.similarity_search_with_relevance_scores(query,k= top_k, score_threshold = score_threshold)


def vector_txt_file(txt_file: str, vector_db_dir: str, sys_cfg:dict):
    logger.info(f"start_load_txt_doc {txt_file}")
    loader = TextLoader(txt_file, encoding='utf8')
    docs = loader.load()
    process_doc(docs, vector_db_dir, sys_cfg)

def vector_pdf_file(pdf_file: str, vector_db_dir: str, sys_cfg:dict):
    logger.info(f"start_load_pdf_doc {pdf_file}")
    loader = UnstructuredPDFLoader(pdf_file, encoding='utf8')
    docs = loader.load()
    process_doc(docs, vector_db_dir, sys_cfg)

def vector_txt_dir(txt_dir: str, vector_db_dir: str, sys_cfg: dict):  # 修改函数
    logger.info(f"start_load_txt_dir: {txt_dir}")
    loader = DirectoryLoader(
        path=txt_dir,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf8'},
        silent_errors=True
    )
    documents = loader.load()
    process_doc(documents, vector_db_dir, sys_cfg)

def vector_pdf_dir(pdf_dir: str, vector_db_dir: str, sys_cfg: dict):
    """
    :param pdf_dir: a directory with all pdf file
    :param sys_cfg: system configuration info.
    """

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
    process_doc(documents, vector_db_dir, sys_cfg)


def search_txt(txt: str, vector_db_dir: str, score_threshold: float, sys_cfg: dict, txt_num: int) -> str:
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
    vector_txt_file("/home/rd/doc/文档生成/knowledge_base/1.txt", my_vector_db_dir, my_cfg['api'])
    # vector_txt_dir("/home/rd/doc/文档生成/knowledge_base", my_vector_db_dir, my_cfg['api'])
    # vector_pdf_file("/home/rd/doc/文档生成/knowledge_base/1.pdf", my_vector_db_dir, my_cfg['api'])
    # vector_pdf_dir("/home/rd/doc/文档生成/knowledge_base", my_vector_db_dir, my_cfg['api'])
    q = "危化品车辆监控涉及哪些内容"
    logger.info(f"start_search: {q}")
    results = search_txt(q, my_vector_db_dir, 0.5, my_cfg['api'], 3)
    logger.info(f"result: {results}")
