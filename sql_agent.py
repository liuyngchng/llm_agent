#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
from typing import Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
import logging.config
import httpx
from sql_util import sqlite_output, mysql_output
from sys_init import init_cfg

"""
pip install langchain_openai langchain_ollama langchain_core langchain_community pandas tabulate pymysql
"""

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)


class SQLGenerator:
    """
    for mysql
    # db_uri = "mysql+pymysql://db_user:db_password@db_host/db_name"
    """
    def __init__(self, db_uri: str, api_uri: str, api_key:str,
                 model_name:str, is_remote_model:bool):
        self.db = SQLDatabase.from_uri(db_uri)
        self.api_uri = api_uri
        self.api_key = api_key
        self.model_name = model_name
        self.is_remote_model = is_remote_model
        self.llm = self.get_llm()

        # 带数据库结构的提示模板
        self.gen_sql_prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             """您是一个专业的SQL生成助手。已知数据库结构：
             {schema}

             请严格按以下要求生成SQL：
             1. 仅输出标准SQL代码块，不要任何解释
             2. 使用与表结构完全一致的中文字段名，不要使用英文字段名
             3. WHERE条件需包含公司名称和时间范围过滤
             4. 禁止包含分析过程或思考步骤
             5. 查询语句中禁止用 *表示全部字段， 需列出详细的字段名称清单
             6. 禁止生成 update、delete 等任何对数据修改的语句
             """
             ),
            ("human", "用户问题：{question}")
        ])

        self.gen_nl_prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             """您是一个专业的数据解读助手。已知 Markdown格式的数据清单：
             {markdown_dt}

             (1) 请输出对数据的简洁解读，不要啰嗦
             (2) 如果没有提供数据，给出比较客气的回答，说没有查询到相关数据
             (3) 最终输出中，除了解读内容外，还需要返回原始的数据列表
             (4) 原始数据需要输出为html的多行表格,表格通过简单样式美化一下
             (5) 最终输出为html格式的文本，方便直接插入静态页面的<div></div>内部
             (6) 不要输出任何markdown格式的文本
             """
             )
        ])

    def generate_sql(self, question: str) -> str:
        """生成SQL查询"""
        chain = self.gen_sql_prompt_template | self.llm
        response = chain.invoke({
            "question": question,
            "schema": self.get_schema_info()
        })
        return response.content

    def get_nl_with_dt(self, markdown_dt: str):
        chain = self.gen_nl_prompt_template | self.llm
        response = chain.invoke({
            "markdown_dt": markdown_dt
        })
        return response.content

    def execute_query(self, sql: str) -> Dict:
        """执行SQL查询"""
        try:
            result = self.db.run(sql)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"SQL执行失败：{e}")
            return {"success": False, "error": str(e)}

    def get_schema_info(self) -> str:
        """获取数据库结构信息"""
        schema_entries = []
        for table in self.db.get_usable_table_names():
            # 使用新的字段获取方式
            columns = self.db._inspector.get_columns(table)  # 访问私有_inspector属性
            column_str = ",".join([col["name"] for col in columns])
            schema_entries.extend([
                f"表名：{table}",
                f"字段：{column_str}",
                f"示例数据：{self.db.run(f'SELECT * FROM {table} LIMIT 3')}",
                "-----------------"
            ])
        return "\n".join(schema_entries)

    def get_llm(self):
        if self.is_remote_model:
            if "https" in self.api_uri:
                model = ChatOpenAI(api_key=self.api_key,
                                   base_url=self.api_uri,
                                   http_client=httpx.Client(verify=False, proxy=None),
                                   model=self.model_name,
                                   temperature=0
                                   )
            else:
                model = ChatOllama(model=self.model_name, base_url=self.api_uri, temperature=0)
        else:
            model = ChatOllama(model=self.model_name, base_url=self.api_uri, temperature=0)
        logger.debug(f"model type {type(model)}, model: {model}")
        return model


def extract_sql(raw_sql: str) -> str:
    # 精准匹配 ```sql...``` 代码块
    pattern = r"```sql(.*?)```"
    match = re.search(pattern, raw_sql, re.DOTALL)  # DOTALL模式匹配换行

    if match:
        clean_sql = match.group(1)
        # 清理首尾空白/换行（保留分号）
        return clean_sql.strip(" \n\t")
    return raw_sql  # 无代码块时返回原始内容

def get_dt_with_nl(q: str, db_uri: str, api_uri:str, api_key: str,
                   model_name: str, output_data_format: str, is_remote_model: bool) -> str:
    """
    通过自然语言查询数据库中的数据
    """
    sql =""
    dt = ""
    agent = SQLGenerator(db_uri, api_uri, api_key, model_name, is_remote_model)
    try:
        # 生成SQL
        logger.info(f"提交的问题：{q}")
        sql = agent.generate_sql(q)
        logger.debug(f"generate_sql {sql}")
        sql = extract_sql(sql)
        logger.debug(f"extract_sql sql\n\n {sql}\n")

        if "sqlite" in db_uri:
            logger.debug(f"connect to sqlite db {db_uri}")
            dt = sqlite_output(db_uri, sql, "markdown")
        elif "mysql" in db_uri:
            logger.debug(f"connect to mysql db {db_uri}")
            dt = mysql_output(db_uri, sql, "markdown")
        else:
            logger.warning("other data type need to be done")
    except Exception as e:
        logger.error(f"error, {e}，sql: {sql}", exc_info=True)
    nl_dt = agent.get_nl_with_dt(dt)
    logger.info(f"nl_dt: {nl_dt}")
    return nl_dt

if __name__ == "__main__":
    os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    my_cfg = init_cfg()
    # while True:
    #     input_q = input("请输入您的问题(输入q退出)：")
    #     if input_q == "q":
    #         exit(0)
    input_q = "查询2025年的数据"
    result = get_dt_with_nl(input_q, my_cfg['db_uri'], my_cfg["api_uri"], my_cfg['api_key'], my_cfg['model_name'], 'json', True)
    logger.info(f"输出数据:\n{result}")