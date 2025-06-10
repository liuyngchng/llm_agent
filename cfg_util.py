#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import copy
import re
import sqlite3
import logging.config
import time

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

from db_util import DbUtl

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)
config_db = "cfg.db"
user_sample_data_db = "user_info.db"


def auth_user(user:str, t: str, cfg: dict) -> dict:
    auth_result ={"pass": False, "uid": ""}
    with sqlite3.connect(config_db) as my_conn:
        sql = f"select id, role from user where name='{user}' and t = '{t}' limit 1"
        check_info = DbUtl.sqlite_query_tool(my_conn, sql)
        user_dt = check_info['data']

    if user_dt:
        auth_result["pass"] = True
        auth_result["uid"] = user_dt[0][0]
        auth_result["role"] = user_dt[0][1]
        auth_result["t"] = encrypt(str(time.time() * 1000), cfg['sys']['cypher_key'])
    return auth_result

def get_user_info_by_uid(uid: str)-> dict:
    user_info = {}
    with sqlite3.connect(config_db) as my_conn:
        try:
            sql = f"select id, name, role, area from user where id='{uid}' limit 1"
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            user_dt = check_info['data']
            if user_dt:
                user_info['id']     = user_dt[0][0]
                user_info['name']   = user_dt[0][1]
                user_info['role']   = user_dt[0][2]
                user_info['area']   = user_dt[0][3]
                logger.info(f"get_user_info_by_uid, {json.dumps(user_info, ensure_ascii=False)}")
                return user_info
        except Exception as e:
            logger.error(f"get_user_info_err_for_uid, {uid}")
    logger.error(f"no_user_info_found_for_uid, {uid}")
    return user_info

def get_uid_by_user(usr:str) ->str:
    check_sql = f"select id from user where name='{usr}' limit 1"
    uid = ''
    with sqlite3.connect(config_db) as my_conn:
        check_info = DbUtl.sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_info {check_info}")
        check_data = check_info['data']
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
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            user_dt = check_info['data']
            user = user_dt[0][0]
            logger.info(f"get_user_with_uid, {user}, {uid}")
        except Exception as e:
            logger.info(f"no_user_info_found_for_uid, {uid}")
    return user

def get_user_role_by_uid(uid:str)-> str | None:
    role = None
    with sqlite3.connect(config_db) as my_conn:
        try:
            sql = f"select role from user where id='{uid}' limit 1"
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            user_dt = check_info['data']
            role = user_dt[0][0]
            logger.info(f"role {role}, uid {uid}")
        except Exception as e:
            logger.info(f"no_user_info_found_for_uid, {uid}")
    return role

def get_ds_cfg_by_uid(uid:str, cfg: dict) -> dict:
    config = {}
    with sqlite3.connect(config_db) as my_conn:
        check_sql = (
            f"select uid, db_type, db_name, db_host, db_port, "
            f"db_usr, db_psw, tables, add_chart, is_strict, llm_ctx from db_config where uid='{uid}' limit 1")
        db_config_info = DbUtl.sqlite_query_tool(my_conn, check_sql)
        logger.debug(f"check_sql, {check_sql}")
        check_info = db_config_info['data']
        if not check_info:
            logger.info(f"no_db_config_for_uid {uid}")
            return config
        try:
            check_uid = check_info[0][0]
            config = {
                "uid":          check_uid,
                "db_type":      check_info[0][1],
                "db_name":      check_info[0][2],
                "db_host":      check_info[0][3],
                "db_port":      check_info[0][4],
                "db_usr":       decrypt(check_info[0][5], cfg['sys']['cypher_key']),
                "db_psw":       decrypt(check_info[0][6], cfg['sys']['cypher_key']),
                "tables":       check_info[0][7],
                "add_chart":    check_info[0][8],
                "is_strict":    check_info[0][9],
                "llm_ctx":      check_info[0][10]
            }
        except Exception as e:
            logger.exception("exception_occurred_get_data_source_config_by_uid")
            logger.info(f"no_db_config_for_uid {uid}")
    logger.info(f"db_config_info_for_uid, {uid}, {config}")
    return config

def save_ds_cfg(ds_cfg: dict, cfg: dict) -> bool:
    """
    :param cfg: system config
    :param ds_cfg: data source config
    """
    save_result = False
    if not ds_cfg['uid']:
        logger.error("uid_in_data_source_cfg_is_null")
        return save_result
    logger.info("start_encrypt_db_source_user_and_password")
    ds_cfg['db_usr_cypher'] = encrypt(ds_cfg['db_usr'], cfg['sys']['cypher_key'])
    ds_cfg['db_psw_cypher'] = encrypt(ds_cfg['db_psw'], cfg['sys']['cypher_key'])
    if ds_cfg["llm_ctx"]:
        llm_ctx = ds_cfg["llm_ctx"].replace("'", '"')
    else:
        llm_ctx = ''
    current_config = get_ds_cfg_by_uid(ds_cfg['uid'], cfg)
    if current_config:
        exec_sql = (f'''
                    UPDATE 
                        db_config 
                    SET 
                        db_type ='{ds_cfg["db_type"]}', 
                        db_host ='{ds_cfg["db_host"]}', 
                        db_port ='{ds_cfg["db_port"]}',
                        db_name ='{ds_cfg["db_name"]}', 
                        db_usr ='{ds_cfg["db_usr_cypher"]}', 
                        db_psw ='{ds_cfg["db_psw_cypher"]}',
                        tables ='{ds_cfg["tables"]}',
                        add_chart = '{ds_cfg["add_chart"]}',
                        is_strict = '{ds_cfg["is_strict"]}',
                        llm_ctx = '{llm_ctx}'
                    WHERE 
                        uid = '{ds_cfg["uid"]}'
                    ''')
    else:
        exec_sql = (f'''
                    INSERT INTO db_config 
                        (uid, db_type, db_host, db_port, db_name, db_usr, db_psw, tables, add_chart, is_strict, llm_ctx)
                    values (
                        '{ds_cfg["uid"]}', 
                        '{ds_cfg["db_type"]}',
                        '{ds_cfg["db_host"]}', 
                        '{ds_cfg["db_port"]}', 
                        '{ds_cfg["db_name"]}', 
                        '{ds_cfg["db_usr_cypher"]}', 
                        '{ds_cfg["db_psw_cypher"]}',
                        '{ds_cfg["tables"]}',
                        '{ds_cfg["add_chart"]}',
                        '{ds_cfg["is_strict"]}',
                        '{llm_ctx}'
                    )
                    ''')
    with sqlite3.connect(config_db) as my_conn:
        try:
            exec_sql = exec_sql.replace('\n', ' ')
            exec_sql = re.sub(r'\s+', ' ', exec_sql).strip()
            result = DbUtl.sqlite_insert_delete_tool(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def delete_data_source_config(uid: str, cfg: dict) -> bool:
    delete_result = False
    if not uid:
        logger.error("uid_null_err")
        return delete_result
    current_config = get_ds_cfg_by_uid(uid, cfg)
    if current_config:
        delete_sql = f"delete from db_config where uid = '{uid}'"
    else:
        logger.error(f"no_db_source_cfg_found_for_uid_{uid}")
        return False
    with sqlite3.connect(config_db) as my_conn:
        try:
            result = DbUtl.sqlite_insert_delete_tool(my_conn, delete_sql)
            logger.info(f"exec_sql_success {delete_sql}")
            if result.get('result'):
                delete_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {delete_sql}")
    return delete_result

def build_data_source_cfg_with_uid(uid: str, sys_cfg:dict)->dict:
    source_cfg = get_ds_cfg_by_uid(uid, sys_cfg)
    if not source_cfg:
        return  sys_cfg
    my_new_dict = copy.deepcopy(sys_cfg)
    my_new_dict['db']['type'] = source_cfg["db_type"]
    my_new_dict['db']['name'] = source_cfg["db_name"]
    my_new_dict['db']['host'] = source_cfg["db_host"]
    my_new_dict['db']['port'] = source_cfg["db_port"]
    my_new_dict['db']['user'] = source_cfg["db_usr"]
    my_new_dict['db']['password'] = source_cfg["db_psw"]
    my_new_dict['db']['tables'] = source_cfg["tables"]
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
    pln_txt = unpad(decrypted, AES.block_size).decode()
    logger.info(f"get_pln_txt_for_cypher_txt, {pln_txt}, {dt}")
    return pln_txt

def get_const(key:str)->str | None:
    value = None
    with sqlite3.connect(config_db) as my_conn:
        try:
            sql = f"select value from const where key='{key}' limit 1"
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            value_dt = check_info['data']
            value = value_dt[0][0]
            logger.info(f"get_const {value} with key {key}")
        except Exception as e:
            logger.info(f"no_value_info_found_for_key, {key}")
    return value

def get_consts()-> dict:
    const = {}
    with sqlite3.connect(config_db) as my_conn:
        sql = f"select key, value from const limit 100"
        try:
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            value_dt = check_info['data']
            for key, value in value_dt:
                const[key] = value
        except Exception as e:
            logger.exception(f"err_occurred_for_db {config_db}, sql {sql}")
    return const

def get_hack_info(uid: str)-> dict:
    with sqlite3.connect(config_db) as my_conn:
        sql = f"select hack_q_dict from hack_list where uid = '{uid}' limit 1"
        try:
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            hack_q_list = check_info['data']
            if hack_q_list:
                return json.loads(hack_q_list[0][0])
        except Exception as e:
            logger.exception(f"err_occur_in_get_hack_q_dict_for_db {config_db}, sql {sql}")
    return {}

def get_hack_file(uid: str) -> dict:
    file_full_path = f'./hack/{uid}.txt'
    try:
        with open(file_full_path) as f:
            hack_dict = dict(line.rstrip('\n').split('\t', 1) for line in f)
            logger.info(f"return_hack_dict_for_uid_{uid}, {json.dumps(hack_dict, ensure_ascii=False)}, hack_file {file_full_path}")
            return hack_dict
    except FileNotFoundError:
        logger.error(f"file_not_found, file_full_path={file_full_path}")
        return {}

def get_user_sample_data(sql: str)-> dict:
    """
    get sample data for user consumption data
    """
    const = {}
    with sqlite3.connect(user_sample_data_db) as my_conn:
        try:
            check_info = DbUtl.sqlite_query_tool(my_conn, sql)
            value_dt = check_info['data']
            for key, value in value_dt:
                const[key] = value
        except Exception as e:
            logger.exception(f"err_occurred_for_db {config_db}, sql {sql}")
    return const


def get_user_sample_data_rd_cfg_dict(cfg_dict: dict) -> dict:
    user_sample_data_rd_dict = {}
    user_sample_data_rd_dict["db"]["type"] = "sqlite"
    user_sample_data_rd_dict["db"]["name"] = user_sample_data_db
    user_sample_data_rd_dict["api"] = cfg_dict["api"]
    return user_sample_data_rd_dict


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    a = {}
    if a:
        logger.info("a is OK")
    else:
        logger.info("a is not OK")
    # key0 = '1234567890123456'
    # dt0 = 'test'
    # dt1 =encrypt(dt0, key0)
    # logger.info(dt1)
    # dt2 = decrypt(dt1, key0)
    # logger.info(dt2)
    a = get_consts()
    logger.info(f"a {a}")
    uid = '332987921'
    user = get_user_info_by_uid(uid)
    logger.info(f"user {user}")