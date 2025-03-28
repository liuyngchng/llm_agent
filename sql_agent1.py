#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
import logging.config
import httpx
from sqlite_util import output_data

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

# model_name = "deepseek-r1"
model_name = "llama3.1"
api_url = "http://127.0.0.1:11434"
api_key = "123456789"
db_file = "test1.db"
db_uri = f"sqlite:///{db_file}"
question ="查询山东天然气销售分公司的订单详细信息"

def init_cfg(cfg_file="env.cfg"):
    global api_url, api_key, model_name
    with open(cfg_file) as f:
        lines = f.readlines()
    if len(lines) < 2:
        logger.error("cfg_err_in_file_{}".format(cfg_file))
        return
    try:
        api_url = lines[0].strip()
        api_key = lines[1].strip()
        model_name = lines[2].strip()
        logger.info("init_cfg_info, api_url:{}, api_key:{}, model_name:{}"
                    .format(api_url, api_key, model_name))
    except Exception as e:
        logger.error("init_cfg_error: {}".format(e))

class SQLGenerator:

    def __init__(self, db_uri: str):
        self.db = SQLDatabase.from_uri(db_uri)
        self.llm = self.get_llm(False)

        # 带数据库结构的提示模板
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             """您是一个专业的SQL生成助手。已知数据库结构：
             {schema}

             请严格按以下要求生成SQL：
             1. 仅输出标准SQL代码块，不要任何解释
             2. 使用与表结构完全一致的中文字段名
             3. WHERE条件需包含公司名称和时间范围过滤
             4. 禁止包含分析过程或思考步骤
             5. select 中禁止使用 *， 列出详细的字段名称
             """
             ),
            ("human", "用户问题：{question}")
        ])

    def generate_sql(self, question: str) -> str:
        """生成SQL查询"""
        chain = self.prompt_template | self.llm
        response = chain.invoke({
            "question": question,
            "schema": self.get_schema_info()
        })
        return response.content

    def execute_query(self, sql: str) -> Dict:
        """执行SQL查询"""
        try:
            result = self.db.run(sql)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"SQL执行失败：{str(e)}")
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

    @staticmethod
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


if __name__ == "__main__":
    init_cfg()
    agent = SQLGenerator(db_uri)
    # 生成SQL
    logger.info(f"提交问题：{question}")
    sql = agent.generate_sql(question)
    sql= sql.replace("```", "").replace("[SQL:", "").replace("]","")
    logger.debug(f"生成的SQL：\n\n{sql}\n")

    # 执行查询
    # result = agent.execute_query(sql)
    # if result["success"]:
    #     logger.info(f"查询结果：\n{result["data"]}")
    # else:
    #     logger.error(f"查询失败：{result['error']}")
    conn = sqlite3.connect(db_file)
    result = output_data(conn, sql)
    logger.info(f"输出数据:\n{result}")