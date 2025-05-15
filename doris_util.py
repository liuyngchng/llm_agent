#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import requests
import logging.config
from sys_init import init_yml_cfg


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

class Doris:
    """
    A doris data source class
    """
    def __init__(self, cfg: dict):
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
            "tenantName": cfg['tenantName'],
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
        return response.json()

    def get_table_list(self):
        get_table_list_sql = "show tables"
        my_json = self.exec_sql(get_table_list_sql)
        logger.info(f"response {my_json}")
        return my_json["data"][0][f"Tables_in_{self.data_source}"]

    def get_schema(self):
        """
        get schema
        """
        get_schema_sql = f"show create table {self.data_source}.{self.get_table_list()}"
        logger.info(f"get_schema_sql {get_schema_sql}")
        my_json = self.exec_sql(get_schema_sql)
        logger.info(f"response {my_json}")
        return my_json["data"][0].get('Create Table').split('ENGINE')[0]

    def count_dt(self):
        count_sql = "select count(1) from dws_dw_ycb_day"
        count_body = self.build_json(count_sql)
        response = requests.post(self.url, json=count_body, headers=self.headers, proxies={'http': None, 'https': None})
        my_json = response.json()['data'][0]['count(1)']
        logger.info(f"response {my_json}")
        return my_json

if __name__ == "__main__":
    my_cfg = init_yml_cfg()['doris']
    logger.info(f"my_cfg: {my_cfg}")
    my_doris = Doris(my_cfg)
    tables = my_doris.get_table_list()
    logger.info(f"my_tables {tables}")
    dt = my_doris.get_schema()
    logger.info(f"my_dt {dt}")
    count = my_doris.count_dt()
    logger.info(f"my_count {count}")