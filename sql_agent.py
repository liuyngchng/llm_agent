#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import math
import os

from typing import Dict
from datetime import datetime

import cfg_util
from doris import Doris
from utils import extract_md_content, rmv_think_block, extract_json

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from langchain_ollama import ChatOllama
import logging.config
import httpx
from pydantic import SecretStr
from my_enums import DBType, DataType

from db_util import DbUtl
from sys_init import init_yml_cfg

"""
pip install langchain_openai langchain_ollama \
    langchain_core langchain_community pandas tabulate pymysql
"""

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

MAX_MSG_COUNT = 20
# limit msg_history size to MAX_MSG_COUNT
usr_msg_list = {}

PAGE_SIZE = 20

def get_usr_msgs(uid: str):
    """
    get user msg history as a context to let llm know how to function
    usr_msg_list data structure: {"uid": ["用户提问:msg1", "系统回复:msg2", "用户提问:msg3"]}
    """
    return usr_msg_list.get(uid)

def save_usr_msg(uid: str, msg: str):
    """
    add user msg to msg list
    """
    msg_list = usr_msg_list.get(uid, [])
    if len(msg_list) > MAX_MSG_COUNT:
        msg_list.pop(0)
    msg_list.append(msg)
    usr_msg_list[uid] = msg_list
    logger.info(f"saved_usr_msg, uid {uid}, msg_list {usr_msg_list.get(uid, [])}")

class SqlAgent(DbUtl):
    """
    for mysql
    # db_uri = "mysql+pymysql://db_user:db_password@db_host/db_name"
    """

    def __init__(self, cfg:dict , is_remote_model=True, prompt_padding=""):
        self.cfg = cfg
        self.db_type = cfg['db']['type'].lower()
        if DBType.DORIS.value == self.db_type:
            self.doris_dt_source_cfg = cfg['db']
            self.doris_dt_source = Doris(self.doris_dt_source_cfg)
        else:
            db_uri = DbUtl.get_db_uri(cfg)
            self.db_dt_source = SQLDatabase.from_uri(db_uri)
        self.llm_api_uri = cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(cfg['api']['llm_api_key'])
        self.llm_model_name = cfg['api']['llm_model_name']
        self.is_remote_model = is_remote_model
        self.llm = self.get_llm()

        # 带数据库结构的提示模板
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        sql_gen_msg = f"""{cfg['prompts']['sql_gen_msg']}\n当前时间是 {current_time}"""
        intercept_q_msg = f"""{cfg['prompts']['intercept_q_msg']}\n当前时间是 {current_time}"""
        # try:
        #     sql_gen_msg = sql_gen_msg.replace("{sql_dialect}", cfg['db']['type'])
        # except Exception as e:
        #     logger.error("set_sql_dialect_err", e)
        # logger.debug(f"sql_gen_msg {sql_gen_msg}")
        self.sql_gen_prompt_template = ChatPromptTemplate.from_messages([
            ("system", f"{sql_gen_msg}, {prompt_padding}"),
            ("human", "用户问题：{msg}")
        ])
        chart_dt_gen_msg = f"""{cfg['prompts']['chart_dt_gen_msg']}"""
        # logger.debug(f"chart_dt_gen_msg {chart_dt_gen_msg}")
        self.chart_dt_gen_prompt_template = ChatPromptTemplate.from_messages([
            ("system", chart_dt_gen_msg),
            ("human", "用户问题：{msg}")
        ])

        self.desc_usr_dt_template = ChatPromptTemplate.from_messages([
            ("system", "根据查询到的数据\n{usr_dt}\n回答用户的问题"),
            ("human", "用户问题：{msg}")
        ])

        self.intercept_q_msg_template = ChatPromptTemplate.from_messages([
            ("system", intercept_q_msg),
            ("human", "用户问题：{msg}")
        ])

    def build_invoke_json(self, uid: str, q: str) -> dict:
        return {
            "msg": q,
            "schema": self.get_schema_info(),
            "sql_dialect": self.db_type,
            "chat_history": get_usr_msgs(uid)
        }

    def generate_sql(self, uid: str, question: str) -> str:
        """
        generate sql
        """
        chain = self.sql_gen_prompt_template | self.llm
        gen_sql_dict = self.build_invoke_json(uid, question)
        logger.info(f"gen_sql_dict: {gen_sql_dict}")
        response = chain.invoke(gen_sql_dict)
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

    def gen_usr_dt_check_sql(self, uid: str, question: str) -> str:
        """
        generate sql for get user data from user account database
        """
        chain = self.sql_gen_prompt_template | self.llm
        check_sql_dict = self.build_invoke_json(uid, question)
        logger.info(f"check_sql_dict: {check_sql_dict}")
        response = chain.invoke(check_sql_dict)
        return response.content

    def get_chart_dt(self, md_dt: str):
        """
        build chart.js data from source data
        :param md_dt： data table in markdown format
        """
        chain = self.chart_dt_gen_prompt_template | self.llm
        response = chain.invoke({
            "msg": md_dt
        })
        return response.content

    def intercept_usr_question(self, uid: str, q: str):
        chain = self.intercept_q_msg_template | self.llm
        intercept_gen_sql_dict = {
            "msg": q,
            "schema": self.get_schema_info(),
            "chat_history": get_usr_msgs(uid)
        }
        logger.info(f"intercept_gen_sql_dict {intercept_gen_sql_dict}")
        response = chain.invoke(intercept_gen_sql_dict)
        return response.content

    def execute_query(self, sql: str) -> Dict:
        """执行SQL查询"""
        try:
            result = self.db_dt_source.run(sql)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"SQL执行失败：{e}")
            return {"success": False, "error": str(e)}

    def get_all_tables(self)-> list:
        if DBType.ORACLE.value in self.db_type:
            table_list = DbUtl.get_orc_db_info(self.cfg)
        elif DBType.DORIS.value in self.db_type:
            table_list = self.doris_dt_source.get_table_list()
        else:
            table_list = self.db_dt_source.get_usable_table_names()
        return table_list

    def get_table_list(self)-> list:
        if self.cfg['db'].get('tables'):
            table_list = self.cfg['db']['tables'].split(',')
            logger.info(f"cfg_db_tables {table_list}")
        else:
            table_list = self.get_all_tables()
        return table_list

    def get_schema_info(self) -> str:
        if DBType.DORIS.value == self.db_type:
            doris_schema = self.doris_dt_source.get_schema_for_llm()
            # logger.info(f"doris_schema\n {doris_schema}")
            return doris_schema
        schema_entries = []
        for table in self.get_table_list():
            if DBType.ORACLE.value == self.db_type:
                table = table.upper()
            columns = self.db_dt_source._inspector.get_columns(table)
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
                f"示例数据：\n{self.db_dt_source.run(sample_dt_sql)}",
                "-----------------"
            ])
        schema_info = "\n".join(schema_entries)
        # logger.debug(f"schema_info:\n{schema_info}")
        return schema_info

    def get_llm(self):
        if self.is_remote_model:
            if "https" in self.llm_api_uri:
                model = ChatOpenAI(
                    api_key=self.llm_api_key,
                    base_url=self.llm_api_uri,
                    http_client=httpx.Client(verify=False, proxy=None),
                    model=self.llm_model_name,
                    temperature=0
                )
            else:
                model = ChatOllama(model=self.llm_model_name, base_url=self.llm_api_uri, temperature=0)
        else:
            model = ChatOllama(model=self.llm_model_name, base_url=self.llm_api_uri, temperature=0)
        logger.debug(f"modeltype {type(model)}, model: {model}")
        return model


    def get_dt_with_nl(self, uid: str, q: str, dt_fmt: str) -> dict:
        """
        get data from db by natural language
        :param uid: user id
        :param q: the question (natural language) user submitted
        :param dt_fmt: A DataType enum
        """
        sql =""
        adt = self.get_table_list()
        logger.info(f"agent_detected_tables:{adt} for_db_type {self.cfg['db']['type']}")
        if not adt or len(adt)> self.cfg['db']['max_table_num']:
            info = (f"please_check_your_data_source_user_privilege_or_db_schema, "
                f"none_table_or_too_much_table_can_be_accessed_by_the_user,"
                f" cfg['db']={self.cfg['db']}")
            raise Exception(info)
        nl_dt_dict = {"chart": {}, "raw_dt": {}, "sql": "", "total_count": 0, "cur_page": 1, "total_page":2}
        if self.cfg['db']['strict_search']:
            logger.info(f"check_user_question_with_llm_in_strict_search：{q}")
            intercept = self.intercept_usr_question(uid, q)
            if "查询条件清晰" not in intercept:
                nl_dt_dict["raw_dt"] = intercept
                logger.info(f"nl_dt:\n {nl_dt_dict}\n")
                save_usr_msg(uid, q)
                return nl_dt_dict
        try:
            logger.info(f"start_gen_sql_from_txt：{q}")
            sql = self.generate_sql(uid, q)
            save_usr_msg(uid, q)
            # logger.debug(f"gen_sql\n{sql}")
            nl_dt_dict["sql"] = extract_md_content(sql, "sql")
            logger.info(f"gen_sql_from_txt {q}, {nl_dt_dict.get('sql', '').replace('\n', ' ')}")
        except Exception as e:
            logger.error(f"gen_sql_err, {e}, txt: {q}", exc_info=True)
            nl_dt_dict["raw_dt"] = "用户问题转换为数据查询条件时发生异常"
            nl_dt_dict["sql"] = "暂无 SQL"
            return nl_dt_dict
        try:
            nl_dt_dict["raw_dt"] = self.get_dt_with_sql(nl_dt_dict["sql"], dt_fmt)
            count_sql = DbUtl.gen_count_sql(nl_dt_dict["sql"])
            count_dt = self.get_dt_with_sql(count_sql, DataType.JSON.value)
            total_count = json.loads(count_dt)[0].get("COUNT(1)")
            nl_dt_dict["total_count"] = total_count
            nl_dt_dict["total_page"] = math.ceil(total_count / PAGE_SIZE)
        except Exception as e:
            logger.error(f"get_dt_with_sql_err, {e}, sql: {sql}", exc_info=True)
            nl_dt_dict["raw_dt"] = "使用SQL从数据源查询数据时发生异常"
            return nl_dt_dict
        logger.info(f"nl_dt:\n {nl_dt_dict}\n")
        return self.build_chart_dt(uid, nl_dt_dict)

    def get_pg_dt(self, uid: str, usr_page_dt: dict, page_size=PAGE_SIZE) -> dict:
        logger.info(f"last_sql_for_{uid}: {usr_page_dt.get('sql', '').replace('\n', '')}")
        page_sql = DbUtl.get_page_sql(usr_page_dt['sql'], usr_page_dt['cur_page'], page_size)
        logger.info(f"next_sql: {page_sql}")
        dt = self.get_dt_with_sql(page_sql)
        nl_dt_dict = {
            "chart": {}, "raw_dt": dt, "sql": page_sql,
            "cur_page": usr_page_dt['cur_page'],
            "total_count":usr_page_dt['total_count'],
            "total_page": usr_page_dt['total_page'],
        }
        logger.info(f"nl_dt:\n {nl_dt_dict}\n")
        return self.build_chart_dt(uid, nl_dt_dict)

    def build_chart_dt(self, uid: str, nl_dt: dict) -> dict:
        """
        add chart dt for db retrieve dt
        : param dt: db retrieved dt
        : nl_dt: final dt need to be returned
        """
        cfg = cfg_util.get_ds_cfg_by_uid(uid, self.cfg)
        logger.info(f"cfg_for_uid {uid}, {cfg}")
        if cfg:
            if cfg.get("add_chart") == 1:
                return self.add_chart_to_raw_dt(nl_dt)
            else:
                return nl_dt
        if not self.cfg['prompts']['add_chart_to_dt']:
            return nl_dt
        return self.add_chart_to_raw_dt(nl_dt)

    def get_dt_with_sql(self, sql: str, dt_fmt=DataType.MARKDOWN.value) -> str:
        """
        :param sql: A Database SQL end with limit(for mysql)
        :param dt_fmt: A DataType enum
        """
        db_type = self.cfg.get('db', {}).get('type', "").lower()
        if DBType.SQLITE.value in db_type:
            db_uri = DbUtl.get_db_uri(self.cfg)
            logger.debug(f"connect_to_sqlite_db {db_uri}")
            dt = DbUtl.sqlite_output(db_uri, sql, dt_fmt)
        elif DBType.MYSQL.value in db_type:
            logger.debug(f"connect_to_mysql_db")
            dt = DbUtl.mysql_output(self.cfg, sql, dt_fmt)
        elif DBType.ORACLE.value in db_type:
            logger.debug(f"connect_to_oracle_db")
            dt = DbUtl.oracle_output(self.cfg, sql, dt_fmt)
        elif DBType.DORIS.value in db_type:
            logger.debug(f"connect_to_doris_db")
            dt = self.doris_dt_source.doris_output(sql, dt_fmt)
        else:
            raise RuntimeError("other_data_type_need_to_be_done")
        return dt

    def add_chart_to_raw_dt(self, nl_dt_dict:dict)-> dict:
        """
        add chart data to raw dt
        """
        logger.info("start_add_chart_to_raw_dt")
        chart_dt = {}
        try:
            nl_dt = self.get_chart_dt(nl_dt_dict["raw_dt"])
            logger.debug(f"nl_dt_from_agent\n{nl_dt}\n")
            nl_dt = rmv_think_block(nl_dt)
            logger.debug(f"nl_dt_without_think\n{nl_dt}\n")
            nl_dt = extract_json(nl_dt)
            logger.debug(f"nl_dt_only_json_str\n{nl_dt}\n")
            chart_dt = json.loads(nl_dt)
        except Exception as e:
            logger.exception("err_to_add_description_to_data", nl_dt_dict["raw_dt"])
        if chart_dt['chart']:
            nl_dt_dict['chart'] = chart_dt['chart']
        else:
            logger.error(f"chart_dt['chart'] is null, chart_dt {chart_dt}")
        logger.info(f"nl_chart_dt_with_raw_dt:\n{nl_dt_dict}\n")
        return nl_dt_dict



if __name__ == "__main__":
    save_usr_msg("123", "hello1")
    # save_usr_msg("123", "hello2")
    # os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    # my_cfg = init_yml_cfg()
    # while True:
    #     input_q = input("请输入您的问题(输入q退出)：")
    #     if input_q == "q":
    #         exit(0)
    # input_q = "查询2024年的数据明细"
    # SqlAgent.get_dt_with_nl(123, input_q, DataType.JSON.value, True)
