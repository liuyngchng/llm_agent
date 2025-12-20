#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
配置管理
"""
import json
import copy
import os
import re
import sqlite3
import logging.config
import time
from decimal import Decimal
from typing import Any
import base64
import functools
import platform

from common.cm_utils import get_time_str
from common.const import CFG_DB_FILE, USER_SAMPLE_DATA_DB, CFG_DB_URI
from common.my_enums import DataType

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

def auth_user(user:str, t: str, cfg: dict) -> dict:
    auth_result ={"pass": False, "uid": "", "msg":""}
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        sql = f"select id, role from user where name='{user}' limit 1"
        check_info = query_sqlite(my_conn, sql)
        user_dt = check_info.get('data', [])
        if not user_dt:
            auth_result["msg"] = f"当前用户名 {user} 不存在，请注册后再尝试登录"
            return auth_result
        sql = f"select id, role from user where name='{user}' and t = '{t}' limit 1"
        check_info = query_sqlite(my_conn, sql)
        user_dt = check_info.get('data', [])
    if user_dt:
        auth_result["pass"] = True
        auth_result["uid"] = user_dt[0][0]
        auth_result["role"] = user_dt[0][1]
        auth_result["t"] = encrypt(str(time.time() * 1000), cfg['sys']['cypher_key'])
    else:
        auth_result["msg"] = f"当前用户 {user} 的密码输入错误"
    return auth_result

def get_user_info_by_uid(uid: int)-> dict:
    user_info = {}
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            sql = f"select id, name, role, area from user where id={uid} limit 1"
            check_info = query_sqlite(my_conn, sql)
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

def get_uid_by_user(usr_name:str) ->str:
    check_sql = f"select id from user where name='{usr_name}' limit 1"
    uid = ''
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        check_info = query_sqlite(my_conn, check_sql)
        logger.debug(f"check_info {check_info}")
        if check_info:
            check_data = check_info.get('data', [])
        else:
            check_data = []
        try:
            if check_data and check_data[0]:
                uid = check_data[0][0]
        except (IndexError, TypeError) as e:
            logger.info(f"user info for {usr_name} can't be found")
    return uid

def get_user_name_by_uid(uid: int)-> str | None:
    user = None
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            sql = f"select name from user where id={uid} limit 1"
            check_info = query_sqlite(my_conn, sql)
            user_dt = check_info['data']
            user = user_dt[0][0]
            logger.info(f"get_user_with_uid, {user}, {uid}")
        except Exception as e:
            logger.info(f"no_user_info_found_for_uid, {uid}")
    return user

def get_user_role_by_uid(uid:int)-> str | None:
    role = None
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            sql = f"select role from user where id={uid} limit 1"
            check_info = query_sqlite(my_conn, sql)
            user_dt = check_info['data']
            role = user_dt[0][0]
            logger.info(f"role {role}, uid {uid}")
        except Exception as e:
            logger.info(f"no_user_info_found_for_uid, {uid}")
    return role

def get_user_hack_info(uid: int, cfg: dict)-> str | None:
    user_hack_info = None
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            sql = f"select hack_info from user where id={uid} limit 1"
            check_info = query_sqlite(my_conn, sql)
            user_dt = check_info['data']
            if user_dt and user_dt[0] and user_dt[0][0]:
                user_hack_info = decrypt(user_dt[0][0], cfg['sys']['cypher_key'])
            else:
                user_hack_info = ""
            logger.debug(f"uid {uid}, user_hack_info {user_hack_info[:20]}...")
        except Exception as e:
            logger.exception(f"no_user_hack_info_found_for_uid, {uid}")
    return user_hack_info

def save_user_hack_info(uid: int, user_hack_info: str, cfg: dict) -> bool:
    """
    :param uid: user id
    :param user_hack_info: user_hack_info for txt to SQL
    :param cfg: system config
    """
    save_result = False
    if not user_hack_info or not uid:
        logger.error("user_hack_info_or_uid_is_null")
        return save_result
    logger.info("start_encrypt_user_hack_info")
    user_hack_info1 = encrypt(user_hack_info, cfg['sys']['cypher_key'])
    exec_sql = f"update user set hack_info ='{user_hack_info1}' where id = {uid}"
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            exec_sql = re.sub(r'\s+', ' ', exec_sql).strip()
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
                logger.info("save_user_hack_info_success")
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def get_ds_cfg_by_uid(uid:int, cfg: dict) -> dict:
    config = {}
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        check_sql = (
            f"select uid, db_type, db_name, db_host, db_port, "
            f"db_usr, db_psw, tables, add_chart, is_strict, llm_ctx from db_config where uid={uid} limit 1")
        db_config_info = query_sqlite(my_conn, check_sql)
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
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            exec_sql = exec_sql.replace('\n', ' ')
            exec_sql = re.sub(r'\s+', ' ', exec_sql).strip()
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def save_usr(user_name: str, token: str) -> bool:
    """
    :param user_name: user's name need to be saved.
    :param token: user's token relation with password need to be saved.
    """
    save_result = False
    exec_sql = f"INSERT INTO user (name, t) values ('{user_name}','{token}' )"
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            exec_sql = exec_sql.replace('\n', ' ')
            exec_sql = re.sub(r'\s+', ' ', exec_sql).strip()
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def set_db_cache(key: str, value: str, timestamp: str, cypher_key: str) -> bool:
    """
    :param key: cache key
    :param value: cache value
    :param timestamp: cache timestamp
    :param cypher_key: key used to encrypt data
    """
    save_result = False
    if not cypher_key:
        raise Exception("cypher_key_null_err")
    encrypt_value = encrypt(value, cypher_key)
    exec_sql = f"INSERT INTO cache_info (key, value, timestamp) values ('{key}','{encrypt_value}', '{timestamp}')"
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            exec_sql = exec_sql.replace('\n', ' ')
            exec_sql = re.sub(r'\s+', ' ', exec_sql).strip()
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def del_db_cache(key: str) -> bool:
    """
    :param key: cache key
    """
    del_result = False
    exec_sql = f"delete from cache_info where key='{key}'"
    if platform.system() == "Linux":
        exec_sql += " limit 1"
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            exec_sql = exec_sql.replace('\n', ' ')
            exec_sql = re.sub(r'\s+', ' ', exec_sql).strip()
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.info(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                del_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return del_result

def get_db_cache(key:str, cypher_key: str)->tuple | None:
    """
    :param key: cache key
    :param cypher_key: key used to encrypt data
    """
    if not cypher_key:
        raise Exception("cypher_key_null_err")
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            sql = f"select value ,timestamp from cache_info where key='{key}' limit 1"
            cache_info = query_sqlite(my_conn, sql)
            value_dt = cache_info['data']
            value = value_dt[0][0]
            timestamp = value_dt[0][1]
            decrypt_value = decrypt(value, cypher_key)
            # logger.info(f"get_cache_with_key {key}, {decrypt_value}")
            return decrypt_value, timestamp
        except Exception as e:
            logger.info(f"no_cache_info_found_for_key, {key}")
    return None

def delete_data_source_config(uid: int, cfg: dict) -> bool:
    delete_result = False
    if not uid:
        logger.error("uid_null_err")
        return delete_result
    current_config = get_ds_cfg_by_uid(uid, cfg)
    if current_config:
        delete_sql = f"delete from db_config where uid = {uid}"
    else:
        logger.error(f"no_db_source_cfg_found_for_uid_{uid}")
        return False
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        try:
            result = insert_del_sqlite(my_conn, delete_sql)
            logger.info(f"exec_sql_success {delete_sql}")
            if result.get('result'):
                delete_result = True
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {delete_sql}")
    return delete_result

def build_data_source_cfg_with_uid(uid: int, sys_cfg:dict)->dict:
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
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    cipher = AES.new(key.encode(), AES.MODE_ECB)
    data = pad(dt.encode(), AES.block_size)
    encrypted = cipher.encrypt(data)
    dt_rt = base64.b64encode(encrypted).decode()
    # logger.info(f"return {dt_rt} for pln_txt {dt}")
    return dt_rt

def decrypt(dt: str, key: str) -> str:
    from Crypto.Cipher import AES
    cipher = AES.new(key.encode(), AES.MODE_ECB)
    encrypted_data = base64.b64decode(dt)
    decrypted = cipher.decrypt(encrypted_data)
    from Crypto.Util.Padding import unpad
    pln_txt = unpad(decrypted, AES.block_size).decode()
    # logger.info(f"get_pln_txt_for_cypher_txt, {pln_txt}, {dt}")
    return pln_txt



def get_consts(app: str)-> dict:
    const = {}
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        sql = f"select key, value from const where app='{app}' limit 100"
        try:
            check_info = query_sqlite(my_conn, sql)
            value_dt = check_info['data']
            for key, value in value_dt:
                const[key] = value
        except Exception as e:
            logger.exception(f"err_occurred_for_db {CFG_DB_FILE}, sql {sql}")
    return const

def get_user_list():
    user_list = []
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        sql = f"select id, name from user limit 100"
        try:
            check_info = query_sqlite(my_conn, sql)
            value_dt = check_info['data']
            for id, name in value_dt:
                user_list.append({"id": id, "name": name})
        except Exception as e:
            logger.exception(f"err_occurred_for_db {CFG_DB_FILE}, sql {sql}")
    return user_list

def get_hack_info(uid: int)-> dict:
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        sql = f"select hack_q_dict from hack_list where uid = {uid} limit 1"
        try:
            check_info = query_sqlite(my_conn, sql)
            hack_q_list = check_info['data']
            if hack_q_list:
                return json.loads(hack_q_list[0][0])
        except Exception as e:
            logger.exception(f"err_occur_in_get_hack_q_dict_for_db {CFG_DB_FILE}, sql {sql}")
    return {}

def get_usr_prompt_template(template_name: str,  sys_cfg: dict, uid=0)-> str:
    """
    获取用户提示词模板配置， 为了兼容以前的配置文件配置，添加了从配置文件读取的部分；
    首先读取指定用户的配置，如果没有则读取通用的配置
    :param template_name 模板名称
    :param sys_cfg 系统配置 yaml 文件
    :param uid 用户 ID, 当 UID为 0 时，为公共配置
    """
    if not template_name or template_name == '':
        logger.warning(f"template_name_is_null_direct_return, {template_name}")
        return ""
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        sql = f"select value from prompt_template where name = '{template_name}' and  uid = {uid} limit 1"
        try:
            prompt_info = query_sqlite(my_conn, sql)
            prompt = prompt_info.get('data', [])
            if prompt and prompt[0]:
                return prompt[0][0]
            if uid != 0:
                sql = f"select value from prompt_template where name = '{template_name}' and  uid = 0 limit 1"
                prompt_info = query_sqlite(my_conn, sql)
                prompt = prompt_info.get('data', [])
                if prompt and prompt[0]:
                    return prompt[0][0]
            if not sys_cfg or not sys_cfg.get('prompts'):
                raise RuntimeError(f"no_sys_cfg_prompts_err")
            prompt = sys_cfg['prompts'].get(template_name, None)
            if prompt:
                return prompt
        except Exception as e:
            logger.exception(f"err_occur_in_get_usr_prompt_template_for_db {CFG_DB_FILE}, sql {sql}")
    raise RuntimeError(f"no_prompt_template_config_err_for_key {template_name}")

def save_usr_prompt_template(uid: int, template_name: str, template_value: str):
    """
    :param uid: user id
    :param template_name: 提示词模板名称
    :param template_value: 提示词模板值
    """
    save_result = False
    if not uid or not template_name or not template_value:
        logger.error("uid_or_template_name_or_template_value_null_err")
        return save_result
    if uid == 0:
        logger.error("illegal_uid_to_set_template_err")
        return save_result
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        sql = f"select value from prompt_template where name = '{template_name}' and  uid = {uid} limit 1"
        try:
            prompt_info = query_sqlite(my_conn, sql)
            if not prompt_info:
                logger.error(f"table_not_exist_for_sql, {sql}")
                return save_result
            prompt = prompt_info['data']
            if prompt:
                logger.info(f"user_prompt_template_for_key_{template_name}_exist_to_update")
                exec_sql = f"""update prompt_template set value = '{template_value}' where uid = {uid} and name = '{template_name}'"""
                if platform.system() == "Linux":
                    exec_sql += " limit 1"
            else:
                exec_sql = f"""insert into prompt_template (uid, name, value) values ({uid}, '{template_name}', '{template_value}')"""
            result = insert_del_sqlite(my_conn, exec_sql)

            if result.get('result'):
                logger.info(f"exec_sql_success {exec_sql}")
                save_result = True
            else:
                logger.info(f"exec_sql_fail {exec_sql}")
                save_result = False
        except Exception as e:
            logger.exception(f"err_occur_in_save_usr_prompt_template_for_db {CFG_DB_FILE}, sql {sql}")
        return save_result

def del_usr_prompt_template(uid: int):
    """
    :param uid: user id
    """
    save_result = False
    if not uid or uid == 0:
        logger.error("illegal_uid_to_del_usr_template_err")
        return save_result
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        exec_sql = f"delete from prompt_template where uid = {uid} and name in ('refine_q_msg', 'sql_gen_msg')"
        try:
            result = insert_del_sqlite(my_conn, exec_sql)
            if result.get('result'):
                logger.info(f"exec_sql_success {exec_sql}")
                save_result = True
            else:
                logger.info(f"exec_sql_fail {exec_sql}")
                save_result = False
        except Exception as e:
            logger.exception(f"err_occur_in_del_usr_prompt_template_for_db {CFG_DB_FILE}, sql {exec_sql}")
        return save_result

@functools.lru_cache(maxsize=128)
def get_hack_dict(uid: int) -> dict:
    """
    返回一个用户问题->可执行的问题对应关系的字典
    """
    file_full_path = f'./hack/{uid}.txt'
    if not os.path.exists(file_full_path):
        logger.error(f"file_not_found_return_empty_dict, {file_full_path}")
        return {}
    try:
        with open(file_full_path, 'r', encoding='utf-8') as f:
            hack_dict = dict(re.split(r'\t| +', line.rstrip('\n'), 1) for line in f)
            logger.info(f"return_hack_dict_for_uid_{uid}, {json.dumps(hack_dict, ensure_ascii=False)}, hack_file {file_full_path}")
            return hack_dict
    except FileNotFoundError:
        logger.error(f"file_not_found, file_full_path={file_full_path}")
        return {}

@functools.lru_cache(maxsize=128)
def get_hack_q_file_content(uid: int) -> str:
    """
    返回对应文件的文本
    """
    file_full_path = f'./hack/{uid}.txt'
    if not os.path.exists(file_full_path):
        logger.error(f"file_not_found_return_empty_str, {file_full_path}")
        return ""
    try:
        with open(file_full_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            logger.info(f"return_hack_q_file_content_for_uid_{uid}, {file_content}, hack_file {file_full_path}")
            return file_content
    except FileNotFoundError:
        logger.error(f"file_not_found, {file_full_path}")
        return ""


def get_user_sample_data(sql: str)-> dict:
    """
    get sample data for user consumption data
    """
    const = {}
    with sqlite3.connect(USER_SAMPLE_DATA_DB) as my_conn:
        try:
            check_info = query_sqlite(my_conn, sql)
            value_dt = check_info['data']
            for key, value in value_dt:
                const[key] = value
        except Exception as e:
            logger.exception(f"err_occurred_for_db {CFG_DB_FILE}, sql {sql}")
    return const



def get_user_sample_data_rd_cfg_dict(cfg_dict: dict) -> dict:
    user_sample_data_rd_dict = {}
    user_sample_data_rd_dict["db"]["type"] = "sqlite"
    user_sample_data_rd_dict["db"]["name"] = USER_SAMPLE_DATA_DB
    user_sample_data_rd_dict["api"] = cfg_dict["api"]
    return user_sample_data_rd_dict

def sqlite_output(db_uri: str, sql: str, data_format: str) -> str | Any:
    """
    cfg["db_uri"] = "sqlite:///test1.db"
    """

    db_file = db_uri.split('/')[-1]
    with sqlite3.connect(db_file) as my_conn:
        # logger.debug(f"connect_to_db_file {db_file}")
        my_dt = output_data(my_conn, sql, data_format)
    if DataType.JSON.value == data_format:
        try:
            my_dt = json.loads(my_dt)
        except Exception as ex:
            logger.error(f"json_parse_error_for_dt: {my_dt}, {ex}")
    # logger.debug(f"sqlite_output, data_format {data_format}, my_dt, {my_dt}")
    return my_dt


def output_data(db_con, sql:str, data_format:str) -> str:
    data = query_sqlite(db_con, sql)
    if data.get('error'):
        raise RuntimeError(f"error_occurred_in_exec_sqlite_sql, err_info={data}, sql={sql}")
    # logger.debug(f"data {data} for {db_con}")
    import pandas as pd
    df = pd.DataFrame(data.get('data'), columns=data['columns'])
    dt_fmt = data_format.lower()

    if DataType.HTML.value in dt_fmt:
        dt = get_pretty_html(df)
    elif DataType.MARKDOWN.value in dt_fmt:
        dt = get_md_dt_from_data_frame(df)

    elif DataType.JSON.value in dt_fmt:
        dt = df.to_json(force_ascii=False, orient='records')
    else:
        info = f"error data format {data_format}"
        logger.error(info)
        raise info
    dt1 = dt.replace('\n', ' ')
    # logger.debug(f"output_data_dt:{dt1}")
    return dt

def get_md_dt_from_data_frame(df):
    if df.empty:
        return ''
    return df.map(lambda x: f"{x:.0f}" if isinstance(x, (Decimal, float)) else x,
        na_action='ignore').to_markdown(index=False)

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

def query_sqlite(db_con, query: str) -> dict:
    try:
        cursor = db_con.cursor()
        query = query.replace('\n', ' ')
        # logger.debug(f"execute_query, {query}")
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        return {"columns": columns, "data": data}
    except Exception as e:
        logger.exception(f"sqlite_query_err, pls_check_your_sqlite_file_{db_con}_and_sql_is_correct, {query}")
        # raise Exception
        exit(-1)
        # return {"error": str(e)}

def insert_del_sqlite(db_con, sql: str) -> dict:
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

def save_file_info(uid: int, fid: str, full_path: str, file_suffix:int = 0) -> dict:
    """
    保存文件信息
    :param uid: user id
    :param fid: 文件id
    :param full_path: 文件存储路径
    :param file_suffix: 文件类型 , 0: docx; 1: xlsx
    :return:
    """
    logger.debug(f"save_file_info, {uid}, {fid}, {full_path}")
    timestamp = get_time_str()
    sql = (f"insert into file_info(uid, fid, full_path, file_suffix, timestamp) values "
           f"({uid}, '{fid}', '{full_path}', '{file_suffix}', '{timestamp}')")
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {CFG_DB_FILE} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        logger.debug(f"save_file_info_sql, {sql}")
        my_dt = insert_del_sqlite(my_conn, sql)
        return my_dt

def get_file_info(uid: int, fid: str) -> dict:
    """
    根据文件ID查询文件信息
    :param uid 用户 ID
    :param fid: 文件 ID
    :return: a dict
    """
    if not fid or not uid:
        raise RuntimeError(f"param_null_err, {uid}, {fid}")
    sql = f"select * from file_info where uid = {uid} and fid = '{fid}' limit 1"
    logger.debug(f"get_file_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.debug(f"get_file_info_dt {my_dt}")
    return my_dt


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    test_my_dt = get_usr_prompt_template("hi",  {"test":{"test"}}, 123)
    logger.info(test_my_dt)


