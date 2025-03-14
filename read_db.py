#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
详见  https://langchain-ai.github.io/langgraph/tutorials/sql-agent/
"""
from langchain_community.utilities import SQLDatabase
from typing import Any, Annotated

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_ollama import OllamaLLM, ChatOllama

from langchain_core.tools import tool

from langchain_core.prompts import ChatPromptTemplate


def sql_expert(sql: str, llm_name, api_uri):
    query_check_system = """You are a SQL expert with a strong attention to detail.
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

    # query_check = query_check_prompt | ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(
    #     [db_query_tool], tool_choice="required"
    # )
    # query_check.invoke({"messages": [("user", "SELECT * FROM Artist LIMIT 10;")]})

    query_check = query_check_prompt | ChatOllama(model=llm_name, base_url=api_uri).bind_tools(
        [db_query_tool]
    )
    result = query_check.invoke({"messages": [("user", sql)]})
    print("sql_expert: {}".format(result))


@tool
def db_query_tool(query: str, jdbc_url: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    db = SQLDatabase.from_uri(jdbc_url)
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


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


def get_data(jdbc_uri: str):
    db = SQLDatabase.from_uri(jdbc_uri)
    print("db.dialect: {}".format(db.dialect))
    print("db.get_usable_table_names: {}".format(db.get_usable_table_names()))
    # db.run("insert into a(a, b) values (2, 'hi')")
    result = db.run("SELECT * FROM a LIMIT 10;")
    print("result={}".format(result))



def get_schema(jdbc_uri, llm_name, api_url):
    """
    list_tables_tool: Fetch the available tables from the database
    get_schema_tool: Fetch the DDL for a table
    db_query_tool: Execute the query and fetch the results OR return an error message if the query fails
    :param jdbc_uri:
    :param llm_name:
    :param api_url:
    :return:
    """
    db = SQLDatabase.from_uri(jdbc_uri)
    toolkit = SQLDatabaseToolkit(db=db, llm = OllamaLLM(model=llm_name, base_url=api_url))
    tools = toolkit.get_tools()

    list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
    get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

    print("list_tables_tool: {}".format(list_tables_tool.invoke("")))

    print("get_schema_tool: {}".format(get_schema_tool.invoke("a")))


if __name__ == "__main__":
    """
    use a LLM tool call to retrieve information in database sqlite.
    """
    db_uri = "sqlite:///test.db"
    # llm_name_str = "deepseekR17B"

    #支持 tools工具调用功能
    llm_name_str = "llama3.2:3B"
    api_uri_str = "http://127.0.0.1:11434"
    sql_str = "SELECT * FROM a LIMIT 10;"
    # get_data(db_uri)
    # get_schema(db_uri, llm_name_str, api_uri)

    # test db_query_tool
    a = db_query_tool.invoke(sql_str, db_uri)
    print("db_query_tool invoke {} , get {}".format(sql_str, a))

    # test sql expert to check sql
    sql_expert(sql_str, llm_name_str, api_uri_str)

    # Define a new graph
    # workflow = StateGraph(State)
