#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langgraph.graph import StateGraph, START, END
from langchain_ollama import OllamaLLM
from langgraph.graph.state import CompiledStateGraph

llm = OllamaLLM(model="llama3.1", base_url='http://127.0.0.1:11434')


# 定义图节点
def chatbot(d):
    return {"messages": [llm.invoke(d)]}


def get_graph() -> "CompiledStateGraph":
    # 创建一个 StateGraph 对象
    graph_builder = StateGraph(dict)
    # 定义图的入口和边
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)

    # 编译图
    graph = graph_builder.compile()
    return graph


if __name__ == "__main__":
    """
    output a graph with localized graphviz library instead of online API
    """
    file_name = "{}.png".format(__file__.split("/")[-1])
    my_graph = get_graph()
    print('save graph as png format to local file "{}"'.format(file_name))
    my_graph.get_graph().draw_png(file_name)

    # user_input = '介绍你自己的模型名称、量化参数、部署需要的资源等'
    # print("execute graph for user input: {}".format(user_input))
    # for event in my_graph.stream(user_input):
    #     for value in event.values():
    #         print("Assistant:", value["messages"])
