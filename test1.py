#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict
import logging
from pathlib import Path

from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain.chains import RetrievalQA
from langchain_chroma import Chroma
class VectorStoreQA:
    def __init__(self,
                 model_name: str = "deepseek-r1",
                 embedding_model: str = "nomic-embed-text:latest",
                 temperature: float = 0.5,
                 k: int = 4):
        """
        初始化 QA 系统
        
        Args:
            model_name: LLM 模型名称
            embedding_model: 嵌入模型名称
            temperature: LLM 温度参数
            k: 检索返回的文档数量
        """
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.k = k
        # 初始化 LLM
        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature,
        )
        
        # 初始化 embeddings
        self.embeddings = OllamaEmbeddings(model=embedding_model)
        
        # 初始化向量存储
        self.vector_store = Chroma(embedding_function=self.embeddings)
        
        # 初始化 prompt 模板
        # self.prompt = ChatPromptTemplate.from_messages([
        #     ("system", """你的任务是且只基于提供的上下文信息回答用户问题。要求：1. 回答要准确、完整，并严格基于上下文信息2. 如果上下文信息不足以回答问题，不要编造信息和联想，直接说：在知识库中我找不到相关答案3. 采用结构化的格式组织回答，便于阅读"""),
        #     ("user", """上下文信息：
        #     {context}
            
        #     用户问题：{question}
            
        #     请提供你的回答：""")
        # ])
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """上下文中没有相关资料的不要编造信息、不要从你历史库中搜索，直接说：在知识库中我找不到相关答案。"""),
            ("user", """上下文信息：{context}
            用户问题：{question}
            请提供你的回答：""")
        ])
            
 
    def load_documents(self, file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        """
        加载并处理文本文档
        
        Args:
            file_path: 文本文件路径
            chunk_size: 文档分块大小
            chunk_overlap: 分块重叠大小
        """
        try:
            # 验证文件
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 加载文档
            loader = TextLoader(str(path))
            docs = loader.load()
            
            # 文档分块
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            splits = text_splitter.split_documents(docs)
            
            # 添加到向量存储
            self.vector_store.add_documents(documents=splits)
            self.logger.info(f"成功加载文档: {file_path}")
            
        except Exception as e:
            self.logger.error(f"文档处理错误: {str(e)}")
            raise
 
    def get_answer(self, question: str) -> BaseMessage:
        """
        获取问题的答案
        Args:
            question: 用户问题
        Returns:
            包含答案的字典
        """
        # 使用similarity_search_with_score方法获取文档和分数  
        docs_and_scores = self.vector_store.similarity_search_with_score(  
            query=question,  
            k=self.k
        )  
        
        # 打印每个文档的内容和相似度分数  
        print("\n=== 检索到的相关文档 ===")  
        for doc, score in docs_and_scores:  
            print(f"\n相似度分数: {score:.4f}")  # 保留4位小数  
            print(f"文档内容: {doc.page_content}")  
            print(f"元数据: {doc.metadata}")  # 如果需要查看文档元数据  
            print("-" * 50)  # 分隔线  
 
        # 提取文档内容用于后续处理  
        context = "\n\n".join(doc.page_content for doc, _ in docs_and_scores)  
        # 打印完整的prompt内容  
        print("\n=== 实际发送给模型的Prompt ===")  
        formatted_prompt = self.prompt.format(  
            question=question,  
            context=context  
        )  
        print(formatted_prompt)  
        print("=" * 50)  
        # docs = self.retriever.get_relevant_documents(question)  
        # 将文档内容合并为上下文  
        # context = "\n\n".join(doc.page_content for doc in docs)  
        # print(context)
        # 创建chain并调用
        chain = self.prompt | self.llm  
        response = chain.invoke({  
            "question": question,  
            "context": context  
        })  
        return response
    def clear_vector_store(self):
        """清空向量存储"""
        try:
            self.vector_store.delete_collection()
            self.vector_store = Chroma(embedding_function=self.embeddings)
            self.logger.info("已清空向量存储")
        except Exception as e:
            self.logger.error(f"清空向量存储时发生错误: {str(e)}")
            raise
 
# 使用示例
if __name__ == "__main__":
    # 初始化 QA 系统
    qa_system = VectorStoreQA(
        model_name="deepseek-r1",
        k=4
    )
    
    # 加载文档
    qa_system.load_documents("/tmp/1.txt")
    
    # 提问
    question = "my question is？"
    result = qa_system.get_answer(question)
    print(result)
