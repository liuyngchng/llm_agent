#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import sqlite3
import httpx
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from typing import Any
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from typing import Annotated, Literal
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field, SecretStr
from typing_extensions import TypedDict
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
import logging.config

from common import db_util
from common.sys_init import init_yml_cfg

"""
curl -s --noproxy '*' -X POST http://127.0.0.1:11434/api/chat -d '{
    "model": "llama3.1:8b",
    "messages": [
        {"role": "user", "content": "你好，我想订一张机票。"}
        ],
    "stream":false
}' | jq
"""

logging.config.fileConfig('../../logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

# 支持 tools 调用
#llm_model_name="llama3.1:8b"

my_cfg = init_yml_cfg()

model_name = my_cfg['api']['llm_model_name']
api_url = my_cfg['api']['llm_api_uri']
api_key = SecretStr(my_cfg['api']['llm_api_key'])
db_file = my_cfg['db']['name']
db_uri = db_util.get_db_uri(my_cfg)
question = "查询山东天然气销售分公司2025年的订单详细信息"


def get_llm(is_remote: False):
    if is_remote:
        if "https" in api_url:
            model = ChatOpenAI(api_key=api_key, base_url=api_url,
                               http_client=httpx.Client(verify=False), model=model_name, temperature=0)
        else:
            model = ChatOllama(model=model_name, base_url=api_url, temperature=0)
    else:
        model = ChatOllama(model=model_name, base_url=api_url, temperature=0)
    return model

# Define the state for the agent
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# Describe a tool to represent the end state
class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""

    final_answer: str = Field(..., description="The final answer to the user")


def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
    # print("input_in_create_tool_node_with_fallback", tools)
    create_tool_node_with_fallback_result = ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )
    # print("output_in_create_tool_node_with_fallback", create_tool_node_with_fallback_result)
    return create_tool_node_with_fallback_result

# Add a node for the first tool call
def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    # print("input_in_first_tool_call:", state)
    first_tool_call_result= {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "sql_db_list_tables",
                    }
                ],
            )
        ]
    }
    # print("output_in_first_tool_call:", first_tool_call_result)
    return first_tool_call_result

# def node_test(state: State) -> dict[str, list[AIMessage]]:
#     print("########state_in_node_is######## {}".format(state))
#     return {"messages": ["this is a test message"]}

def model_get_schema_call(state: State) -> dict[str, list[AIMessage]]:
    # print("input_in_model_get_schema_call:", state)
    # Add a node for a model to choose the relevant tables based on the msg and available tables
    # just for localhost call
    # model_get_schema = ChatOllama(model="llama3.1:8b", base_url=api_url, temperature=0).bind_tools(
    #     [get_schema_tool]
    # )
    model_get_schema = get_llm(is_remote=True).bind_tools(
            [get_schema_tool]
    )

    logger.debug(f"model_get_schema_invoke({state["messages"][-1].content})")
    model_get_schema_call_result = {
        "messages": [model_get_schema.invoke(state["messages"][-1].content)]
    }
    logger.debug(f"output_in_model_get_schema_call:{model_get_schema_call_result}")
    return model_get_schema_call_result

def model_check_query(state: State) -> dict[str, list[AIMessage]]:
    """
    Use this tool to double-check if your query is correct before executing it.
    """
    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}

def query_gen_node(state: State):
    message = query_gen.invoke(state)

    # Sometimes, the LLM will hallucinate and call the wrong tool. We need to catch this and return an error message.
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Remember to only call SubmitFinalAnswer to submit the final answer. Generated queries should be outputted WITHOUT a tool call.",
                        tool_call_id=tc["id"],
                    )
                )
    else:
        tool_messages = []
    return {"messages": [message] + tool_messages}

# Define a conditional edge to decide whether to continue or end the workflow
def should_continue(state: State) -> Literal[END, "correct_query", "query_gen"]:
    messages = state["messages"]
    # print("messages_in_should_continue: {}".format(messages))
    last_message = messages[-1]
    return END;
    # If there is a tool call, then we finish
    # if getattr(last_message, "tool_calls", None):
    #     return END
    # if last_message.content.startswith("Error:"):
    #     return "query_gen"
    # else:
    #     return "correct_query"

if __name__ == "__main__":
    """
    A SQL agent demo.
    give LLM a JDBC uri, let it get the database and table schema.
    LLM read the database schema, and get the information.
    a msg input about the information in DB will be turned into a SQL query,
    then data retrieved from DB returned back from LLM to user.
    """
    # use SQLite DB
    db = SQLDatabase.from_uri(db_uri)

    # use MySQL DB
    # db_user = "test"
    # db_password = "test"
    # db_host = "127.0.0.1"
    # db_name = "test"
    # db = SQLDatabase.from_uri(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")
    logger.debug("db dialect is: {}".format(db.dialect))
    logger.debug("db tables is: {}".format(db.get_usable_table_names()))

    # just for test purpose only to check whether DB Uri is OK.
    # db.run("SELECT * FROM customer_info LIMIT 10;")

    toolkit = SQLDatabaseToolkit(db=db,
                                 # llm=ChatOllama(model="llama3.1:8b", base_uri=""),
                                 llm = get_llm(is_remote=True),

                                 )
    toolkit_tools = toolkit.get_tools()

    list_tables_tool = next(tool for tool in toolkit_tools if tool.name == "sql_db_list_tables")
    get_schema_tool = next(tool for tool in toolkit_tools if tool.name == "sql_db_schema")

    # for test list_tables_tool
    # print("test list_tables_tool")
    # print(list_tables_tool.invoke(""))

    #for test get_schema_tool
    #print("test get_schema_tool")
    #print(get_schema_tool.invoke("order_info"))

    # for test db_query_tool
    # print("test db_query_tool")
    # print(db_query_tool.invoke("SELECT * FROM customer_info LIMIT 3;"))

    query_check_system = """You are a SQLite expert with a strong attention to detail.
    
    You are a helpful assistant with tool calling capabilities.
    
    When you receive a tool call response, use the output to format an answer to the orginal user msg.

    Double check the SQLite query for common mistakes, including:
    - Using NOT IN with NULL values
    - Using UNION when UNION ALL should have been used
    - Using BETWEEN for exclusive ranges
    - Data type mismatch in predicates
    - Properly quoting identifiers
    - Using the correct number of arguments for functions
    - Casting to the correct data type
    - Using the proper columns for joins
    
    If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.
    
    You will call the appropriate tool to execute the query after running this check."""

    query_check_prompt = ChatPromptTemplate.from_messages(
        [("system", query_check_system), ("placeholder", "{messages}")]
    )
    # query_check = query_check_prompt |ChatOllama(model="llama3.1:8b", temperature=0).bind_tools(
    #     [db_query_tool], tool_choice="required"
    # )

    query_check = query_check_prompt | get_llm(is_remote=True).bind_tools(
        [db_query_tool], tool_choice="required"
    )

    # for test purpose query_check only
    # q_c_r = query_check.invoke({"messages": [("user", "SELECT * FROM customer_info LIMIT 10;")]})
    # print("test query_check: {}".format(q_c_r))

    # Define a new graph
    workflow = StateGraph(State)
    workflow.add_node("first_tool_call", first_tool_call)

    # Add nodes for the first two tools
    workflow.add_node(
        "list_tables_tool", create_tool_node_with_fallback([list_tables_tool])
    )

    # a test node for check node status
    # workflow.add_node("node_check_call", node_test)


    workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))


    workflow.add_node("model_get_schema",model_get_schema_call)

    # Add a node for a model to generate a query based on the msg and schema
    query_gen_system = """You are a SQLite database expert with a strong attention to detail.
    
    When you receive a tool call response, use the output to format an answer to the orginal user msg.

    You are a helpful assistant with tool calling capabilities.

    Given an input msg, output a syntactically correct SQLite query to run, then look at the results of the query and return the answer.
    
    DO NOT call any tool besides SubmitFinalAnswer to submit the final answer.
    
    When generating the query:
    
    Output the SQL query that answers the input msg without a tool call.
    
    Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
    You can order the results by a relevant column to return the most interesting examples in the database.
    Never query for all the columns from a specific table, only ask for the relevant columns given the msg.
    
    If you get an error while executing a query, rewrite the query and try again.
    
    If you get an empty result set, you should try to rewrite the query to get a non-empty result set. 
    NEVER make stuff up if you don't have enough information to answer the query... just say you don't have enough information.
    
    If you have enough information to answer the input msg, simply invoke the appropriate tool to submit the final answer to the user.
    
    DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database."""
    query_gen_prompt = ChatPromptTemplate.from_messages(
        [("system", query_gen_system), ("placeholder", "{messages}")]
    )
    # query_gen = query_gen_prompt | ChatOllama(model="llama3.1:8b", temperature=0).bind_tools(
    #     [SubmitFinalAnswer]
    # )
    query_gen = query_gen_prompt | get_llm(is_remote=True).bind_tools(
        [SubmitFinalAnswer]
    )

    workflow.add_node("query_gen", query_gen_node)

    # Add a node for the model to check the query before executing it
    workflow.add_node("correct_query", model_check_query)

    # Add node for executing the query
    workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))

    # Specify the edges between the nodes
    workflow.add_edge(START, "first_tool_call")
    workflow.add_edge("first_tool_call", "list_tables_tool")

    workflow.add_edge("list_tables_tool", "model_get_schema")
    workflow.add_edge("model_get_schema", "get_schema_tool")
    workflow.add_edge("get_schema_tool", "query_gen")
    workflow.add_conditional_edges(
        "query_gen",
        should_continue,
    )
    workflow.add_edge("correct_query", "execute_query")
    workflow.add_edge("execute_query", "query_gen")

    # Compile the workflow into a runnable
    app = workflow.compile()
    img_name = "{}.png".format(__file__.split("/")[-1])
    #print("save the graph to local txt_file {}".format(img_name))
    #app.get_graph().draw_png(img_na信息me)
    user_question = question
    logger.info("msg is: {}".format(user_question))
    messages = app.invoke(
        {"messages": [("user", user_question)]}, {"recursion_limit":100 }
    )
    # json_str = messages["messages"][-1].tool_calls[0]["args"]["final_answer"]
    json_str = messages["messages"][-1].content
    logger.debug(f"SQL is : {json_str}")
    # answer = db_query_tool.invoke(json_str)
    # logger.info(f"answer is: {answer}")
    # del db
    conn = sqlite3.connect(db_file)
    answer = db_util.sqlite_output(conn, json_str)



    # for event in app.stream(
    #         {"messages": [("user", user_question)]}, {"recursion_limit":10 }
    # ):
    #     print(event)
