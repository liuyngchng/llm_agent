#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langgraph.graph import StateGraph
from langgraph.constants import START, END
import graphviz
from graphviz import Digraph
def chat_bot():
    return {"messages": ["this is a test"]}

def compiled_graph_to_dot(graph) -> str:
    dot = Digraph()
    # 添加节点 (假设graph.nodes可遍历)
    for node in graph.nodes:
        dot.node(str(node), f"{node}")
    # 添加边 (假设graph.edges包含元组)
    for src, dst in graph.edges:
        dot.edge(str(src), str(dst), xlabel=graph.edges.get((src, dst), ""))
    return dot.source


def get_graph():
    # 创建状态图
    sg = StateGraph(dict)
    # 定义图的入口和边
    sg.add_node("chatbot", chat_bot)
    sg.add_edge(START, "chatbot")
    sg.add_edge("chatbot", END)

    # 编译图
    graph = sg.compile()

    # 使用Graphviz渲染并保存图形
    dot = graph.to_dot()  # 将状态图转换为Graphviz的DOT格式
    # 保存为PNG文件
    graphviz.Source(dot).render(__name__, format='png', cleanup=True)


if __name__ == "__main__":
    """
    a stage grave output test which is not finished yet.
    """
    get_graph()
