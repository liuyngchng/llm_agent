#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
from typing import LiteralString

import pandas as pd
import requests
import logging.config

from my_enums import DataType
from sys_init import init_yml_cfg
from tabulate import tabulate


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)



class Doris:
    """
    A doris data source class
    """
    def __init__(self, cfg: dict):
        if not 'url' in cfg:
            cfg = self.build_cfg(cfg)
        self.url = cfg['url']
        self.token = cfg['token']
        self.data_source = cfg['data_source']
        self.uid = cfg['uid']
        self.headers = {
            "Content-Type": "application/json",
            "token": self.token,
        }
        self.json_template = {
            "currentPage": 1,
            "pageSize": 10,
            "name": self.data_source,
            "total": False,
            "script": "",
            "tenantName": cfg.get('tenantName', 'trqgd'),
            "uid": self.uid,
        }
        # {
        #     "db1_name": {},
        #     "db2_name": {
        #         "table1_name": {
        #             "column1_name": "column1_comment",
        #             "column2_name": "column2_comment",
        #         }
        #     }
        # }
        self.comment_map = self.init_comment_map()

    def build_json(self, sql: str):
        """
        build json body from sql
        """
        return {
            **self.json_template,
            "script": sql
        }

    def exec_sql(self, sql: str) -> json:
        """
        exec sql in doris
        """
        logger.info(f"exec_sql [{sql}]")
        body = self.build_json(sql)
        response = requests.post(self.url, json=body, headers=self.headers, proxies={'http': None, 'https': None})
        exec_json = response.json()
        if exec_json['code'] == 200:
            return exec_json['data']
        else:
            logger.error(f"exec_sql_exception_[{sql}],return_from_uri {self.url}, {exec_json}")
            raise RuntimeError(f"exec_sql_exception_{sql}")

    def get_table_col_comment(self, schema_name: str, table_name: str) -> list:
        """
        [{'COLUMN_NAME': 'a', 'COLUMN_COMMENT': 'comment_a'}, {'COLUMN_NAME': 'b', 'COLUMN_COMMENT': 'comment_b'}]
        """
        # sql = (f"SELECT COLUMN_NAME, COLUMN_COMMENT "
        #        f"FROM INFORMATION_SCHEMA.COLUMNS "
        #        f"WHERE TABLE_SCHEMA='{schema_name}' AND TABLE_NAME='{table_name}'")
        sql = f"SHOW CREATE TABLE {schema_name}.{table_name}"
        logger.info(f"get_col_comment_sql {sql}")
        exe_result = self.exec_sql(sql)
        return Doris.parse_ddl_to_list(exe_result[0].get('Create Table').split('ENGINE')[0])

    def get_table_list(self) -> list:
        get_table_list_sql = "show tables"
        my_json = self.exec_sql(get_table_list_sql)
        logger.info(f"response {my_json}")
        table_list = ['dws_dw_ycb_day']
        # table_list = [item[f"Tables_in_{self.data_source}"] for item in my_json]
        return table_list

    def get_schema_info(self) -> list:
        """
        get schema
        """
        schema_table = []
        for table in self.get_table_list():
            get_schema_sql = f"show create table {self.data_source}.{table}"
            logger.info(f"get_schema_sql {get_schema_sql}")
            my_json = self.exec_sql(get_schema_sql)
            table_schema_json = {"name": table, "schema_md_table": my_json[0].get('Create Table').split('ENGINE')[0]}
            schema_table.append(
                table_schema_json
            )
            logger.info(f"response {my_json}")
        return schema_table

    @staticmethod
    def parse_ddl_to_md_table(ddl_sql: str) -> str:
        pattern = r'`(\w+)`\s+([^\s]+)\s+.*?COMMENT\s+\'(.*?)\''
        columns = []
        for line in ddl_sql.split('\n'):
            match = re.search(pattern, line.strip())
            if match:
                name = match.group(1)
                col_type = match.group(2)
                comment = match.group(3)
                columns.append({"name": name, "type": col_type, "comment": comment})

        # 生成Markdown表格
        header = "| 字段名 | 字段类型 | 字段注释 |\n|--------|----------|----------|"
        rows = [f"| {col['name']} | {col['type']} | {col['comment']} |" for col in columns]
        return '\n'.join([header] + rows)

    @staticmethod
    def parse_ddl_to_list(ddl_sql: str) -> list:
        pattern = r'`(\w+)`\s+([^\s]+)\s+.*?COMMENT\s+\'(.*?)\''
        columns = []
        for line in ddl_sql.split('\n'):
            match = re.search(pattern, line.strip())
            if match:
                name = match.group(1)
                # col_type = match.group(2)
                comment = match.group(3)
                columns.append({"COLUMN_NAME": name, "COLUMN_COMMENT": comment})
                # columns.append({"COLUMN_NAME": name, "COLUMN_TYPE": col_type, "COLUMN_COMMENT": comment})
        return columns

    def get_schema_for_llm(self):
        """
        get schema from llm
        """
        schema_entries = []
        tb_schema_list = self.get_schema_info()
        logger.info(f"my_dt {tb_schema_list}")
        for tb_schema_json in tb_schema_list:
            md_tbl_schema = self.parse_ddl_to_md_table(tb_schema_json['schema_md_table'])
            logger.info(f"md_tbl\n{md_tbl_schema}")
            sample_dt_sql = f"SELECT * FROM {tb_schema_json['name']} LIMIT 3"
            schema_entries.extend([
                f"表名：{tb_schema_json['name']}",
                f"字段信息：\n{md_tbl_schema}",
                f"示例数据：\n{self.exec_sql(sample_dt_sql)}",
                "-----------------"
            ])
        schema_info = "\n".join(schema_entries)
        logger.debug(f"schema_info:\n{schema_info}")
        return schema_info

    def count_dt(self, count_sql: str):
        count_body = self.build_json(count_sql)
        response = requests.post(self.url, json=count_body,
             headers=self.headers, proxies={'http': None, 'https': None})
        my_json = response.json()['data'][0]['count(1)']
        logger.info(f"response {my_json}")
        return my_json

    @staticmethod
    def build_cfg(cfg) -> dict:
        """
        build http cfg from database cfg
        """
        cfg['url'] = f"http://{cfg['host']}:{cfg['port']}/api/db/execute"
        cfg['token'] = cfg['password']
        cfg['data_source'] = cfg['name']
        cfg['uid'] = cfg['user']
        cfg.pop('host')
        cfg.pop('port')
        cfg.pop('password')
        cfg.pop('name')
        cfg.pop('user')
        logger.info(f"build_doris_cfg {cfg}")
        return cfg

    def output_data(self, sql: str, data_format: str) -> str | LiteralString | None:
        try:
            data = self.exec_sql(sql)
            if not data:
                # return json.dumps({"columns": [], "data": []})
                return "目前没有符合您提问的数据，您可以换个问题或扩大查询范围再试试"
            columns = self.get_col_name_from_sql(data, sql)
            rows = [list(row.values()) for row in data]
            df = pd.DataFrame(rows, columns=columns)
            dt_fmt = data_format.lower()
            if DataType.HTML.value in dt_fmt:
                dt = df.to_html(index=False, border=0).replace(...)
            elif DataType.MARKDOWN.value in dt_fmt:
                dt = df.to_markdown(index=False) if not df.empty else ''
            elif DataType.JSON.value in dt_fmt:
                dt = df.to_json(force_ascii=False, orient='records')
            else:
                raise ValueError(f"unsupported_format: {data_format}")
            return dt
        except Exception as e:
            logger.error(f"doris_output_error: {str(e)}")
            return json.dumps({"error": str(e)})

    def get_col_name_from_sql(self, data, sql):
        table_match = re.search(r'(?i)FROM\s+([\w.]+)', sql)
        table_name = table_match.group(1) if table_match else 'unknown_table_name'
        raw_columns = list(data[0].keys()) if data else []
        if 'unknown_table_name' == table_name:
            logger.error(f"get_table_name_err_for_sql {sql}")
            columns = raw_columns
        else:
            columns = [self.get_comment(self.data_source, table_name, col) or col
                for col in raw_columns]
        return columns

    @staticmethod
    def get_col_comment_by_col_name(db_schema, db_name, table_name, column_name):
        for db in db_schema:
            if db["db"] != db_name: continue
            for table in db["table"]:
                if table["name"] != table_name: continue
                for col in table["column"]:
                    if col["name"] == column_name:
                        comment = col.get("comment", "").strip()
                        if not comment: return column_name
                        comment = ''.join(filter(str.isalnum, comment))
                        return comment[:10] if len(comment) > 10 else comment
        return column_name

    def get_comment(self, db, table, col):
        if (db_map := self.comment_map.get(db)) \
                and (table_map := db_map.get(table)) \
                and (comment := table_map.get(col)):
            return comment
        return None

    def init_comment_map(self):
        my_comment_map = {}
        table_list = self.get_table_list()
        for table in table_list:
            cmt_list = self.get_table_col_comment(self.data_source, table)
            logger.info(f"get_comment_list {cmt_list}")
            for item in cmt_list:
                col_name = item['COLUMN_NAME']
                raw_comment = item['COLUMN_COMMENT'].strip()
                processed = ''.join(filter(lambda c: c.isalnum(), raw_comment))
                processed = processed[:10] if processed else col_name
                my_comment_map.setdefault(self.data_source, {}).setdefault(table, {})[col_name] = processed
        logger.info(f"my_comment_map {my_comment_map}")
        return my_comment_map


def get_sql_from_terminal() -> str:
    """
    接收 console 中的 输入的 sql, 可以多行，以；结尾
    接收完一个sql后，继续等待控制台输入其他sql
    Returns:
        str: 完整的SQL语句（包含结尾的分号）
    """
    sql_lines = []
    print("\nEnter your SQL (end with ';'):")
    print("(Type 'exit;' or 'quit;' to end the session)")

    while True:
        try:
            line = input().strip()
            if not line:  # Skip empty lines
                continue
            sql_lines.append(line)
            if line.endswith(';'):
                break
        except EOFError as ex:  # Handle Ctrl+D
            logger.error("err_to_get_input", ex)
            return ""

    sql = ' '.join(sql_lines)
    # Clean up multiple spaces while preserving SQL string content
    sql = ' '.join(sql.split())
    return sql


def console_simulator():
    """
    控制台模拟器，得到一个sql后，执行，显示执行结果，等待其他sql的输入
    """
    console_cfg = init_yml_cfg()['doris']
    logger.info(f"my_cfg: {console_cfg}")
    console_doris = Doris(console_cfg)

    print("Doris SQL Console (Enter SQL statements ending with ';')")
    print("Type 'exit;' or 'quit;' to end the session\n")

    while True:
        try:
            console_sql = get_sql_from_terminal()
            if not console_sql:  # Handle EOF (Ctrl+D)
                break
            # Check for exit commands (case insensitive)
            sql_lower = console_sql.lower()
            if sql_lower in ('exit;', 'quit;'):
                print("Exiting Doris SQL Console...")
                break
            if not console_sql.strip():
                continue

            # Execute the SQL
            try:
                result = console_doris.exec_sql(console_sql)
                # Assuming exec_sql returns something displayable
                print("Execution result:")
                if (isinstance(result, list) and len(result) > 0 and
                        isinstance(result[0], dict) and
                        'Table' in result[0] and 'Create Table' in result[0]):
                    print_show_create_table(result)
                elif isinstance(result, dict) and 'data' in result:
                    print_data_table(result)
                else:
                    # 非 CREATE TABLE 的输出
                    print(result)
            except Exception as e:
                logger.error(f"SQL execution error: {e}")
                print(f"Error executing SQL: {e}")

        except KeyboardInterrupt:
            print("\nTo exit, please type 'exit;' or 'quit;'")
            continue


def print_data_table(result):
    data = result['data']
    if isinstance(data, list) and len(data) > 0:
        print("\n查询结果:")
        # 转换数据为表格格式
        headers = data[0].keys()
        rows = [list(item.values()) for item in data]
        # 处理None值为空字符串
        rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        # 打印表格
        print(tabulate(rows, headers=headers, tablefmt="grid"))
        # 显示记录数
        print(f"\n共 {len(data)} 条记录")
    else:
        print("\n查询结果为空")
    # 如果有异常信息则显示
    if result.get('exception'):
        print(f"\n警告: {result['exception']}")


def print_show_create_table(result):
    table_info = result[0]
    table_name = table_info['Table']
    create_table = table_info['Create Table']
    # 提取表注释（如果有）
    table_comment = ""
    comment_match = re.search(r"COMMENT\s*=\s*'([^']*)'", create_table, re.IGNORECASE)
    if comment_match:
        table_comment = comment_match.group(1)
    # 打印表信息
    print(f"\n表名: {table_name}")
    if table_comment:
        print(f"表注释: {table_comment}")
    print("-" * 50)
    # 格式化并打印字段信息
    print("\n字段结构:")
    # 提取字段定义部分
    fields_section = re.search(r'\(([\s\S]*?)\)\s*ENGINE', create_table)
    if fields_section:
        field_defs = fields_section.group(1).split('\n')
        for field in field_defs:
            field = field.strip()
            if not field or field.startswith('PRIMARY KEY') or field.startswith('DUPLICATE KEY'):
                continue

            # 提取字段名、类型和注释
            field_parts = re.split(r'\s+(?=(?:[^\']*\'[^\']*\')*[^\']*$)', field)
            field_name = field_parts[0].strip('`')
            field_type = field_parts[1] if len(field_parts) > 1 else ''
            field_comment = ""

            # 查找注释
            comment_match = re.search(r"COMMENT\s*'([^']*)'", field, re.IGNORECASE)
            if comment_match:
                field_comment = comment_match.group(1)

            # 打印字段信息
            print(f"{field_name:<20} {field_type:<15} {field_comment}")
    # 打印分区信息
    # partition_match = re.search(r'PARTITION BY [^\n]+\n\(([\s\S]*?)\)\n', create_table)
    # if partition_match:
    #     print("\n分区信息:")
    #     partitions = partition_match.group(1).split('\n')
    #     for part in partitions:
    #         part = part.strip()
    #         if part:
    #             print(f"  {part}")
    # 打印属性信息
    props_match = re.search(r'PROPERTIES\s*\(([\s\S]*?)\);', create_table)
    if props_match:
        print("\n表属性:")
        props = props_match.group(1).split('\n')
        for prop in props:
            prop = prop.strip(' ,"')
            if prop:
                print(f"  {prop}")


if __name__ == "__main__":
    console_simulator()
    # my_cfg = init_yml_cfg()['doris']
    # logger.info(f"my_cfg: {my_cfg}")
    # my_doris = Doris(my_cfg)
    # my_comment_list = my_doris.get_table_col_comment("a10analysis", "dws_dw_ycb_day")
    # logger.info(f"my_comment_list {my_comment_list}")
    # tables = my_doris.get_table_list()
    # logger.info(f"my_tables {tables}")
    # my_tb_schema_list = my_doris.get_schema_info()
    # logger.info(f"my_dt {my_tb_schema_list}")
    # llm_schema_info = my_doris.get_schema_for_llm()
    # logger.info(f"schema_for_llm {llm_schema_info}")
    # count = my_doris.count_dt()
    # logger.info(f"my_count {count}")
    # sample_dt = my_doris.exec_sql("select * from dws_dw_ycb_day limit 1")
    # logger.info(f"sample_dt {sample_dt}")
