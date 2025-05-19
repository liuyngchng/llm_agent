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
            raise f"exec_sql_exception_{sql}"

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

    def count_dt(self):
        count_sql = "select count(1) from dws_dw_ycb_day"
        count_body = self.build_json(count_sql)
        response = requests.post(self.url, json=count_body, headers=self.headers, proxies={'http': None, 'https': None})
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

            columns = list(data[0].keys()) if data else []
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


if __name__ == "__main__":
    my_cfg = init_yml_cfg()['doris']
    logger.info(f"my_cfg: {my_cfg}")
    my_doris = Doris(my_cfg)
    tables = my_doris.get_table_list()
    logger.info(f"my_tables {tables}")
    my_tb_schema_list = my_doris.get_schema_info()
    logger.info(f"my_dt {my_tb_schema_list}")
    llm_schema_info = my_doris.get_schema_for_llm()
    logger.info(f"schema_for_llm {llm_schema_info}")
    count = my_doris.count_dt()
    logger.info(f"my_count {count}")
    sample_dt = my_doris.exec_sql("select * from dws_dw_ycb_day limit 1")
    logger.info(f"sample_dt {sample_dt}")