#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
import os

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

def change_list(my_list: list):
    my_list.append("append_txt_in_change_list")

def change_txt(source: str):
    source += "append_txt_in_change_txt"


if __name__ =="__main__":
    from langgraph.graph import StateGraph, MessagesState, START, END
    def mock_llm(state: MessagesState):
        return {"messages": [{"role": "ai", "content": "hello world"}]}
    graph = StateGraph(MessagesState)
    graph.add_node(mock_llm)
    graph.add_edge(START, "mock_llm")
    graph.add_edge("mock_llm", END)
    graph = graph.compile()

    graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
    # answer = "origin_txt"
    # change_txt(answer)
    # logger.info(f"changed_txt:{answer}")
    # my_list = ["origin_item"]
    # change_list(my_list)
    # logger.info(f"changed_list:{my_list}")