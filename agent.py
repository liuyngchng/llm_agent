#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langgraph.graph import StateGraph, START, END
from langchain_ollama import OllamaLLM

# 初始化模型
llm = OllamaLLM(model="deepseek-r1:7B", base_url='http://127.0.0.1:11434')

    
# 定义图节点
def chatbot(d):
    return {"messages": [llm.invoke(d)]}

if __name__ == "__main__":
    """
    a agent for a LLM ,just define a graph with a single node to chat with ollamaLLM
    the graph for workflow can be extended for other purpose.
    """
    # 创建一个 StateGraph 对象
    graph_builder = StateGraph(dict)
    # 定义图的入口和边
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)

    # 编译图
    graph = graph_builder.compile()

    # 执行图
    user_input = '介绍你自己'
    for event in graph.stream(user_input):
        for value in event.values():
            print("Assistant:", value["messages"])
