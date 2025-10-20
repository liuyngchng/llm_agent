#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
SQL 语句生成及数据查询服务， 提供流式输出
pip install langchain_openai langchain_ollama \
    langchain_core langchain_community pandas tabulate pymysql
"""
import json
import math
import ast
import os
import time

from typing import Dict
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.utilities import SQLDatabase
import logging.config
from pydantic import SecretStr

from common import cfg_util, agt_util
from apps.chat2db.doris import Doris
from common.cm_utils import extract_md_content, rmv_think_block, extract_json, get_table_name_from_sql
from common.my_enums import DBType, DataType, YieldType, AppType
from common.db_util import DbUtl
from common.sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

MAX_MSG_COUNT = 20
# limit msg_history size to MAX_MSG_COUNT
usr_msg_list = {}

PAGE_SIZE = 100

SQL_REVIEW_TIME = 3


def get_usr_msgs(uid: int):
    """
    get user msg history as a context to let llm know how to function
    usr_msg_list data structure: {"uid": ["用户提问:msg1", "系统回复:msg2", "用户提问:msg3"]}
    """
    return usr_msg_list.get(uid)

def save_usr_msg(uid: int, msg: str):
    """
    add user msg to msg list
    """
    msg_list = usr_msg_list.get(uid, [])
    if len(msg_list) > MAX_MSG_COUNT:
        msg_list.pop(0)
    msg_list.append(msg)
    usr_msg_list[uid] = msg_list
    logger.info(f"saved_usr_msg, uid {uid}, msg_list {usr_msg_list.get(uid, [])}")

class SqlYield(DbUtl):
    """
    for mysql
    # db_uri = "mysql+pymysql://db_user:db_password@db_host/db_name"
    """

    def __init__(self, uid: int, sys_cfg:dict, prompt_padding=""):

        self.cfg = sys_cfg
        self.uid = uid
        ds_cfg = cfg_util.get_ds_cfg_by_uid(uid, sys_cfg)
        if ds_cfg:
            self.cfg['db']['type']=ds_cfg['db_type']
            self.cfg['db']['name'] = ds_cfg['db_name']
            self.cfg['db']['host'] = ds_cfg['db_host']
            self.cfg['db']['port'] = ds_cfg['db_port']
            self.cfg['db']['user'] = ds_cfg['db_usr']
            self.cfg['db']['password'] = ds_cfg['db_psw']
            self.cfg['db']['tables'] = ds_cfg['tables']
            self.cfg['db']['add_chart'] = ds_cfg['add_chart']
            self.cfg['db']['is_strict'] = ds_cfg['is_strict']
            self.cfg['db']['llm_ctx'] = ds_cfg['llm_ctx']
        self.db_type = sys_cfg['db']['type'].lower()
        if DBType.DORIS.value == self.db_type:
            self.doris_dt_source_cfg = sys_cfg['db']
            self.doris_dt_source = Doris(self.doris_dt_source_cfg)
        elif DBType.DM8.value == self.db_type:
            # 对于DM8，不初始化 db_dt_source，因为SQLAlchemy不支持
            self.db_dt_source = None
            logger.info("dm8_database_detected, skipping SQLDatabase initialization")
        else:
            db_uri = DbUtl.get_db_uri(sys_cfg)
            self.db_dt_source = SQLDatabase.from_uri(db_uri)
        self.llm_api_uri = sys_cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(sys_cfg['api']['llm_api_key'])
        self.llm_model_name = sys_cfg['api']['llm_model_name']
        self.db_name = self.cfg['db'].get('name', self.cfg['db'].get('data_source'))

        # 带数据库结构的提示模板
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        refine_q_msg = f"""{cfg_util.get_usr_prompt_template('refine_q_msg', self.cfg, self.uid)}\n当前时间是 {current_time}"""
        sql_gen_msg = f"""{cfg_util.get_usr_prompt_template('sql_gen_msg', self.cfg, self.uid)}\n当前时间是 {current_time}"""
        sql_review_msg = f"""{cfg_util.get_usr_prompt_template('sql_review_msg', self.cfg, self.uid)}\n当前时间是 {current_time}"""
        count_sql_gen_msg = cfg_util.get_usr_prompt_template('count_sql_gen_msg', self.cfg, self.uid)
        explain_sql_msg = cfg_util.get_usr_prompt_template('explain_sql_msg', self.cfg, self.uid)
        intercept_q_msg = f"""{cfg_util.get_usr_prompt_template('intercept_q_msg', self.cfg, self.uid)}\n当前时间是 {current_time}"""
        self.refine_q_prompt_template = ChatPromptTemplate.from_messages([
            ("system", f"{refine_q_msg}\n{prompt_padding}"),
            ("human", "用户问题：{msg}")
        ])

        self.sql_gen_prompt_template = ChatPromptTemplate.from_messages([
            ("system", f"{sql_gen_msg}, {prompt_padding}"),
            ("human", "用户问题：{msg}")
        ])

        self.sql_review_prompt_template = ChatPromptTemplate.from_messages([
            ("system", f"{sql_review_msg}, {prompt_padding}")
        ])

        self.count_sql_gen_prompt_template = ChatPromptTemplate.from_messages([
            ("system", f"{count_sql_gen_msg}\n{prompt_padding}"),
            ("human", "查询数据的SQL：{msg}")
        ])

        self.explain_sql_msg_template = ChatPromptTemplate.from_messages([
            ("system", f"{explain_sql_msg}\n{prompt_padding}"),
            ("human", "查询数据的SQL：{msg}")
        ])
        chart_dt_gen_msg = f"""{cfg_util.get_usr_prompt_template('chart_dt_gen_msg', self.cfg, self.uid)}"""
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
            ("system", f"{intercept_q_msg}\n{prompt_padding}"),
            ("human", "用户问题：{msg}")
        ])

    def build_invoke_json(self, uid: int, q: str) -> dict:
        return {
            "msg": q,
            "schema": self.get_schema_info(),
            "sql_dialect": self.db_type,
            "max_record_per_page": PAGE_SIZE,
            "chat_history": get_usr_msgs(uid)
        }

    @staticmethod
    def build_refine_invoke_json(q: str, hack_content: str, data_source_info: str) -> dict:
        return {
            "msg": q,
            "data_source_info": data_source_info,
            "user_short_q_desc": hack_content
        }

    def refine_q(self, uid: int, question: str) -> str:
        """
        refine user question to let it can be understood by llm in a normal way.
        """
        # hack_content = cfg_util.get_hack_q_file_content(uid)
        hack_content = cfg_util.get_user_hack_info(uid, self.cfg)
        data_source_info = cfg_util.get_const("data_source_info", AppType.CHAT2DB.name.lower())
        chain = self.refine_q_prompt_template | self.get_llm()
        refine_q_dict = SqlYield.build_refine_invoke_json(question, hack_content, data_source_info)
        logger.info(f"start_refine_user_q, {uid}, {question}")
        response = chain.invoke(refine_q_dict)
        logger.info(f"return_from_refine_user_q, {response.content}, origin_q {question}")
        return response.content

    def get_hack_vdb(self, uid: int):
        """
        1. 如果vdb不存在，则创建vdb
        2. 如果vdb存在，则加载vdb
        """
        hack_vdb_file = f"./vdb/{uid}_q_hack_desc_vdb"
        if not os.path.exists(hack_vdb_file):
            task_id = int(time.time())
            file = f"./hack/{uid}_q_desc.txt"
            logger.info(f"vector_file({file}, {hack_vdb_file})")
            # todo debug, task_id need to be replaced with file_id
            from common.vdb_util import vector_file
            vector_file(task_id, file, hack_vdb_file, self.cfg['api'],
                        80, 10, 10, ["\n"])
        from common.vdb_util import load_vdb
        hack_vdb = load_vdb(hack_vdb_file, self.cfg['api'])
        if not hack_vdb:
            raise RuntimeError(f"load_vdb {hack_vdb_file} failed, hack_vdb_collection_is_null")

    def search_vdb(self, user_q: str, uid: int) -> str:
        hack_vdb_file = f"./vdb/{uid}_q_hack_desc_vdb"
        from common.vdb_util import search_txt
        result = search_txt(user_q, hack_vdb_file, 0.5, self.cfg['api'], 1)
        logger.info(f"search_result: {result}")
        return result

    def gen_sql_by_txt(self, uid: int, question: str) -> str:
        """
        generate sql
        """
        chain = self.sql_gen_prompt_template | self.get_llm()
        gen_sql_dict = self.build_invoke_json(uid, question)
        logger.info(f"gen_sql_by_txt: {gen_sql_dict}")
        response = chain.invoke(gen_sql_dict)
        return response.content

    def review_sql(self, current_sql: str, error_reason="") -> str:
        """
        generate sql
        """
        chain = self.sql_review_prompt_template | self.get_llm()
        review_sql_dict = {
            "current_sql": current_sql,
            "error_reason": error_reason,
            "schema": self.get_table_schema_info(get_table_name_from_sql(current_sql)),
            "sql_dialect": self.db_type
        }
        logger.info(f"review_sql_dict: {review_sql_dict}")
        response = chain.invoke(review_sql_dict)
        return response.content

    def gen_count_sql_by_sql(self, uid: int, sql: str) -> str:
        """
        generate count sql by data retrieval sql
        """
        chain = self.count_sql_gen_prompt_template | self.get_llm()
        gen_sql_dict = self.build_invoke_json(uid, sql)
        logger.info(f"gen_count_sql_by_sql: {gen_sql_dict}")
        response = chain.invoke(gen_sql_dict)
        return response.content

    def get_explain_sql_txt(self, uid: int, sql: str) -> str:
        """
        generate count sql by data retrieval sql
        """
        chain = self.explain_sql_msg_template | self.get_llm()
        explain_sql_dict = self.build_invoke_json(uid, sql)
        logger.info(f"get_explain_sql_txt: {explain_sql_dict}")
        response = chain.invoke(explain_sql_dict)
        return response.content

    def desc_usr_dt(self, question: str, usr_dt: dict) -> str:
        """
        generate sql
        """
        chain = self.desc_usr_dt_template | self.get_llm()
        response = chain.invoke({
            "msg": question,
            "usr_dt": usr_dt,
        })
        return response.content

    def gen_usr_dt_check_sql(self, uid: int, question: str) -> str:
        """
        generate sql for get user data from user account database
        """
        chain = self.sql_gen_prompt_template | self.get_llm()
        check_sql_dict = self.build_invoke_json(uid, question)
        logger.info(f"check_sql_dict: {check_sql_dict}")
        response = chain.invoke(check_sql_dict)
        return response.content

    def get_chart_dt(self, md_dt: str):
        """
        build chart.js data from source data
        :param md_dt： data table in mark down format
        """
        chain = self.chart_dt_gen_prompt_template | self.get_llm()
        response = chain.invoke({
            "msg": md_dt
        })
        return response.content

    def intercept_usr_question(self, uid: int, q: str):
        chain = self.intercept_q_msg_template | self.get_llm()
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
        elif DBType.DM8.value in self.db_type:
            table_list = DbUtl.get_dm8_db_info(self.cfg)
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

    def get_table_schema_info(self, table_name: str) -> str:
        if DBType.DORIS.value == self.db_type:
            doris_schema = self.doris_dt_source.get_table_schema(self.doris_dt_source.data_source, table_name)
            # logger.info(f"doris_schema\n {doris_schema}")
            return doris_schema
        elif DBType.DM8.value == self.db_type:
            dm8_schema = DbUtl.get_dm8_table_schema(self.cfg, table_name)
            return dm8_schema

        if DBType.ORACLE.value == self.db_type:
            table_name = table_name.upper()
        columns = self.db_dt_source._inspector.get_columns(table_name)
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
        sample_dt_sql = f'SELECT * FROM {table_name} {limit}'
        schema_info =f'''表名：{table_name}\n 字段信息：\n{column_table}\n"示例数据：\n{self.db_dt_source.run(sample_dt_sql)}'''
        # logger.debug(f"schema_info:\n{schema_info}")
        return schema_info

    def get_schema_info(self) -> str:
        if DBType.DORIS.value == self.db_type:
            doris_schema = self.doris_dt_source.get_schema_for_llm()
            # logger.info(f"doris_schema\n {doris_schema}")
            return doris_schema
        elif DBType.DM8.value == self.db_type:
            # 添加DM8的schema信息获取
            dm8_schema = DbUtl.get_dm8_schema_info(self.cfg)
            return dm8_schema
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
        return agt_util.get_model(self.cfg)


    def yield_dt_with_nl(self, uid: int, q: str, dt_fmt: str, user_page_dt: dict):
        """
        get data from db by natural language
        :param uid: user id
        :param q: the question (natural language) user submitted
        :param dt_fmt: A DataType enum
        :param user_page_dt: for pagination
        """
        logger.info(f"uid:{uid}, q:{q}, dt_fmt:{dt_fmt}")
        yield SqlYield.build_yield_dt(f"{q}...")
        adt = self.get_table_list()
        logger.info(f"agent_detected_tables, {adt}, db_type, {self.cfg['db']['type']}")
        if not adt or len(adt)> self.cfg['db']['max_table_num']:
            info = (f"please_check_your_data_source_user_privilege_or_db_schema, "
                f"none_table_or_too_much_table_can_be_accessed_by_the_user,"
                f" cfg['db']={self.cfg['db']}")
            yield SqlYield.build_yield_dt("连接数据源时发生异常")
            raise RuntimeError(info)
        cfg = cfg_util.get_ds_cfg_by_uid(uid, self.cfg)
        logger.info(f"cfg_for_uid {uid}, {cfg}")

        refined_q = self.refine_q(uid, q)
        logger.info(f"refined_q, {refined_q}, original_q, {q}")
        refined_q = extract_md_content(refined_q, "sql")
        logger.info(f"refined_q_extract_md, {refined_q}, original_q, {q}")
        q = refined_q
        yield SqlYield.build_yield_dt(q)
        if cfg.get("is_strict") == 1:
            logger.info(f"check_user_question_with_llm_in_strict_search, {q}")
            intercept = self.intercept_usr_question(uid, q)
            if "查询条件清晰" not in intercept:
                logger.info(f"intercept_txt:\n {intercept}\n")
                save_usr_msg(uid, q)
                yield SqlYield.build_yield_dt(f"需要您进一步确认，{intercept}")

        try:
            logger.info(f"start_to_gen_sql_from_txt：{q}")
            yield SqlYield.build_yield_dt("正在生成查询条件...")
            sql = self.gen_sql_by_txt(uid, q)
            save_usr_msg(uid, q)
            # logger.debug(f"gen_sql\n{sql}")
            extract_sql = extract_md_content(sql, "sql")

            logger.info(f"start_to_review_sql, {extract_sql}")
            yield SqlYield.build_yield_dt(f"SQL 已生成，开始校对 ...")
            review_sql = self.review_sql(extract_sql)
            extract_sql = extract_md_content(review_sql, "sql")

            area = cfg_util.get_user_info_by_uid(uid)['area']
            if area:
                ou_id_list = area.split(',')
                extract_sql = DbUtl.add_ou_id_condition(extract_sql, ou_id_list)
            # extract_sql = extract_sql.replace('\n', ' ')
            # extract_sql = re.sub(r'\s+', ' ', extract_sql).strip()
            extract_sql = extract_sql.replace('\n', ' ').replace('\\s+', ' ')
            sql_dt = f"查询条件： {extract_sql}"
            user_page_dt[uid] = {"sql": extract_sql, "cur_page": 1}
            yield SqlYield.build_yield_dt(sql_dt)
            # for line in extract_sql.split("\n"):
            #     yield SqlYield.build_yield_dt(line)
            yield SqlYield.build_yield_dt("开始查询数据...")
            logger.info(f"gen_sql_from_txt {q}, {extract_sql}")
        except Exception as e:
            logger.error(f"gen_sql_err, {e}, txt: {q}", exc_info=True)
            yield SqlYield.build_yield_dt("用户问题转换为数据查询条件时发生异常")
            return
        try:
            raw_dt = ""
            sql_review_time = 1
            while sql_review_time < SQL_REVIEW_TIME:
                raw_dt = self.get_dt_with_sql(extract_sql, dt_fmt)
                if raw_dt.find(cfg_util.DORIS_HTTP_REQ_NOT_200_ERR) > 0:
                    logger.info(f"{sql_review_time} time to_start_to_review_sql, {extract_sql}")
                    yield SqlYield.build_yield_dt(f"查询出错，第{sql_review_time}次开始重新生成SQL...")
                    logger.info(f"start_to_review_sql_after_sql_executed, {extract_sql}, {raw_dt}")
                    review_sql = self.review_sql(extract_sql, raw_dt)
                    sql_review_time += 1
                    extract_sql = extract_md_content(review_sql, "sql")
                    sql_dt = f"查询条件： {extract_sql}"
                    user_page_dt[uid] = {"sql": extract_sql, "cur_page": 1}
                    yield SqlYield.build_yield_dt(sql_dt)
                else:
                    break

            raw_dt1 = raw_dt.replace('\n', ' ')
            if SqlYield.is_valid_dt(raw_dt1):
                yield SqlYield.build_yield_dt(f"<div>查询到的数据如下:</div><br>{raw_dt1}", YieldType.HTML.value)
            else:
                yield SqlYield.build_yield_dt(f"<div>{raw_dt1}</div>", YieldType.HTML.value)
            yield SqlYield.build_yield_dt("查询符合条件的数据数量...")
        except Exception as e:
            logger.error(f"get_dt_with_sql_err, {e}, sql: {extract_sql}", exc_info=True)
            yield SqlYield.build_yield_dt("从数据源查询数据时发生异常")
            return
        total_page = 0
        if SqlYield.is_valid_dt(raw_dt1):
            count_sql = ''
            total_count = 0
            try:
                # count_sql_txt = self.gen_count_sql_by_sql(uid, nl_dt_dict["sql"])
                # count_sql = extract_md_content(count_sql_txt, "sql")
                count_sql = DbUtl.gen_count_sql(extract_sql)
                count_sql1 = count_sql.replace('\n', ' ')
                extract_sql1 = extract_sql.replace('\n', ' ')
                logger.info(f"gen_count_sql_by_get_dt_sql, result {count_sql1}, origin_get_dt_sql {extract_sql1}")
                count_dt_json = self.get_dt_with_sql(count_sql, DataType.JSON.value)
                total_count = SqlYield.get_count_num_from_json(count_dt_json)
                user_page_dt[uid]["total_count"] = total_count
                logger.info(f"dt_total_count, {total_count}")
                yield SqlYield.build_yield_dt("开始计算总页数...")
            except Exception as e:
                logger.error(f"get_dt_count_with_count_sql_err, {e}, count_sql: {count_sql}", exc_info=True)
                yield SqlYield.build_yield_dt("获取总数据条数发生异常")
            total_page = 1
            try:
                logger.info(f"get_total_page {total_count} / {PAGE_SIZE}")
                if isinstance(total_count, (int, float, complex)):
                    total_page = math.ceil(total_count / PAGE_SIZE)
                else:
                    logger.error(f"total_count_type_err_for {total_count}")

                user_page_dt[uid]["total_page"] = total_page

                yield_test = SqlYield.build_yield_dt(json.dumps(user_page_dt[uid]), YieldType.MSG.value)
                logger.info(f"yield_test {yield_test}")
                yield yield_test
                dt =f"<span>共 {total_count} 条数据, {total_page} 页, 每页 {PAGE_SIZE} 条数据</span>"
                yield SqlYield.build_yield_dt(dt, YieldType.HTML.value)
                yield SqlYield.build_yield_dt("生成查询条件说明...")
            except Exception as e:
                logger.error(f"get_total_count_or_total_page_err, {e}", exc_info=True)
        else:
            dt = f"<span>共 0 条数据, 0 页, 每页 {PAGE_SIZE} 条数据</span>"
            yield SqlYield.build_yield_dt(dt, YieldType.HTML.value)
            yield SqlYield.build_yield_dt("生成查询条件说明...")
        try:
            logger.info("get_explain_sql_txt_start")
            explain_sql_txt = self.get_explain_sql_txt(uid, extract_sql)
            explain_sql_txt = extract_md_content(explain_sql_txt, "sql")
            extract_sql1 = extract_sql.replace('\n', ' ')
            logger.info(f"get_explain_sql_txt, {explain_sql_txt}, input_sql, {extract_sql1}")
            yield SqlYield.build_yield_dt(f"查询条件说明：{explain_sql_txt}")
        except Exception as e:
            logger.error(f"get_explain_sql_txt_err, {e}, sql: {extract_sql}", exc_info=True)
            yield SqlYield.build_yield_dt("暂时无法给您提供数据查询的相关解释")
        logger.info(f"start_build_chart_dt, {raw_dt}")
        if not SqlYield.is_valid_dt(raw_dt1):
            yield SqlYield.build_yield_dt("任务执行完毕")
            return
        yield SqlYield.build_yield_dt("准备绘图...")
        chart_dt = self.yield_chart_dt(uid, raw_dt)
        if chart_dt:
            yield SqlYield.build_yield_dt(chart_dt, YieldType.CHART_JS.value)
        if total_page > 1:
            next_page_html = f"<div>数据已输出完毕， 查看&nbsp;&nbsp;<a href='#' onclick='loadNextPage(event)'>下一页</a></div>"
            yield SqlYield.build_yield_dt(next_page_html, YieldType.HTML.value)
        else:
            yield SqlYield.build_yield_dt("任务执行完毕")

    @staticmethod
    def is_valid_dt(raw_dt: str) -> bool:
        return raw_dt and raw_dt.find('</table>') > 0


    @staticmethod
    def build_yield_dt(dt: str, dt_type=YieldType.TXT.value) -> str:
        """
        :param dt: a raw dt
        :param dt_type: A {@link YieldType} instance
        return a data structure: {"data_type": "msg", "data": {}}, or {"data_type": "msg", "data": "sample_data"}
        """
        if dt_type in (YieldType.CHART_JS.value, YieldType.MSG.value):
            json_dt = json.dumps({"data_type": dt_type, "data": json.loads(dt)}, ensure_ascii=False)
        else:
            json_dt = json.dumps({"data_type": dt_type, "data": dt}, ensure_ascii=False)
        return f"data: {json_dt}\n\n"

    @staticmethod
    def get_count_num(count_dt:str) -> int:
        try:
            data = ast.literal_eval(count_dt)
            return next(iter(json.loads(data)[0].values()))
        except Exception as e:
            logger.error(f"get_count_num_err, {count_dt}")
            return 0

    @staticmethod
    def get_count_num_from_json(count_dt: str) -> int:

        try:
            my_json = json.loads(count_dt)
            return next(iter(my_json[0].values()))
        except Exception as e:
            logger.error(f"get_count_num_err, {count_dt}")
            return 0

    def get_pg_dt(self, uid: int, usr_page_dt: dict, page_size=PAGE_SIZE):
        last_sql1 = usr_page_dt.get('sql', '').replace('\n', '')
        logger.info(f"last_sql_for_{uid}: {last_sql1}")
        page_sql = DbUtl.get_page_sql(usr_page_dt['sql'], usr_page_dt['cur_page'], page_size)
        logger.info(f"next_sql: {page_sql}")
        dt = self.get_dt_with_sql(page_sql, DataType.HTML.value)
        yield SqlYield.build_yield_dt(dt, YieldType.HTML.value)
        chart_dt = self.yield_chart_dt(uid, dt)
        yield SqlYield.build_yield_dt(chart_dt, YieldType.CHART_JS.value)

    def yield_chart_dt(self, uid: int, raw_dt: str) -> str:
        """
        add chart dt for db retrieve dt
        : param dt: db retrieved dt
        : nl_dt: final dt need to be returned
        """
        try:
            cfg = cfg_util.get_ds_cfg_by_uid(uid, self.cfg)
            logger.info(f"cfg_for_uid {uid}, {cfg}")
            if cfg and cfg.get("add_chart") == 1 or self.cfg['chart_js']['add_chart_to_dt']:
                return self.get_chart_dt_from_raw_dt(raw_dt)
            else:
                logger.info("no_chart_dt_to_output")
        except Exception as e:
            logger.error(f"build_chart_dt_err, {e}", exc_info=True)
        return ""

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
        elif DBType.DM8.value in db_type:
            logger.debug(f"connect_to_dm8_db")
            dt = DbUtl.dm8_output(self.cfg, sql, dt_fmt)
        elif DBType.DORIS.value in db_type:
            logger.debug(f"connect_to_doris_db")
            dt = self.doris_dt_source.doris_output(sql, dt_fmt)
        else:
            raise RuntimeError("other_data_type_need_to_be_done")
        logger.debug(f"output_dt {dt}")
        return dt


    def get_chart_dt_from_raw_dt(self, raw_dt:str) -> str:
        """
        add chart data to raw dt
        """
        logger.info(f"start_add_chart_to_raw_dt， {raw_dt}")
        try:
            chart_dt = self.get_chart_dt(raw_dt)
            chart_dt1 = chart_dt.replace('\n', ' ')
            logger.debug(f"nl_dt_from_agent, {chart_dt1}")
            chart_dt = rmv_think_block(chart_dt)
            chart_dt1 = chart_dt.replace('\n', ' ')
            logger.debug(f"nl_dt_without_think, {chart_dt1}")
            chart_dt = extract_json(chart_dt)
            chart_dt1 = chart_dt.replace('\n', ' ')
            logger.debug(f"nl_dt_only_json_str, {chart_dt1}")
            return chart_dt
        except Exception as e:
            logger.exception(f"err_to_add_description_to_raw_dt, nl_dt {raw_dt}")
        return ""


if __name__ == "__main__":
    save_usr_msg(123, "hello1")
    # save_usr_msg("123", "hello2")
    # os.system("unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy")
    my_cfg = init_yml_cfg()
    # while True:
    #     input_q = input("请输入您的问题(输入q退出)：")
    #     if input_q == "q":
    #         exit(0)
    input_q = "查询2024年的数据明细"
    sql_yield = SqlYield(123, my_cfg)
    sql_yield.yield_dt_with_nl("123", input_q, DataType.HTML.value)
