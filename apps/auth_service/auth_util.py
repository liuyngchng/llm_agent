#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
import os
import sqlite3
import time

CFG_DB_FILE = "user.db"
CFG_DB_URI=f"sqlite:///{CFG_DB_FILE}"

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


def encrypt(dt: str, key:str) -> str:
    """
    密钥 key 需为16/24/32字节,密钥需为16/24/32字节，ECB模式不安全建议改用CBC+IV
    """
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    import base64
    cipher = AES.new(key.encode(), AES.MODE_ECB)
    data = pad(dt.encode(), AES.block_size)
    encrypted = cipher.encrypt(data)
    dt_rt = base64.b64encode(encrypted).decode()
    # logger.info(f"return {dt_rt} for pln_txt {dt}")
    return dt_rt

def decrypt(dt: str, key: str) -> str:
    from Crypto.Cipher import AES
    import base64
    cipher = AES.new(key.encode(), AES.MODE_ECB)
    encrypted_data = base64.b64decode(dt)
    decrypted = cipher.decrypt(encrypted_data)
    from Crypto.Util.Padding import unpad
    pln_txt = unpad(decrypted, AES.block_size).decode()
    # logger.info(f"get_pln_txt_for_cypher_txt, {pln_txt}, {dt}")
    return pln_txt


def auth_user(user:str, t: str, cfg: dict) -> dict:
    auth_result ={"pass": False, "uid": "", "msg":""}
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {os.path.abspath(CFG_DB_FILE)} 不存在")
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

def save_usr(user_name: str, token: str) -> bool:
    """
    :param user_name: user's name need to be saved.
    :param token: user's token relation with password need to be saved.
    """
    import re
    save_result = False
    exec_sql = f"INSERT INTO user (name, t) values ('{user_name}','{token}' )"
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {os.path.abspath(CFG_DB_FILE)} 不存在")
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

def get_user_info_by_uid(uid: int)-> dict:
    import json
    user_info = {}
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {os.path.abspath(CFG_DB_FILE)} 不存在")
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

def get_uid_by_user(usr_name:str) ->int:
    check_sql = f"select id from user where name='{usr_name}' limit 1"
    uid = -1
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {os.path.abspath(CFG_DB_FILE)} 不存在")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        check_info = query_sqlite(my_conn, check_sql)
        logger.debug(f"check_info {check_info}")
        if check_info:
            check_data = check_info.get('data', [])
        else:
            check_data = []
        try:
            if check_data and check_data[0]:
                uid = int(check_data[0][0])
        except (IndexError, TypeError) as e:
            logger.info(f"user info for {usr_name} can't be found")
    return uid

def get_user_name_by_uid(uid: int)-> str | None:
    user = None
    if not os.path.exists(CFG_DB_FILE):
        raise FileNotFoundError(f"数据库文件 {os.path.abspath(CFG_DB_FILE)} 不存在")
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
        raise FileNotFoundError(f"数据库文件 {os.path.abspath(CFG_DB_FILE)} 不存在")
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