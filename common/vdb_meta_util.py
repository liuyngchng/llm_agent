#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
向量库元数据管理
"""
import platform
import sqlite3
import time

from common import cfg_util
from common.cfg_util import sqlite_output, insert_del_sqlite
from common.const import CFG_DB_URI, CFG_DB_FILE
import logging.config

from common.my_enums import DataType

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

class VdbMeta:
    """
    Vector DB Meta Util Class
    """

    @staticmethod
    def get_vdb_info_by_id(vdb_id: int):
        if not vdb_id:
            raise RuntimeError("uid_null_err")
        sql = f"select * from vdb_info where id = {vdb_id} limit 1"
        logger.info(f"get_vdb_info_by_id_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        return my_dt

    @staticmethod
    def get_vdb_info_by_uid(uid: int, kdb_name='', include_others_public=True):
        if not uid:
            raise RuntimeError("uid_null_err")
        sql = f"select * from vdb_info where uid = {uid}"
        if kdb_name and kdb_name.strip() != '':
            sql += f" and name = '{kdb_name}'"
        logger.debug(f"get_my_vdb_info_by_uid_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        if not include_others_public:
            for item in my_dt:
                if item.get('is_default', -1) == 1:  # 自己的知识库
                    item['name'] = '(默认)' + item.get('name', '')
            logger.debug(f"get_my_vdb_info_by_uid_dt {my_dt}")
            return my_dt
        sql = f"select * from vdb_info where uid != {uid} and is_public = '1'"
        logger.info(f"get_vdb_info_by_not_uid_and_is_public_sql, {sql}")
        public_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        merged_dt = my_dt + public_dt
        for item in merged_dt:
            if uid == item.get('uid', None):  # 自己的知识库
                item['name'] = '我的_' + item.get('name', '')
            else:  # 其他用户的知识库
                uid = item.get("uid", None)
                user_name = uid
                try:
                    user_name = cfg_util.get_user_name_by_uid(uid)
                    if not user_name:
                        user_name = uid
                except Exception as e:
                    logger.error(f"get_user_name_by_uid_err, {str(e)}")
                item['name'] = f'用户[{user_name}]的_' + item.get('name', None)
        logger.debug(f"get_vdb_info_by_uid_dt {merged_dt}")
        return merged_dt

    @staticmethod
    def create_vdb_info(kdb_name: str, uid: int, is_public=False):
        timestamp = time.time()
        # 生成类似格式（UTC时间）
        iso_str = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp))
        sql = f"insert into vdb_info (name, uid, is_public, create_time) values ('{kdb_name}', {uid}, '{is_public}','{iso_str}')"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"create_vdb_info_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"create_vdb_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def active_vdb_file_info(file_id: int, file_path: str):
        if not file_id or not file_path:
            raise RuntimeError(f"param_null_err, {file_id}, {file_path}")
        sql = f"update vdb_file_info set file_path = '{file_path}' where id = {file_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"update_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_by_uid_and_kb_id(uid: int, kb_id: int):
        if not uid or not kb_id:
            logger.error(f"uid_or_kb_id_null_err, uid = {uid}, kb_id = {kb_id}")
            raise RuntimeError("uid_or_kb_id_null_err")
        sql = f"delete from vdb_info where uid = {uid} and id = {kb_id}"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_vdb_by_uid_and_kb_id_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"delete_vdb_by_uid_and_kb_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_list(uid: int, vdb_id: int):
        if not uid or not vdb_id:
            raise RuntimeError(f"get_vdb_file_list_param_null_err, {uid}, {vdb_id}")
        sql = f"select * from vdb_file_info where uid = {uid} and vdb_id = {vdb_id}"
        logger.debug(f"get_vdb_file_list_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_vdb_file_list_dt, {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_processing_list():
        sql = f"select * from vdb_file_info where percent != 100 limit 100"
        # logger.debug(f"get_vdb_processing_file_list_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        # logger.debug(f"get_vdb_processing_file_list_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_user_default_vdb(uid: int):
        if not uid:
            raise RuntimeError(f"get_default_vdb_param_null_err, {uid}")
        sql = f"select id, name from vdb_info where uid = {uid} and is_default = 1 limit 1"
        logger.debug(f"get_default_vdb_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_default_vdb_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_by_id(vbd_id: int):
        if not vbd_id:
            raise RuntimeError(f"get_vdb_by_id_param_null_err, {vbd_id}")
        sql = f"select id, name from vdb_info where id = {vbd_id} limit 1"
        logger.debug(f"get_vdb_by_id_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_vdb_by_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def set_user_default_vdb(uid: int, vdb_id: int):
        if not uid or not vdb_id:
            raise RuntimeError(f"set_default_vdb_param_null_err, {uid}, {vdb_id}")
        sql = f"update vdb_info set is_default = 1 where uid = {uid} and id = {vdb_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        logger.debug(f"set_default_vdb_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"set_default_vdb_dt {my_dt}")
        sql = f"update vdb_info set is_default = 0 where uid = {uid} and id != {vdb_id}"
        logger.debug(f"set_default_vdb_exclude_sql, {sql}")
        my_dt1 = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"set_default_vdb_exclude_dt {my_dt1}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_file_name(file_name: str, uid: int, vdb_id: int) -> list:
        if not uid or not file_name or not vdb_id:
            raise RuntimeError(f"param_null_err {file_name}, {uid}, {vdb_id}")
        sql = f"select * from vdb_file_info where name = '{file_name}' and uid = {uid} and vdb_id = {vdb_id} limit 1"
        logger.debug(f"get_file_info_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_md5(file_md5: str, uid: int, vdb_id: int) -> list:
        if not uid or not file_md5 or not vdb_id:
            raise RuntimeError(f"param_null_err {file_md5}, {uid}, {vdb_id}")
        sql = f"select * from vdb_file_info where file_md5 = '{file_md5}' and uid = {uid} and vdb_id = {vdb_id} limit 1"
        logger.debug(f"get_file_info_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_task_id(task_id: int) -> dict:
        if not task_id:
            raise RuntimeError(f"param_null_err {task_id}")
        sql = f"select * from vdb_file_info where task_id = {task_id} limit 1"
        logger.debug(f"get_file_info_by_task_id, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_file_info_by_task_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_id(file_id: int):
        if not file_id:
            raise RuntimeError(f"file_id_param_null_err {file_id}")
        sql = f"select * from vdb_file_info where id = {file_id} limit 1"
        logger.debug(f"get_file_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"get_file_info_by_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_uid_vbd_id_file_name(file_name: str, uid: int, vdb_id: int):
        sql = f"delete from vdb_file_info where name ='{file_name}' and uid={uid} and vdb_id={vdb_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_file_name_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_file_name_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_task_id(task_id: int):
        sql = f"delete from vdb_file_info where task_id={task_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_vbd_task_id_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"delete_file_by_vbd_task_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_id(file_id: int):
        if not file_id:
            logger.error(f"file_id_null_err, {file_id}")
            return
        sql = f"delete from vdb_file_info where id={file_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"delete_file_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_uid_vbd_id_file_id(file_id: int, uid: int, vdb_id: int):
        sql = f"delete from vdb_file_info where id ={file_id} and uid={uid} and vdb_id={vdb_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_file_id_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_file_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_uid_vbd_id(uid: int, vdb_id: int):
        sql = f"delete from vdb_file_info where uid={uid} and vdb_id={vdb_id}"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def save_vdb_file_info(original_file_name: str, saved_file_name: str, uid: int, vdb_id: int, task_id: int,
                           file_md5: str):
        timestamp = time.time()
        # 生成类似格式（UTC时间）
        iso_str = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp))
        sql = (f"insert into vdb_file_info (name, uid, vdb_id, file_path, task_id, file_md5, create_time) values"
               f" ('{original_file_name}', {uid}, {vdb_id}, '{saved_file_name}', {task_id}, '{file_md5}', '{iso_str}')")
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"save_file_info_sql, {sql}")
            my_dt = insert_del_sqlite(my_conn, sql)
        logger.info(f"save_file_info_dt, {my_dt}")
        return my_dt

    @staticmethod
    def update_vdb_file_path(file_id: int, file_path: str):
        if not file_id or not file_path:
            raise RuntimeError(f"param_null_err, {file_id}, {file_path}")
        sql = f"update vdb_file_info set file_path = '{file_path}' where id = {file_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"update_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def update_vdb_file_process_info(file_id: int, process_info: str, percent=-1):
        if not file_id or not process_info:
            raise RuntimeError(f"param_null_err, {file_id}, {process_info}")
        if percent == -1:
            sql = f"update vdb_file_info set process_info = '{process_info}' where id = {file_id}"
        else:
            sql = f"update vdb_file_info set process_info = '{process_info}', percent={percent} where id = {file_id}"
        if platform.system() == "Linux":
            sql += " limit 1"
        logger.debug(f"update_file_info_sql, {sql}")
        my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.debug(f"update_file_info_dt {my_dt}")
        return my_dt


if __name__ == "__main__":
    result = VdbMeta.get_vdb_file_processing_list()
    logger.info(f"result {result}")