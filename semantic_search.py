from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import logging.config

# 加载配置
logging.config.fileConfig('logging.conf')

# 创建 logger
logger = logging.getLogger(__name__)

if __name__ == "__main__":

    # 读取PDF文档
    doc = "./1.pdf"
    loader = PyPDFLoader(doc)
    pages = loader.load_and_split()

    # 分割文本
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(pages)

    # 创建向量存储
    embeddings = HuggingFaceEmbeddings(model_name="../bge-large-zh-v1.5")
    db = FAISS.from_documents(texts, embeddings)

    # 语义搜索
    query = "your question?"
    logger.info("similarity_search {} in doc {}".format(query, doc))
    # 搜索部分
    docs_with_scores = db.similarity_search_with_relevance_scores(query, k=2)

    # 输出结果和相关性分数
    # for doc, score in docs_with_scores:
    #     print(f"[相关度：{score:.2f}] {doc.page_content[:200]}...")
    # 构建增强提示
    template = """基于以下上下文：
    {context}
    
    回答：{question}"""
    prompt = ChatPromptTemplate.from_template(template)

    # 调用Ollama
    model = ChatOllama(model="deepseek-r1:7b")
    chain = prompt | model
    logger.info("submit user question in LLM: {}".format(query))
    response = chain.invoke({
        "context": "\n\n".join([doc.page_content for doc, score  in docs_with_scores]),
        "question": query
    })

    logger.info("answer： {}".format(response.content))
