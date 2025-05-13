#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os

from typing import Dict
from datetime import datetime

from utils import extract_md_content, rmv_think_block, extract_json

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from langchain_ollama import ChatOllama
import logging.config
import httpx
from pydantic import SecretStr
from my_enums import DBType, DataType

from db_util import sqlite_output, mysql_output, get_db_uri, oracle_output, get_orc_db_info
from sys_init import init_yml_cfg

"""
pip install langchain_openai langchain_ollama \
    langchain_core langchain_community pandas tabulate pymysql
"""

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class SQLGenerator:
    """
    for mysql
    # db_uri = "mysql+pymysql://db_user:db_password@db_host/db_name"
    """

    def __init__(self, cfg:dict , is_remote_model:bool, prompt_padding=""):
        self.cfg = cfg
        db_uri = get_db_uri(cfg)
        self.db = SQLDatabase.from_uri(db_uri)
        self.db_type = cfg['db']['type'].lower()
        self.api_uri = cfg['api']['llm_api_uri']
        self.api_key = SecretStr(cfg['api']['llm_api_key'])
        self.model_name = cfg['api']['llm_model_name']
        self.is_remote_model = is_remote_model
        self.llm = self.get_llm()

        # 带数据库结构的提示模板
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        sql_gen_sys_msg = f"""{cfg['prompts']['sql_gen_sys_msg']}\n当前时间是{current_time}"""
        # try:
        #     sql_gen_sys_msg = sql_gen_sys_msg.replace("{sql_dialect}", cfg['db']['type'])
        # except Exception as e:
        #     logger.error("set_sql_dialect_err", e)
        logger.debug(f"sql_gen_sys_msg {sql_gen_sys_msg}")
        self.sql_gen_prompt_template = ChatPromptTemplate.from_messages([
            ("system", f"{sql_gen_sys_msg}, {prompt_padding}"),
            ("human", "用户问题：{msg}")
        ])
        nl_gen_sys_msg = f"""{cfg['prompts']['nl_gen_sys_msg']}"""
        logger.debug(f"nl_gen_sys_msg {nl_gen_sys_msg}")
        self.nl_gen_prompt_template = ChatPromptTemplate.from_messages([
            ("system", nl_gen_sys_msg),
            ("human", "用户问题：{msg}")
        ])

        self.desc_usr_dt_template = ChatPromptTemplate.from_messages([
            ("system", "根据查询到的数据\n{usr_dt}\n回答用户的问题"),
            ("human", "用户问题：{msg}")
        ])

    def generate_sql(self, question: str) -> str:
        """
        generate sql
        """
        chain = self.sql_gen_prompt_template | self.llm
        response = chain.invoke({
            "msg": question,
            "schema": self.get_schema_info(),
            "sql_dialect": self.db_type,
        })
        return response.content

    def desc_usr_dt(self, question: str, usr_dt: dict) -> str:
        """
        generate sql
        """
        chain = self.desc_usr_dt_template | self.llm
        response = chain.invoke({
            "msg": question,
            "usr_dt": usr_dt,
        })
        return response.content

    def gen_usr_dt_check_sql(self, question: str) -> str:
        """
        generate sql for get user data from user account database
        """
        chain = self.sql_gen_prompt_template | self.llm
        response = chain.invoke({
            "msg": question,
            "schema": self.get_schema_info(),
            "sql_dialect": self.db_type,
        })
        return response.content

    def get_nl_with_dt(self, markdown_dt: str):
        chain = self.nl_gen_prompt_template | self.llm
        response = chain.invoke({
            "msg": markdown_dt
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

    def get_table_list(self)-> list:
        if "oracle" in self.db_type:
            table_list = get_orc_db_info(self.cfg)
        else:
            table_list = self.db.get_usable_table_names()
        return table_list

    def get_schema_info(self) -> str:
        schema_entries = []
        for table in self.get_table_list():
            if DBType.ORACLE.value in self.db_type:
                table = table.upper()
            columns = self.db._inspector.get_columns(table)
            table_header = "| 字段名 | 字段类型 | 字段注释 |\n|--------|----------|----------|"
            table_rows = []
            for col in columns:
                name = col["name"]
                col_type = str(col.get("type", "N/A"))
                comment = col.get("comment", "")
                table_rows.append(f"| {name} | {col_type} | {comment} |")

            column_table = "\n".join([table_header] + table_rows)
            if DBType.ORACLE.value in self.db_type:
                limit = "WHERE ROWNUM <= 3"
            else:
                limit = "LIMIT 3"
            sample_dt_sql = f'SELECT * FROM {table} {limit}'
            schema_entries.extend([
                f"表名：{table}",
                f"字段信息：\n{column_table}",
                f"示例数据：\n{self.db.run(sample_dt_sql)}",
                "-----------------"
            ])
        schema_info = "\n".join(schema_entries)
        logger.debug(f"schema_info:\n{schema_info}")
        return schema_info


    def get_llm(self):
        if self.is_remote_model:
            if "https" in self.api_uri:
                model = ChatOpenAI(
                    api_key=self.api_key,
                    base_url=self.api_uri,
                    http_client=httpx.Client(verify=False, proxy=None),
                    model=self.model_name,
                    temperature=0
                )
            else:
                model = ChatOllama(model=self.model_name, base_url=self.api_uri, temperature=0)
        else:
            model = ChatOllama(model=self.model_name, base_url=self.api_uri, temperature=0)
        logger.debug(f"modeltype {type(model)}, model: {model}")
        return model

def desc_usr_dt(q: str, cfg: dict, is_remote_model: bool, usr_dt: dict) -> str:
    """
    通过自然语言查询数据库中的数据
    """
    agent = SQLGenerator(cfg, is_remote_model)
    return agent.desc_usr_dt(q, usr_dt)


def get_dt_with_nl(q: str, cfg: dict, output_data_format: str, is_remote_model: bool, prompt_padding="") -> str:
    """
    通过自然语言查询数据库中的数据
    """
    sql =""
    dt = ""
    nl_dt_dict={"chart":{}, "raw_dt": {}}
    agent = SQLGenerator(cfg, is_remote_model, prompt_padding)
    adt = agent.get_table_list()
    logger.info(f"agent_detected_tables:{adt} for db_type {cfg['db']['type']}")
    if not adt or len(adt)> cfg['db']['max_table_num']:
        info = (f"please_check_your_data_source_user_privilege_or_db_schema, "
                f"none_table_or_too_much_table_can_be_accessed_by_the_user,"
                f" cfg['db']={cfg['db']}")
        raise Exception(info)
    try:
        # 生成SQL
        logger.info(f"summit_question_to_llm：{q}")
        sql = agent.generate_sql(q)
        logger.debug(f"llm_output_sql\n{sql}")
        sql = extract_md_content(sql, "sql")
        logger.debug(f"extract_sql\n\n{sql}\n")
        db_uri = get_db_uri(cfg)
        if DBType.SQLITE.value in db_uri:
            logger.debug(f"connect to sqlite db {db_uri}")
            dt = sqlite_output(db_uri, sql, output_data_format)
        elif DBType.MYSQL.value in db_uri:
            logger.debug(f"connect to mysql db {db_uri}")
            dt = mysql_output(cfg, sql, output_data_format)
        elif DBType.ORACLE.value in db_uri:
            logger.debug(f"connect to oracle db {db_uri}")
            dt = oracle_output(cfg, sql, output_data_format)
        else:
            raise "other data type need to be done"
    except Exception as e:
        logger.error(f"error, {e}，sql: {sql}", exc_info=True)
    nl_dt_dict["raw_dt"] = dt
    logger.info(f"nl_dt_dict:\n {nl_dt_dict}\n")
    if not dt:
        return json.dumps(nl_dt_dict, ensure_ascii=False)

    if not cfg['prompts']['add_chart_to_dt']:
        logger.info(f"nl_raw_dt:\n{dt}\n")
        return json.dumps(nl_dt_dict, ensure_ascii=False)
    return add_chart_to_raw_dt(agent, dt, nl_dt_dict)


def add_chart_to_raw_dt(agent: SQLGenerator, dt:str, nl_dt_dict:dict)-> str:
    """
    add chart data to raw dt
    """
    logger.info("start_add_chart_to_raw_dt")
    chart_dt = {}
    try:
        nl_dt = agent.get_nl_with_dt(dt)
        logger.debug(f"nl_dt_from_agent\n{nl_dt}\n")
        nl_dt = rmv_think_block(nl_dt)
        logger.debug(f"nl_dt_without_think\n{nl_dt}\n")
        nl_dt = extract_json(nl_dt)
        logger.debug(f"nl_dt_only_json_str\n{nl_dt}\n")
        chart_dt = json.loads(nl_dt)
    except Exception as e:
        logger.exception("err_to_add_description_to_data", dt)
    if chart_dt['chart']:
        nl_dt_dict['chart'] = chart_dt['chart']
    else:
        logger.error(f"chart_dt['chart'] is null, chart_dt {chart_dt}")
    nl_dt_dict_str = json.dumps(nl_dt_dict, ensure_ascii=False)
    logger.info(f"nl_chart_dt_with_raw_dt:\n{nl_dt_dict_str}\n")
    return nl_dt_dict_str



if __name__ == "__main__":
    os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    my_cfg = init_yml_cfg()
    # while True:
    #     input_q = input("请输入您的问题(输入q退出)：")
    #     if input_q == "q":
    #         exit(0)
    input_q = "查询2024年的数据明细"
    get_dt_with_nl(input_q, my_cfg, DataType.JSON.value, True)