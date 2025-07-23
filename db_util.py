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

DB_CONN_TIMEOUT=5      # 连接超时(秒)
DB_RW_TIMEOUT=20       # 数据读写超时(秒)
CFG_DB_FILE = "cfg.db"
CFG_DB_URI=f"sqlite:///{CFG_DB_FILE}"

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
            comment_map = {"YEAR":"年", "MONTH": "月"}
            with db_con.cursor() as cursor:
                cursor.execute(f"SHOW FULL COLUMNS FROM {full_table_name}")
                for col in cursor.fetchall():
                    comment_map[col[0].upper()] = DbUtl.get_punctuation_seg(col[8])
            processed_columns = []
            for col in raw_columns:
                col_upper = col.upper()
                comment = comment_map.get(col_upper, "")
                suffix, base_col = "", col
                patterns = [
                    (r'^(AVG|SUM|MAX|MIN|COUNT)\(([\w`]+)\)$', lambda m: (f"{m[1]}的", m[2].replace('`', ''))),
                    (r'^(TOTAL|AVG|SUM|MAX|MIN)_([\w`]+)$', lambda m: (f"{m[1]}的", m[2].replace('`', '')))
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
                    base_comment = DbUtl.get_punctuation_seg(comment)
                    base_comment = base_comment[:16]
                final_name = f"{base_comment}{suffix}" if base_comment else col
                processed_columns.append(final_name.strip())
            return processed_columns
        except Exception as e:
            logger.error(f"Error processing column names: {str(e)}")
            return raw_columns

    @staticmethod
    def get_punctuation_seg(text):
        punctuations = "，。！？；：“”‘’【】（）,.?!;:\"'[]{}"
        for i, c in enumerate(text):
            if c in punctuations:
                return text[:i]
        return text

    @staticmethod
    def sqlite_query_tool(db_con, query: str) -> dict:
        try:
            cursor = db_con.cursor()
            query = query.replace('\n', ' ')
            logger.debug(f"execute_query, {query}")
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
            logger.error(f"insert_delete_err: {e}, sql {sql}")
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
            dt = DbUtl.get_md_dt_from_data_frame(df)

        elif DataType.JSON.value in dt_fmt:
            dt = df.to_json(force_ascii=False, orient='records')
        else:
            info = f"error data format {data_format}"
            logger.error(info)
            raise info
        dt1 = dt.replace('\n', ' ')
        logger.info(f"output_data_dt:{dt1}")
        return dt

    @staticmethod
    def get_md_dt_from_data_frame(df):
        if df.empty:
            return ''
        return df.map(lambda x: f"{x:.0f}" if isinstance(x, (Decimal, float)) else x,
            na_action='ignore').to_markdown(index=False)

    @staticmethod
    def get_pretty_html(df):
        """
        :param df: a DataFrame
        output a pretty html content
        """
        return df.to_html(
            index=False,
            border=0
        ).replace(
            '<table',
            '<table style="border:1px solid #ddd; border-collapse:collapse; width:auto; table-layout:auto"'
        ).replace(
            '<th>',
            '<th style="background:#f8f9fa; padding:8px; border-bottom:2px solid #ddd; text-align:left; white-space:nowrap">'
        ).replace(
            '<td>',
            '<td style="padding:6px; border-bottom:1px solid #eee; white-space:nowrap">'
        )

    @staticmethod
    def mysql_output(cfg: dict, sql:str, data_format:str):
        """
        db_uri = mysql+pymysql://user:pswd@host/db
        """
        db_config = cfg.get('db', {})

        cif = DbUtl.build_mysql_con_dict_from_cfg(db_config)
        with pymysql.connect(
            host=cif['host'], port=cif['port'],
            user=cif['user'],password=cif['password'],
            database=cif['database'], charset=cif['charset'],
            connect_timeout=DB_CONN_TIMEOUT,
            read_timeout=DB_RW_TIMEOUT,
            write_timeout=DB_RW_TIMEOUT
        ) as my_conn:
            sql1 = sql.replace("\n", " ")
            logger.info(f"mysql_output_data, {sql1}, {data_format})")
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
                dsn=dsn,
                connect_timeout=DB_CONN_TIMEOUT,          # 连接超时5秒
            )
            conn.call_timeout = DB_RW_TIMEOUT * 1000       # 调用超时10秒
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
        logger.debug(f"sqlite_output, data_format {data_format}, my_dt, {my_dt}")
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
        sql1 = re.sub(r'LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?',
            f'LIMIT {page_size} OFFSET {offset}',
            origin_sql, flags=re.I, count=1
        )
        return re.sub(r' +', ' ', sql1)

    @staticmethod
    def gen_count_sql(origin_sql: str) -> str:
        """
        :param origin_sql: select a, b from c where a='foo' and b ='bar' limit xxx
        """
        if not origin_sql:
            raise RuntimeError("origin_sql_null_err")
        origin_sql = origin_sql.replace(';', '')
        origin_sql = re.sub(r'\s+', ' ', origin_sql).strip()
        cleaned_sql = re.sub(r'\s+ORDER\s+BY\s+.*?(?=(?:LIMIT|\bWHERE\b|$))', ' ', origin_sql, flags=re.I)
        cleaned_sql = re.sub(r'\s+LIMIT\s+\d+(\s*,\s*\d+)?', '', cleaned_sql, flags=re.I)  # 修正LIMIT匹配
        if re.search(r'\bGROUP\s+BY\b|\bDISTINCT\b', cleaned_sql, re.I):
            return f"SELECT COUNT(1) FROM ({cleaned_sql}) AS pagination_subquery"
        elif re.search(r'\b(COUNT|SUM|AVG|MAX|MIN)\s*\(', cleaned_sql, re.I):
            return "SELECT 1"
        else:
            return re.sub(
                r'^SELECT\s.*?\sFROM\s',
                'SELECT COUNT(1) FROM ',
                cleaned_sql,
                count=1,
                flags=re.I
            ).strip()

    @staticmethod
    def add_ou_id_condition(sql: str, ou_id_list: list):
        import re
        ou_id_str = ', '.join(map(str, ou_id_list))
        pattern = re.compile(
            r'(\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b)',
            re.IGNORECASE | re.DOTALL
        )

        first_match = pattern.search(sql)
        if not first_match:
            return sql.rstrip() + f" WHERE ou_id IN ({ou_id_str})"

        if first_match.group(1).upper().startswith('WHERE'):
            next_match = pattern.search(sql, first_match.end())
            insert_pos = next_match.start() if next_match else len(sql)
            return (
                sql[:insert_pos] +
                f" AND ou_id IN ({ou_id_str}) " +
                sql[insert_pos:]
            )

        # 情况2：第一个关键字非 WHERE（如 GROUP BY）
        insert_pos = first_match.start()
        return (
            sql[:insert_pos] +
            f" WHERE ou_id IN ({ou_id_str}) " +
            sql[insert_pos:]
        )

    @staticmethod
    def get_vdb_info_by_uid(uid: str, kdb_name=''):
        if not uid and uid.strip() != '':
            raise RuntimeError("uid_null_err")
        sql = f"select * from vdb_info where uid = '{uid}'"
        if kdb_name and kdb_name.strip() !='':
            sql += f" and name = '{kdb_name}'"
        logger.info(f"get_vdb_info_by_uid_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI,sql,DataType.JSON.value )
        logger.info(f"get_vdb_info_by_uid_dt {my_dt}")
        return my_dt

    @staticmethod
    def create_vdb_info(kdb_name: str, uid: str, is_public=False):
        sql = f"insert into vdb_info (name, uid, is_public) values ('{kdb_name}', '{uid}', '{is_public}')"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"create_vdb_info_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"create_vdb_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def active_vdb(file_id: int, file_path: str):
        if not file_id or not file_path:
            raise RuntimeError(f"param_null_err, {file_id}, {file_path}")
        sql = f"update file_info set file_path = '{file_path}' where id = '{file_id}' limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI,sql,DataType.JSON.value )
        logger.info(f"update_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_by_uid_and_kb_id(uid: str, kb_id: str):
        if not uid or not kb_id:
            logger.error(f"uid_or_kb_id_null_err, uid = {uid}, kb_id = {kb_id}")
            raise RuntimeError("uid_or_kb_id_null_err")
        sql = f"delete from vdb_info where uid = '{uid}' and id = '{kb_id}'"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_vdb_by_uid_and_kb_id_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_vdb_by_uid_and_kb_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_list(uid: str, vdb_id: str):
        if not uid or not vdb_id:
            raise RuntimeError(f"param_null_err, {uid}, {vdb_id}")
        sql = f"select * from file_info where uid = '{uid}' and vdb_id = '{vdb_id}'"
        logger.info(f"get_vdb_file_list_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI,sql,DataType.JSON.value )
        logger.info(f"get_vdb_file_list_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_file_info(file_name: str, uid: str, vdb_id: str):
        if not uid or not file_name or not vdb_id:
            raise RuntimeError(f"param_null_err {file_name}, {uid}, {vdb_id}")
        sql = f"select * from file_info where name = '{file_name}' and uid = '{uid}' and vdb_id = '{vdb_id}' limit 1"
        logger.info(f"get_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI,sql,DataType.JSON.value )
        logger.info(f"get_file_info_dt {my_dt}")
        return my_dt


    @staticmethod
    def delete_file_by_uid_vbd_id_file_name(file_name: str, uid: str, vdb_id: str):
        sql = f"delete from file_info where name ='{file_name}' and uid='{uid}' and vdb_id='{vdb_id}' limit 1 "
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_file_name_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_file_name_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_file_by_uid_vbd_id_file_id(file_id: str, uid: str, vdb_id: str):
        sql = f"delete from file_info where id ='{file_id}' and uid='{uid}' and vdb_id='{vdb_id}' limit 1 "
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_file_id_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_file_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_file_by_uid_vbd_id(uid: str, vdb_id: str):
        sql = f"delete from file_info where uid='{uid}' and vdb_id='{vdb_id}'"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def save_file_info(original_file_name: str, saved_file_name:str, uid: str, vdb_id: str):
        sql = (f"insert into file_info (name, uid, vdb_id, file_path) values"
               f" ('{original_file_name}', '{uid}', '{vdb_id}', '{saved_file_name}')")
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"save_file_info_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"save_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def update_file_info(file_id: int, file_path: str):
        if not file_id or not file_path:
            raise RuntimeError(f"param_null_err, {file_id}, {file_path}")
        sql = f"update file_info set file_path = '{file_path}' where id = '{file_id}' limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI,sql,DataType.JSON.value )
        logger.info(f"update_file_info_dt {my_dt}")
        return my_dt
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
    my_dt = DbUtl.sqlite_output(CFG_DB, "select * from schema_info where entity = 'dws_dw_ycb_day'", DataType.JSON.value)
    logger.info(f"my_dt {my_dt}")

def test_add_ou_id_condition():
    sql = f'''
        SELECT province, COUNT(id) AS new_user_count 
        FROM user_info 
        WHERE create_time >= '2024-01-01' AND create_time <= '2024-12-31' 
        GROUP BY province 
        ORDER BY new_user_count DESC 
        LIMIT 20;
        '''
    out_sql = DbUtl.add_ou_id_condition(sql, [123, 456])
    logger.info(f"out_sql {out_sql}")
    sql = "select a, max(f) from b \n group by a order by e limit c, d"
    out_sql = DbUtl.add_ou_id_condition(sql, [123, 456])
    logger.info(f"out_sql {out_sql}")

def test_get_count_sql():

    sql = "select a, count(1) from b where c='e' and d='f' group by g order by h limit 100, 20;"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select a, a1 from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select distinct(a1) from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select sum(a1) from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select max(a1) from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select min(a1) from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select count(1) from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")
    sql = "select count(*) from b where c='e' and d='f' order by h LIMIT 10, 20"
    count_sql = DbUtl.gen_count_sql(sql)
    logger.info(f"count_sql, {count_sql}, original_sql {sql}")


if __name__ == "__main__":
    # test_get_count_sql()
    test_add_ou_id_condition()

    # test_db()
    # sql1 = "select a from b where c=d limit 30"
    # new_sql1 = DbUtl.get_page_sql(sql1, 5)
    # logger.info(f"page_sql1, {new_sql1}")

    # sql2 = 'SELECT \n  OU_ID, \n  COMPANY_NAME, \n  OU_CODE, \n  CALC_DT, \n  METER_NUM, \n  METER_R_NUM, \n  EXCEPTION_NUM, \n  CUSTOMER_NUM, \n  CUSTOMER_NEW_NUM, \n  CALC_VOLUME, \n  CALC_AMOUNT, \n  PAY_AMOUNT, \n  METER_R_RATE, \n  ACC_TYPE_NAME, \n  METER_MNFT_NAME, \n  METER_MODEL_NAME, \n  COMMUNITY, \n  METER_NUM_SUM, \n  METER_MODEL_CODE, \n  COUNTY, \n  RG_METER_CATEGORY, \n  RATE_NAME \nFROM \n  dws_dw_ycb_day \nORDER BY \n  CALC_DT DESC\n LIMIT 10;'
    # new_sql2 = DbUtl.get_page_sql(sql2, 5)
    # logger.info(f"page_sql2, {new_sql2}")
    # count_sql2 = DbUtl.gen_count_sql(sql2)
    # logger.info(f"count_sql2, {count_sql2}")
    # txt ='用气量, 单位:立方米'
    # logger.info(DbUtl.get_punctuation_seg(txt))