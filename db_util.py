#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import sqlite3
import json
import pandas as pd
import logging.config
import oracledb

from my_enums import DataType, DBType
from urllib.parse import urlparse, unquote, urlencode, quote
from sys_init import init_yml_cfg
"""
mysql+pymysql://root:123456@localhost:3306/test
postgresql+psycopg2://postgres:123456@localhost:5432/test
sqlite:///test.db
mssql+pymssql://<username>:<password>@<freetds_name>/?charset=utf8
oracle+oracledb://user:pass@hostname:port[/dbname][?service_name=<service>[&key=value&key=value...]]
"""

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

class DbUtl:
    """
    database util class, for process data output, database coneection etc.
    """
    @staticmethod
    def mysql_query_tool(db_con, query: str) -> str:
        try:
            with db_con.cursor() as cursor:  # 使用with自动管理游标
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                data = cursor.fetchall()
                return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"mysql_query_tool_err: {e}")
            raise e

    @staticmethod
    def sqlite_query_tool(db_con, query: str) -> str:
        try:
            cursor = db_con.cursor()
            logger.debug(f"execute_query {query}")
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
        except Exception as e:
            logger.exception(f"sqlite_query_err")
            return json.dumps({"error": str(e)})

    @staticmethod
    def sqlite_insert_delete_tool(db_con, sql: str) -> dict:
        # ///TODO 防止sql注入
        try:
            cursor = db_con.cursor()
            cursor.execute(sql)
            db_con.commit()
            return {"result":True, "affected_rows": cursor.rowcount}
        except Exception as e:
            db_con.rollback()
            logger.error(f"save_data_err: {e}, sql {sql}")
            return {"result":False, "error": "save data failed"}

    @staticmethod
    def output_data(db_con, sql:str, data_format:str) -> str:
        if isinstance(db_con, sqlite3.Connection):
            result = DbUtl.sqlite_query_tool(db_con, sql)
        elif isinstance(db_con, pymysql.Connection):
            result = DbUtl.mysql_query_tool(db_con, sql)
        elif isinstance(db_con, oracledb.Connection):
            result = DbUtl.oracle_query_tool(db_con, sql)

        else:
            logger.error(f"database_type_error, {__file__}")
            raise "database type error"

        data = json.loads(result)
        logger.info(f"data {data} for {db_con}")
        # 生成表格
        df = pd.DataFrame(data['data'], columns=data['columns'])
        dt_fmt = data_format.lower()

        if DataType.HTML.value in dt_fmt:
            # dt = df.to_html()  #生成网页表格
            dt = df.to_html(
                index=False,
                border=0
            ).replace(
                '<table',
                '<table style="border:1px solid #ddd; border-collapse:collapse; width:100%"'
            ).replace(
                '<th>',
                '<th style="background:#f8f9fa; padding:8px; border-bottom:2px solid #ddd; text-align:left">'
            ).replace(
                '<td>',
                '<td style="padding:6px; border-bottom:1px solid #eee">'
            )
        elif DataType.MARKDOWN.value in dt_fmt:
            if df.empty:
                dt = ''
            else:
                dt = df.to_markdown(index=False)  # 控制台打印美观表格
        elif DataType.JSON.value in dt_fmt:
            dt = df.to_json(force_ascii=False, orient='records')
        else:
            info = f"error data format {data_format}"
            logger.error(info)
            raise info
        logger.info(f"output_data_dt:\n{dt}\n")
        return dt

    @staticmethod
    def mysql_output(cfg: dict, sql:str, data_format:str):
        """
        db_uri = mysql+pymysql://user:pswd@host/db
        """
        db_config = cfg.get('db', {})

        cif = DbUtl.build_mysql_con_dict_from_cfg(db_config)
        with pymysql.connect(host=cif['host'],port=cif['port'],user=cif['user'],password=cif['password'],
                             database=cif['database'],charset=cif['charset']) as my_conn:
            logger.info(f"output_data({my_conn}, \n{sql}\n, {data_format})")
            dt = DbUtl.output_data(my_conn, sql, data_format)
        return dt

    @staticmethod
    def build_mysql_con_dict_from_cfg(db_config: dict) -> dict:
        cif = {"charset":"utf8mb4"}
        if all(key in db_config for key in ['name', 'host', 'user', 'password']):
            logger.info("connect db with name, host, user, password")
            cif['host'] = db_config['host']
            cif['port'] = db_config.get("port", 3306)
            cif['user'] = db_config['user']
            cif['password'] = db_config['password']
            cif['database'] = db_config['name']
        else:
            logger.info("connect db with db_uri")
            parsed_uri = urlparse(db_config['uri'])
            logger.info(f"host[{parsed_uri.hostname}], user[{parsed_uri.username}], "
                        f"password[{parsed_uri.password}], database[{parsed_uri.path[1:]}]")
            cif['host'] = unquote(parsed_uri.hostname)
            cif['port'] = parsed_uri.port or 3306
            cif['user'] = unquote(parsed_uri.username)
            cif['password'] = unquote(parsed_uri.password)
            cif['database'] = parsed_uri.path[1:]
        return cif

    #################### for support oracle DB #########################
    @staticmethod
    def oracle_query_tool(db_con, query: str) -> str:
        try:
            cursor = db_con.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
        except Exception as e:
            logger.exception("oracle_query_tool_err")
            raise e

    @staticmethod
    def oracle_output(cfg: dict, sql: str, data_format: str):
        """
        cfg['db']['uri'] =
        oracle+cx_oracle://user:password@host:port/service_name
        oracle+oracledb://user:pass@hostname:port[/dbname][?service_name=<service>[&key=value&key=value...]]
        连接上oracle服务之后，可以通过以下方法获取 service_name
        SELECT VALUE FROM V$PARAMETER WHERE NAME = 'service_names';
        """
        db_config = cfg.get('db', {})
        logger.info(f"db_config {db_config}")
        if all(key in db_config for key in ['name', 'host', 'user', 'password']):
            dsn = oracledb.makedsn(db_config['host'],db_config.get('port', 1521),service_name=db_config['name'])
            conn =  oracledb.connect(
                user=db_config['user'],
                password=db_config['password'],
                dsn=dsn
            )
        else:
            parsed_uri = urlparse(db_config['uri'])
            port = parsed_uri.port or 1521
            dsn = oracledb.makedsn(
                unquote(parsed_uri.hostname),
                port,
                service_name=unquote(parsed_uri.path[1:])
            )
            conn = oracledb.connect(
                user=unquote(parsed_uri.username),
                password=unquote(parsed_uri.password),
                dsn=dsn
            )
        dt = DbUtl.output_data(conn, sql, data_format)
        conn.close()
        return dt

    @staticmethod
    def get_orc_db_info(cfg: dict) -> list:
        dsn = oracledb.makedsn(cfg['db']['host'], cfg['db']['port'], service_name=cfg['db']['name'])
        with oracledb.connect(user=cfg['db']['user'], password=cfg['db']['password'], dsn=dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT table_name FROM user_tables")
                return [row[0] for row in cursor]

    #################### for support oracle DB #########################

    @staticmethod
    def sqlite_output(db_uri: str, sql:str, data_format:str):
        """
        cfg["db_uri"] = "sqlite:///test1.db"
        """

        db_file = db_uri.split('/')[-1]
        with sqlite3.connect(db_file) as my_conn:
            logger.debug(f"connect_to_db_file {db_file}")
            my_dt = DbUtl.output_data(my_conn, sql, data_format)
        if DataType.JSON.value ==  data_format:
            my_dt = json.loads(my_dt)
        return my_dt

    @staticmethod
    def get_db_uri(cfg: dict) -> str:
        """
        mysql+pymysql://user:pswd@host/db
        oracle+cx_oracle://user:password@host:port/service_name
        """
        db_cfg = cfg.get('db', {})
        if all(key in db_cfg for key in ['type', 'name', 'host', 'user', 'password']):
            db_type_cfg = db_cfg['type'].lower()
            if DBType.MYSQL.value in db_type_cfg:
                usr = quote(db_cfg['user'])
                pwd = quote(db_cfg['password'], safe='')
                my_db_uri = (f"mysql+pymysql://{usr}:{pwd}"
                             f"@{db_cfg['host']}:{db_cfg.get('port', 3306)}/{db_cfg['name']}")
            elif DBType.ORACLE.value in db_type_cfg:
                usr = quote(db_cfg['user'])
                pwd = quote(db_cfg['password'])
                my_db_uri = (f"oracle+cx_oracle://{usr}:{pwd}"
                             f"@{db_cfg['host']}:{db_cfg.get('port', 1521)}/?service_name={db_cfg['name']}")
            elif DBType.DORIS.value in db_type_cfg:
                my_db_uri = f"{DBType.DORIS.value}_http://{db_cfg['host']}:{db_cfg.get('port', 31683)}/api/db/execute"
            else:
                raise "unknown db type in config txt_file"
        elif all(key in db_cfg for key in ['type', 'name']):
            db_type_cfg = db_cfg['type'].lower()
            if DBType.SQLITE.value in db_type_cfg:
                my_db_uri = f"sqlite:///{db_cfg['name']}"
            else:
                raise "one of the following key ['type', 'name'] missed in config txt_file"
        else:
            raise "one of the following key ['type', 'name', 'host', 'user', 'password'] missed in config txt_file"
        logger.info(f"db_uri_for_{db_type_cfg}, {my_db_uri}")
        return my_db_uri


def test_db():
    my_sql = "SELECT * from order_info"
    my_cfg = init_yml_cfg()
    logger.info(f"my_cfg {my_cfg}")
    my_db_util = DbUtl()
    db_uri = my_db_util.get_db_uri(my_cfg)
    db_uri = db_uri.lower()
    logger.info(f"db_uri {db_uri}")
    if DBType.SQLITE.value in db_uri:
        my_dt = my_db_util.sqlite_output(db_uri, my_sql, 'json')
    elif DBType.MYSQL.value in db_uri:
        my_dt = my_db_util.mysql_output(my_cfg, my_sql, 'json')
    elif DBType.ORACLE.value in db_uri:
        my_dt = my_db_util.oracle_output(my_cfg, my_sql, 'json')
    else:
        my_dt = None
        raise "check your config txt_file to config correct [dt_uri]"

    logger.info(f"my_dt\n{my_dt}\n")

def test_url():
    url_params = urlencode({"test":'张三'}, encoding="UTF-8")
    logger.info(f"url_encode test:\n {url_params}\n")
    params = [("name", "张三"), ("age", 20), ("gender", "男")]
    url_params = urlencode(params, encoding="UTF-8")
    logger.info(f"url_encode test:\n {url_params}\n")
    decode_params = unquote(url_params)
    logger.info(f"url_decode test:\n {decode_params}\n")

def test_sqlite():
    db_uri = "sqlite:///config.db"
    my_dt = DbUtl.sqlite_output(db_uri, "select * from schema_info where entity = 'dws_dw_ycb_day'", DataType.JSON.value)
    logger.info(f"my_dt {my_dt}")
if __name__ == "__main__":
    # test_db()
    test_sqlite()