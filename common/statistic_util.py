#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
import os
import sqlite3
from datetime import datetime

from common import cfg_util
from common.cfg_util import query_sqlite, insert_del_sqlite, output_data, sqlite_output
from common.my_enums import DataType

STS_DB_FILE = "cfg.db"
STS_DB_URI = f"sqlite:///{STS_DB_FILE}"

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

def get_statistics_list()-> list[dict]:
    """
    获取用户的统计数据清单
    """
    sql = (f"select uid, nickname, date, access_count, input_token, output_token"
           f" from statistics limit 100")
    logger.info(f"get_statistics_list_sql, {sql}")
    my_dt = sqlite_output(STS_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_statistics_list_dt {my_dt}")
    return my_dt

def get_statistics_by_uid(uid: int)-> dict | None:
    """
    获取用户的统计数据
    """
    sql = (f"select uid, nickname, date, access_count,"
        f"input_token, output_token from statistics where uid={uid} limit 1")
    logger.info(f"get_statistics_by_uid_sql, {sql}")
    my_dt = sqlite_output(STS_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_statistics_by_uid_dt {my_dt}")
    return my_dt

def get_access_count_by_uid(uid: int)-> int:
    """
    统计一个用户的累计访问次数
    """
    today = datetime.today().strftime('%Y-%m-%d')
    with sqlite3.connect(STS_DB_FILE) as my_conn:
        try:
            sql = f"select access_count from statistics where uid={uid} and date='{today}' limit 1"
            check_info = query_sqlite(my_conn, sql)
            user_dt = check_info['data']
            if user_dt:
                logger.debug(f"get_access_count_by_uid, {user_dt[0][0]}")
                return user_dt[0][0]
        except Exception as e:
            logger.error(f"get_access_count_by_uid_err, {uid}")
    logger.error(f"no_access_count_found_for_uid, {uid}")
    return -1

def add_access_count_by_uid(uid: int, access_count: int)-> bool:
    """
    更新用户的访问次数
    :param uid: user id
    :param access_count: user access count: user_hack_info for txt to SQL
    """
    save_result = False
    if not access_count or not uid:
        logger.error("user_access_count_or_uid_is_null")
        return save_result
    current_access_count = get_access_count_by_uid(uid)
    today = datetime.today().strftime('%Y-%m-%d')
    if current_access_count >= 0:
        upt_count = access_count + current_access_count
        exec_sql = f"update statistics set access_count ={upt_count} where uid = {uid} and date='{today}'"
    else:
        nickname_info = cfg_util.get_user_info_by_uid(uid)
        if nickname_info:
            exec_sql = f"""insert into statistics (uid, nickname, date, access_count) 
            values ({uid}, '{nickname_info['name']}', '{today}', '{access_count}')"""
        else:
            raise Exception(f"failed_get_nickname_info_for_uid, {uid}, {nickname_info}")
    with sqlite3.connect(STS_DB_FILE) as my_conn:
        try:
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.debug(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
                logger.debug("add_access_count_success")
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result

def get_input_token_by_uid(uid: int)-> int | None:
    today = datetime.today().strftime('%Y-%m-%d')
    with sqlite3.connect(STS_DB_FILE) as my_conn:
        try:
            sql = f"select input_token from statistics where uid={uid} and date='{today}' limit 1"
            check_info = query_sqlite(my_conn, sql)
            user_dt = check_info['data']
            if user_dt:
                logger.debug(f"get_input_token_by_uid, {user_dt[0][0]}")
                return user_dt[0][0]
        except Exception as e:
            logger.error(f"get_input_token_by_uid_err, {uid}")
    logger.error(f"no_input_token_found_for_uid, {uid}")
    return -1

def add_input_token_by_uid(uid: int, input_token: int)-> bool:
    """
    :param uid: user id
    :param input_token: user input token
    """

    save_result = False
    if not input_token or not uid:
        logger.error("user_input_token_or_uid_is_null")
        return save_result
    current_input_token = get_input_token_by_uid(uid)
    today = datetime.today().strftime('%Y-%m-%d')
    if current_input_token >= 0:
        upt_count = input_token + current_input_token
        exec_sql = f"update statistics set input_token ={upt_count} where uid = {uid} and date='{today}'"
    else:
        nickname_info = cfg_util.get_user_info_by_uid(uid)
        if nickname_info:
            exec_sql = f"""insert into statistics (uid, nickname, date, input_token) 
            values ({uid}, '{nickname_info['name']}', '{today}', '{input_token}')"""
        else:
            raise Exception(f"failed_get_nickname_info_for_uid, {uid}, {nickname_info}")
    with sqlite3.connect(STS_DB_FILE) as my_conn:
        try:
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.debug(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
                logger.info("add_input_token_success")
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result


def get_output_token_by_uid(uid: int)-> int | None:
    today = datetime.today().strftime('%Y-%m-%d')
    with sqlite3.connect(STS_DB_FILE) as my_conn:
        try:
            sql = f"select output_token from statistics where uid={uid} and date='{today}' limit 1"
            check_info = query_sqlite(my_conn, sql)
            user_dt = check_info['data']
            if user_dt:
                logger.debug(f"get_output_token_by_uid, {user_dt[0][0]}")
                return user_dt[0][0]
        except Exception as e:
            logger.error(f"get_output_token_by_uid_err, {uid}")
    logger.error(f"no_output_token_found_for_uid, {uid}")
    return -1

def add_output_token_by_uid(uid: int, output_token: int)-> bool:
    """
    :param uid: user id
    :param output_token: user output token
    """
    save_result = False
    if not output_token or not uid:
        logger.error("user_output_token_or_uid_is_null")
        return save_result
    current_output_token = get_output_token_by_uid(uid)
    today = datetime.today().strftime('%Y-%m-%d')
    if current_output_token >= 0:
        upt_count = output_token + current_output_token
        exec_sql = f"update statistics set output_token ={upt_count} where uid = {uid} and date='{today}'"
    else:
        nickname_info = cfg_util.get_user_info_by_uid(uid)
        if nickname_info:
            exec_sql = f"""insert into statistics (uid, nickname, date, output_token) 
                values ({uid}, '{nickname_info['name']}', '{today}', '{output_token}')"""
        else:
            raise Exception(f"failed_get_nickname_info_for_uid, {uid}, {nickname_info}")
    with sqlite3.connect(STS_DB_FILE) as my_conn:
        try:
            result = insert_del_sqlite(my_conn, exec_sql)
            logger.debug(f"exec_sql_success {exec_sql}")
            if result.get('result'):
                save_result = True
                logger.debug("add_output_token_success")
        except Exception as e:
            logger.exception(f"err_in_exec_sql, {exec_sql}")
    return save_result