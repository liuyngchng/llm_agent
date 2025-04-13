#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sqlite3
import logging.config

from db_util import sqlite_query_tool, sqlite_insert_tool

# 加载配置
logging.config.fileConfig('logging.conf', encoding="utf-8")

logger = logging.getLogger(__name__)

def get_uid_by_user(usr:str, sqlite_db: str) ->str:
    check_sql = f"select id from user where name='{usr}' limit 1"
    uid = ''
    with sqlite3.connect(sqlite_db) as my_conn:
        check_info = sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_info {check_info}")
        check_data = json.loads(check_info)['data']

        try:
            uid = check_data[0][0]
        except (IndexError, TypeError) as e:
            logger.exception(f"user info for {usr} can't be found")
    return uid

def get_db_config_by_uid(uid:str, sqlite_db: str) -> dict:
    config = {}
    with sqlite3.connect(sqlite_db) as my_conn:
        check_sql = f"select uid, db_type, db_name, db_host, db_usr, db_psw from db_config where uid='{uid}' limit 1"
        db_config_info = sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_info {db_config_info}")
        check_info = json.loads(db_config_info)['data']
        try:
            uid = check_info[0][0]
            config = {
                "waring_info": "",
                "uid": uid,
                "db_type": check_info[0][1],
                "db_name": check_info[0][2],
                "db_host": check_info[0][3],
                "db_usr": check_info[0][4],
                "db_psw": check_info[0][5],
            }
        except (IndexError, TypeError) as e:
            logger.exception(f"no_db_config_for_uid {uid}")
    return config

def save_data_source_config(config_db: str, config_info: dict) -> bool:
    insert_result = False
    with sqlite3.connect(config_db) as my_conn:
        try:

            insert_sql = (f"insert into db_config (uid, db_type, db_host, db_name, db_usr, db_psw) "
                   f"values ('{config_info["uid"]}', '{config_info["db_type"]}', '{config_info["db_host"]}', "
                          f"'{config_info["db_name"]}', '{config_info["db_usr"]}', '{config_info["db_psw"]}')")
            sqlite_insert_tool(my_conn, insert_sql)
            logger.info(f"exec_sql_success {insert_sql}")
            insert_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {insert_sql}")
    return insert_result