#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sqlite3
import logging.config

from db_util import sqlite_query_tool, sqlite_insert_tool

# 加载配置
logging.config.fileConfig('logging.conf', encoding="utf-8")

logger = logging.getLogger(__name__)
config_db = "config.db"


def auth_user(user:str, t: str) -> dict:
    auth_result ={"pass": False, "uid": ""}
    with sqlite3.connect(config_db) as my_conn:
        sql = f"select id from user where name='{user}' and t = '{t}' limit 1"
        check_info = sqlite_query_tool(my_conn, sql)
        user_id = json.loads(check_info)['data']
    if user_id:
        auth_result = True
    return auth_result

def get_uid_by_user(usr:str) ->str:
    check_sql = f"select id from user where name='{usr}' limit 1"
    uid = ''
    with sqlite3.connect(config_db) as my_conn:
        check_info = sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_info {check_info}")
        check_data = json.loads(check_info)['data']
        try:
            uid = check_data[0][0]
        except (IndexError, TypeError) as e:
            logger.info(f"user info for {usr} can't be found")
    return uid

def get_user_by_uid(uid:str)->str | None:
    user = None
    with sqlite3.connect(config_db) as my_conn:
        try:
            sql = f"select name from user where id='{uid}' limit 1"
            check_info = sqlite_query_tool(my_conn, sql)
            user_dt = json.loads(check_info)['data']
            user = user_dt[0][0]
            logger.info(f"get_user {user} with uid {uid}")
        except Exception as e:
            logger.info(f"no_user_info_found_for_uid, {uid}")
    return user

def get_data_source_config_by_uid(uid:str) -> dict:
    config = {}
    with sqlite3.connect(config_db) as my_conn:
        check_sql = (f"select uid, db_type, db_name, db_host, db_port,"
                     f" db_usr, db_psw from db_config where uid='{uid}' limit 1")
        db_config_info = sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_sql {check_sql}")
        check_info = json.loads(db_config_info)['data']
        try:
            check_uid = check_info[0][0]
            config = {
                "uid": check_uid,
                "db_type": check_info[0][1],
                "db_name": check_info[0][2],
                "db_host": check_info[0][3],
                "db_port": check_info[0][4],
                "db_usr":  check_info[0][5],
                "db_psw":  check_info[0][6],
            }
        except (IndexError, TypeError) as e:
            logger.info(f"no_db_config_for {uid}")
    logger.info(f"db_config_info {config}")
    return config

def save_data_source_config(config_info: dict) -> bool:
    save_result = False
    if not config_info['uid']:
        logger.error("uid in config_info is null")
        return save_result
    current_config = get_data_source_config_by_uid(config_info['uid'])
    if current_config:
        exec_sql = (f"update db_config set "
                    f"db_type ='{config_info["db_type"]}', db_host ='{config_info["db_host"]}', db_port ='{config_info["db_port"]}',"
                    f" db_name='{config_info["db_name"]}', db_usr='{config_info["db_usr"]}', db_psw='{config_info["db_psw"]}'"
                    f" where uid = '{config_info["uid"]}'")
    else:
        exec_sql = (f"insert into db_config (uid, db_type, db_host, db_name, db_usr, db_psw) "
                    f"values ('{config_info["uid"]}', '{config_info["db_type"]}', '{config_info["db_host"]}', "
                    f"'{config_info["db_name"]}', '{config_info["db_usr"]}', '{config_info["db_psw"]}')")
    with sqlite3.connect(config_db) as my_conn:
        save_result = False
        try:
            result = sqlite_insert_tool(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result