#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
# 如果在 project 根目录下运行，可以这样执行  python -m apps.mcp_server.tools.db_query

import logging.config
from pydantic import BaseModel

from common.cm_utils import get_with_retry, post_with_retry
from common.sys_init import init_yml_cfg


logging.config.fileConfig("logging.conf", encoding="utf-8")
logger = logging.getLogger(__name__)

db_cfg = init_yml_cfg()['api']

MCP_TOOLS = {}

def mcp_tool(title, description):
    """装饰器标记函数为MCP工具"""
    def decorator(func):
        MCP_TOOLS[func.__name__] = {
            'func': func,
            'title': title,
            'description': description
        }
        return func
    return decorator

class DbInfo(BaseModel):
    name: str
    description: str
    dialect: str

class TableInfo(BaseModel):
    name: str
    description: str

class TableColumnInfo(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    comment: str

class TableSchemaInfo(BaseModel):
    db_name: str
    table_name: str
    create_table_sql: str

class ChartJsData(BaseModel):
    config: dict
    options: dict

class SqlExecResult(BaseModel):
    msg: str
    data: list[dict]

@mcp_tool("获取可用数据源列表", "获取目前可用的数据源（数据库）列表")
def list_available_db_source() -> list[DbInfo]:
    uri = f"{db_cfg['tool_api_uri']}/ds/list"
    db_source = get_with_retry(uri=uri, headers={}, params={}, proxies=None)
    logger.info(f"db_source_list {db_source}")
    db_list = []
    for item in db_source:
        db_info = DbInfo(name=item['name'], description=item['desc'], dialect=item['dialect'])
        db_list.append(db_info)
    logger.info(f"return_db_source_list {db_list}")
    return db_list

@mcp_tool("获取表清单", "获取某个数据源下的所有表的清单")
def list_available_tables(db_source:str) -> list[TableInfo]:
    """获取指定数据源中的所有表清单信息"""
    uri =f"{db_cfg['tool_api_uri']}/{db_source}/table/list"
    tables = get_with_retry(uri=uri,headers={}, params={}, proxies=None)
    logger.info(f"table_list {tables}")
    table_list = []
    for item in tables:
        table_info = TableInfo(name=item['name'], description=item['desc'])
        table_list.append(table_info)
    return table_list

@mcp_tool("获取表结构", "获取某个数据源下某个表的结构")
def get_table_schema(db_source: str, table_name: str) -> TableSchemaInfo:
    """获取目前 db_source 中表名称为  table_name 的 schema， 输出为 json 格式"""
    uri=f"{db_cfg['tool_api_uri']}/{db_source}/{table_name}/schema"
    tb_json = get_with_retry(uri=uri, headers={}, params={}, proxies=None)
    logger.info(f"get_table_schema {tb_json}")
    tb_schema = TableSchemaInfo(
        db_name=tb_json['db_name'],
        table_name=tb_json['table_name'],
        create_table_sql=tb_json['schema']
    )
    return tb_schema

@mcp_tool("执行查询SQL语句", "执行查询类SQL语句，不可提交修改数据的SQL语句")
def execute_sql_query(sql: str) -> SqlExecResult:
    """执行sql查询， 输出为json格式"""
    sql = sql.upper()
    result = SqlExecResult(msg="", data=[])
    if "INSERT" in sql or "UPDATE" in sql or "DELETE" in sql:
        logger.error(f"仅支持查询类的SQL语句, {sql}")
        result.msg = "仅支持查询类的SQL语句"
        return result
    data = {"sql":sql}
    uri= f"{db_cfg['tool_api_uri']}/exec/task"
    table_schema = post_with_retry(uri=uri, headers={}, data=data, proxies=None)
    logger.info(f"table_schema {table_schema}")
    result = SqlExecResult(msg="", data=table_schema)
    return result

# @mcp_tool("将数据转换为chartjs格式的数据", "将数据库查询获取的二维表格数据，转换为chartjs格式的数据，可由chartjs渲染成图表")
def render_chart(chart_data: dict, chart_type: str, title: str, x_axis: str, y_axis: str) -> dict:
    """
    将输入的数据，转换为chart js 格式的数据
    :param chart_data: 输入的数据， 格式为json格式
    :param chart_type: 图表类型， 支持的类型有：
        - line
        - bar
        - pie
        - radar
        - doughnut
        - polarArea
        - bubble
        - scatter
    :param title: 图表标题
    :param x_axis: 图表x轴标题
    :param y_axis: 图表y轴标题
    :return: 输出为chart js 格式的数据
    """
    chart_js_dt = {}
    return chart_js_dt

def do_test():
    # 测试代码
    # 获取可用数据源列表
    db_list = list_available_db_source()
    logger.info(f"db_list={db_list}")
    # 获取表清单
    table_list = list_available_tables(db_list[0].name)
    logger.info(f"table_list={table_list}")
    # 获取表结构
    table_schema = get_table_schema(db_list[0].name, table_list[0].name)
    logger.info(f"table_schema={table_schema}")
    # 执行查询SQL语句
    sql = "select * from user"
    exec_result = execute_sql_query(sql)
    logger.info(f"exec_result={exec_result}")


if __name__ == "__main__":
    do_test()