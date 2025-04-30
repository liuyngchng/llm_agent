#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import copy
import sqlite3
import logging.config
import time

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

from sqlalchemy import false

from db_util import sqlite_query_tool, sqlite_insert_tool

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)
config_db = "config.db"
user_sample_data_db = "user_info.db"


def auth_user(user:str, t: str, cfg: dict) -> dict:
    auth_result ={"pass": False, "uid": ""}
    with sqlite3.connect(config_db) as my_conn:
        sql = f"select id, role from user where name='{user}' and t = '{t}' limit 1"
        check_info = sqlite_query_tool(my_conn, sql)
        user_dt = json.loads(check_info)['data']

    if user_dt:
        auth_result["pass"] = True
        auth_result["uid"] = user_dt[0][0]
        auth_result["role"] = user_dt[0][1]
        auth_result["t"] = encrypt(str(time.time() * 1000), cfg['sys']['cypher_key'])
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

def get_user_name_by_uid(uid:str)-> str | None:
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

def get_user_role_by_uid(uid:str)-> str | None:
    role = None
    with sqlite3.connect(config_db) as my_conn:
        try:
            sql = f"select role from user where id='{uid}' limit 1"
            check_info = sqlite_query_tool(my_conn, sql)
            user_dt = json.loads(check_info)['data']
            role = user_dt[0][0]
            logger.info(f"role {role}, uid {uid}")
        except Exception as e:
            logger.info(f"no_user_info_found_for_uid, {uid}")
    return role

def get_data_source_config_by_uid(uid:str, cfg: dict) -> dict:
    config = {}
    with sqlite3.connect(config_db) as my_conn:
        check_sql = (f"select uid, db_type, db_name, db_host, db_port,"
                     f" db_usr, db_psw from db_config where uid='{uid}' limit 1")
        db_config_info = sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_sql {check_sql}")
        check_info = json.loads(db_config_info)['data']
        if not check_info:
            logger.info(f"no_db_config_for_uid {uid}")
            return config
        try:
            check_uid = check_info[0][0]
            config = {
                "uid": check_uid,
                "db_type": check_info[0][1],
                "db_name": check_info[0][2],
                "db_host": check_info[0][3],
                "db_port": check_info[0][4],
                "db_usr":  decrypt(check_info[0][5], cfg['sys']['cypher_key']),
                "db_psw":  decrypt(check_info[0][6], cfg['sys']['cypher_key']),
            }
        except Exception as e:
            logger.exception("exception_occurred_get_data_source_config_by_uid")
            logger.info(f"no_db_config_for_uid {uid}")
    logger.info(f"db_config_info_for_uid_{uid}: {config}")
    return config

def save_data_source_config(data_source_cfg: dict, cfg: dict) -> bool:
    save_result = False
    if not data_source_cfg['uid']:
        logger.error("uid_in_data_source_cfg_is_null")
        return save_result
    logger.info("start_encrypt_db_source_user_and_password")
    data_source_cfg['db_usr_cypher'] = encrypt(data_source_cfg['db_usr'], cfg['sys']['cypher_key'])
    data_source_cfg['db_psw_cypher'] = encrypt(data_source_cfg['db_psw'], cfg['sys']['cypher_key'])
    current_config = get_data_source_config_by_uid(data_source_cfg['uid'], cfg)
    if current_config:
        exec_sql = (f'''
                    update db_config set 
                    db_type ='{data_source_cfg["db_type"]}', 
                    db_host ='{data_source_cfg["db_host"]}', 
                    db_port ='{data_source_cfg["db_port"]}',
                    db_name='{data_source_cfg["db_name"]}', 
                    db_usr='{data_source_cfg["db_usr_cypher"]}', 
                    db_psw='{data_source_cfg["db_psw_cypher"]}'
                    where uid = '{data_source_cfg["uid"]}
                    ''')
    else:
        exec_sql = (f'''
                    insert into db_config (uid, db_type, db_host, db_port, db_name, db_usr, db_psw)
                    values ('{data_source_cfg["uid"]}', 
                    '{data_source_cfg["db_type"]}',
                    '{data_source_cfg["db_host"]}', 
                    '{data_source_cfg["db_port"]}', 
                    '{data_source_cfg["db_name"]}', 
                    '{data_source_cfg["db_usr_cypher"]}', 
                    '{data_source_cfg["db_psw_cypher"]}')
                    ''')
    with sqlite3.connect(config_db) as my_conn:
        try:
            result = sqlite_insert_tool(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def build_data_source_cfg_with_uid(uid: str, sys_cfg:dict)->dict:

    source_cfg = get_data_source_config_by_uid(uid, sys_cfg)
    if not source_cfg:
        return  sys_cfg
    my_new_dict = copy.deepcopy(sys_cfg)
    my_new_dict['db']['type'] = source_cfg["db_type"]
    my_new_dict['db']['name'] = source_cfg["db_name"]
    my_new_dict['db']['host'] = source_cfg["db_host"]
    my_new_dict['db']['port'] = source_cfg["db_port"]
    my_new_dict['db']['user'] = source_cfg["db_usr"]
    my_new_dict['db']['password'] = source_cfg["db_psw"]
    return my_new_dict


def encrypt(dt: str, key:str) -> str:
    """
    密钥 key 需为16/24/32字节,密钥需为16/24/32字节，ECB模式不安全建议改用CBC+IV
    """
    cipher = AES.new(key.encode(), AES.MODE_ECB)
    data = pad(dt.encode(), AES.block_size)
    encrypted = cipher.encrypt(data)
    dt_rt = base64.b64encode(encrypted).decode()
    logger.info(f"return {dt_rt} for pln_txt {dt}")
    return dt_rt

def decrypt(dt: str, key: str) -> str:
    cipher = AES.new(key.encode(), AES.MODE_ECB)
    encrypted_data = base64.b64decode(dt)
    decrypted = cipher.decrypt(encrypted_data)
    dt_rt = unpad(decrypted, AES.block_size).decode()
    logger.info(f"return {dt_rt} for cypher_txt {dt}")
    return dt_rt

def get_const(key:str)->str | None:
    value = None
    with sqlite3.connect(config_db) as my_conn:
        try:
            sql = f"select value from const where key='{key}' limit 1"
            check_info = sqlite_query_tool(my_conn, sql)
            value_dt = json.loads(check_info)['data']
            value = value_dt[0][0]
            logger.info(f"get_const {value} with uid {value}")
        except Exception as e:
            logger.info(f"no_value_info_found_for_key, {key}")
    return value

def get_consts()-> dict:
    const = {}
    with sqlite3.connect(config_db) as my_conn:
        sql = f"select key, value from const limit 100"
        try:
            check_info = sqlite_query_tool(my_conn, sql)
            value_dt = json.loads(check_info)['data']
            for key, value in value_dt:
                const[key] = value
        except Exception as e:
            logger.exception(f"err_occurred_for_db {config_db}, sql {sql}")
    return const

def get_user_sample_data(sql: str)-> dict:
    """
    get sample data for user consumption data
    """
    const = {}
    with sqlite3.connect(user_sample_data_db) as my_conn:
        try:
            check_info = sqlite_query_tool(my_conn, sql)
            value_dt = json.loads(check_info)['data']
            for key, value in value_dt:
                const[key] = value
        except Exception as e:
            logger.exception(f"err_occurred_for_db {config_db}, sql {sql}")
    return const


def get_user_sample_data_rd_cfg_dict(cfg_dict: dict) -> dict:
    user_sample_data_rd_dict = {}
    user_sample_data_rd_dict["db"]["type"] = "sqlite"
    user_sample_data_rd_dict["db"]["name"] = user_sample_data_db
    user_sample_data_rd_dict["ai"] = cfg_dict["ai"]
    user_sample_data_rd_dict["ai"]["prompts"] = None
    user_sample_data_rd_dict["ai"]["prompts"]["add_desc_to_dt"] = False
    return user_sample_data_rd_dict


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    # key0 = '1234567890123456'
    # dt0 = 'test'
    # dt1 =encrypt(dt0, key0)
    # logger.info(dt1)
    # dt2 = decrypt(dt1, key0)
    # logger.info(dt2)
    a = get_consts()
    logger.info(f"a {a}")