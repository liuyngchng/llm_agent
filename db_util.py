#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import re
from decimal import Decimal

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
    def mysql_query_tool(db_con, query: str) -> dict:
        try:
            with db_con.cursor() as cursor:
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                # data = cursor.fetchall()
                data = [
                    tuple(
                        item.isoformat() if isinstance(item, (datetime.date, datetime.datetime)) else item
                        for item in row
                    )
                    for row in cursor.fetchall()
                ]
                # return json.dumps({"columns": columns, "data": data}, ensure_ascii=False, default=str)
                return {"columns": columns, "data": data}
        except Exception as e:
            logger.error(f"mysql_query_err: {e}")
            raise e


    @staticmethod
    def get_col_name_from_sql_for_mysql(db_con, raw_columns: list, sql: str) -> list:
        """
        get column name from SQL, for MySQL DB
        :param db_con: database connection info
        :param raw_columns: original columns
        :param sql: sql need to be executed next
        :return: the column name more explainable
        """
        try:
            table_match = re.search(r'(?i)FROM\s+([`\w.]+)', sql)
            table_name = table_match.group(1).replace('`', '') if table_match else None
            if not table_name:
                return raw_columns
            if '.' in table_name:
                schema_name, table_name = table_name.split('.')[:2]
                full_table_name = f"{schema_name}.{table_name}"
            else:
                full_table_name = table_name
            comment_map = {}
            with db_con.cursor() as cursor:
                cursor.execute(f"SHOW FULL COLUMNS FROM {full_table_name}")
                for col in cursor.fetchall():
                    comment_map[col[0].upper()] = col[8]
            processed_columns = []
            for col in raw_columns:
                col_upper = col.upper()
                comment = comment_map.get(col_upper, "")
                suffix, base_col = "", col
                patterns = [
                    (r'^(AVG|SUM|MAX|MIN|COUNT)\(([\w`]+)\)$', lambda m: (f"{m[1]}的", m[2].replace('`', ''))),
                    (r'^(TOTAL|AVG|MAX|MIN)_([\w`]+)$', lambda m: (f"{m[1]}的", m[2].replace('`', '')))
                ]

                for pattern, handler in patterns:
                    match = re.match(pattern, col_upper)
                    if match:
                        suffix_part, base_col = handler(match)
                        suffix = {"AVG的": "平均值", "SUM的": "总和",
                                  "MAX的": "最大值", "MIN的": "最小值",
                                  "COUNT的": "计数", "TOTAL的": "总和"}.get(suffix_part, "")
                        base_comment = comment_map.get(base_col.upper(), "")
                        break
                else:
                    base_comment = comment
                final_name = f"{base_comment}{suffix}" if base_comment else col
                processed_columns.append(final_name.strip())
            return processed_columns
        except Exception as e:
            logger.error(f"Error processing column names: {str(e)}")
            return raw_columns


    @staticmethod
    def sqlite_query_tool(db_con, query: str) -> dict:
        try:
            cursor = db_con.cursor()
            logger.debug(f"execute_query {query}")
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            return {"columns": columns, "data": data}
        except Exception as e:
            logger.exception(f"sqlite_query_err")
            return {"error": str(e)}

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
            data = DbUtl.sqlite_query_tool(db_con, sql)
        elif isinstance(db_con, pymysql.Connection):
            data = DbUtl.mysql_query_tool(db_con, sql)
            try:
                data['columns'] = DbUtl.get_col_name_from_sql_for_mysql(
                    db_con,
                    data['columns'],
                    sql
                )
            except Exception as e:
                logger.error(f"col_name_hack_failed, {str(e)}")
        elif isinstance(db_con, oracledb.Connection):
            data = DbUtl.oracle_query_tool(db_con, sql)
        else:
            logger.error(f"database_type_error, {__file__}")
            raise "database type error"

        logger.info(f"data {data} for {db_con}")
        df = pd.DataFrame(data['data'], columns=data['columns'])
        dt_fmt = data_format.lower()

        if DataType.HTML.value in dt_fmt:
            dt = DbUtl.get_pretty_html(df)
        elif DataType.MARKDOWN.value in dt_fmt:
            if df.empty:
                dt = ''
            else:
                dt = df.map(lambda x: f"{x:.0f}" if isinstance(x, Decimal) else x,
                    na_action='ignore').to_markdown(index=False)

        elif DataType.JSON.value in dt_fmt:
            dt = df.to_json(force_ascii=False, orient='records')
        else:
            info = f"error data format {data_format}"
            logger.error(info)
            raise info
        logger.info(f"output_data_dt:\n{dt}\n")
        return dt

    @staticmethod
    def get_pretty_html(df):
        return df.to_html(
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
    def oracle_query_tool(db_con, query: str) -> dict:
        try:
            cursor = db_con.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            return {"columns": columns, "data": data}
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
        db_type_cfg = db_cfg['type'].lower()
        if DBType.DORIS.value in db_type_cfg:
            my_db_uri = db_cfg['url']
            logger.info(f"db_uri_for_{db_type_cfg}, {my_db_uri}")
            return my_db_uri
        if all(key in db_cfg for key in ['type', 'name', 'host', 'user', 'password']):
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

    @staticmethod
    def get_page_sql(origin_sql: str, page_no=1, page_size=20):
        """
        : param sql: format as : select a, b, c from c.d where e.f limit g
        """
        if not origin_sql:
            raise RuntimeError("origin_sql_null_err")
        origin_sql = origin_sql.replace("\n", " ")
        offset = (page_no - 1) * page_size
        # 替换或添加 LIMIT + OFFSET
        sql1 = re.sub(r'LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?',
                      f'LIMIT {page_size} OFFSET {offset}',
                      origin_sql, flags=re.I, count=1)
        return re.sub(r' +', ' ',sql1)

    @staticmethod
    def gen_count_sql(origin_sql: str) -> str:
        """
        :param origin_sql: select a, b from c where a='foo' and b ='bar' limit xxx
        """
        if not origin_sql:
            raise RuntimeError("origin_sql_null_err")
        origin_sql = origin_sql.replace("\n", " ")
        cleaned_sql = re.sub(r'\s+ORDER\s+BY\s+.*?(?=LIMIT|\bWHERE\b|$)', ' ', origin_sql, flags=re.I)
        cleaned_sql = re.sub(r'\s+LIMIT\s+\d+.*?(?=\s|;|$)', ' ', cleaned_sql, flags=re.I)
        count_sql = re.sub(r'^SELECT\s.*?\sFROM', 'SELECT COUNT(1) FROM ', cleaned_sql, count=1, flags=re.I)
        return count_sql


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
    db_uri = "sqlite:///cfg.db"
    my_dt = DbUtl.sqlite_output(db_uri, "select * from schema_info where entity = 'dws_dw_ycb_day'", DataType.JSON.value)
    logger.info(f"my_dt {my_dt}")


if __name__ == "__main__":
    # test_db()
    # sql1 = "select a from b where c=d limit 30"
    # new_sql1 = DbUtl.get_page_sql(sql1, 5)
    # logger.info(f"page_sql1, {new_sql1}")

    sql2 = 'SELECT \n  OU_ID, \n  COMPANY_NAME, \n  OU_CODE, \n  CALC_DT, \n  METER_NUM, \n  METER_R_NUM, \n  EXCEPTION_NUM, \n  CUSTOMER_NUM, \n  CUSTOMER_NEW_NUM, \n  CALC_VOLUME, \n  CALC_AMOUNT, \n  PAY_AMOUNT, \n  METER_R_RATE, \n  ACC_TYPE_NAME, \n  METER_MNFT_NAME, \n  METER_MODEL_NAME, \n  COMMUNITY, \n  METER_NUM_SUM, \n  METER_MODEL_CODE, \n  COUNTY, \n  RG_METER_CATEGORY, \n  RATE_NAME \nFROM \n  dws_dw_ycb_day \nORDER BY \n  CALC_DT DESC\n LIMIT 10;'
    new_sql2 = DbUtl.get_page_sql(sql2, 5)
    logger.info(f"page_sql2, {new_sql2}")
    count_sql2 = DbUtl.gen_count_sql(sql2)
    logger.info(f"count_sql2, {count_sql2}")