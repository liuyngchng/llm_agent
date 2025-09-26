#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import sqlite3

import cfg_util
from db_util import DbUtl, CFG_DB_URI, CFG_DB_FILE
import logging.config

from my_enums import DataType

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
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        return my_dt

    @staticmethod
    def get_vdb_info_by_uid(uid: int, kdb_name='', include_others_public=True):
        if not uid:
            raise RuntimeError("uid_null_err")
        sql = f"select * from vdb_info where uid = {uid}"
        if kdb_name and kdb_name.strip() != '':
            sql += f" and name = '{kdb_name}'"
        logger.info(f"get_my_vdb_info_by_uid_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        if not include_others_public:
            for item in my_dt:
                if item['is_default'] == 1:  # 自己的知识库
                    item['name'] += '(默认)'
            logger.info(f"get_my_vdb_info_by_uid_dt {my_dt}")
            return my_dt
        sql = f"select * from vdb_info where uid != {uid} and is_public = '1'"
        logger.info(f"get_vdb_info_by_not_uid_and_is_public_sql, {sql}")
        public_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        merged_dt = my_dt + public_dt
        for item in merged_dt:
            if str(item['uid']) == uid:  # 自己的知识库
                item['name'] = '我的_' + item['name']
            else:  # 其他用户的知识库
                uid = item["uid"]
                user_name = uid
                try:
                    user_name = cfg_util.get_user_name_by_uid(uid)
                    if not user_name:
                        user_name = uid
                except Exception as e:
                    logger.error(f"get_user_name_by_uid_err, {str(e)}")
                item['name'] = f'用户[{user_name}]的_' + item['name']
        logger.info(f"get_vdb_info_by_uid_dt {merged_dt}")
        return merged_dt

    @staticmethod
    def create_vdb_info(kdb_name: str, uid: int, is_public=False):
        sql = f"insert into vdb_info (name, uid, is_public) values ('{kdb_name}', {uid}, '{is_public}')"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"create_vdb_info_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"create_vdb_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def active_vdb_file_info(file_id: int, file_path: str):
        if not file_id or not file_path:
            raise RuntimeError(f"param_null_err, {file_id}, {file_path}")
        sql = f"update vdb_file_info set file_path = '{file_path}' where id = {file_id} limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
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
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_vdb_by_uid_and_kb_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_list(uid: int, vdb_id: int):
        if not uid or not vdb_id:
            raise RuntimeError(f"get_vdb_file_list_param_null_err, {uid}, {vdb_id}")
        sql = f"select * from vdb_file_info where uid = {uid} and vdb_id = {vdb_id}"
        logger.info(f"get_vdb_file_list_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_vdb_file_list_dt, {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_processing_list():
        sql = f"select * from vdb_file_info where percent != 100 limit 100"
        logger.info(f"get_vdb_processing_file_list_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_vdb_processing_file_list_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_user_default_vdb(uid: int):
        if not uid:
            raise RuntimeError(f"get_default_vdb_param_null_err, {uid}")
        sql = f"select id, name from vdb_info where uid = {uid} and is_default = 1 limit 1"
        logger.info(f"get_default_vdb_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_default_vdb_dt {my_dt}")
        return my_dt

    @staticmethod
    def set_user_default_vdb(uid: int, vdb_id: int):
        if not uid or not vdb_id:
            raise RuntimeError(f"set_default_vdb_param_null_err, {uid}, {vdb_id}")
        sql = f"update vdb_info set is_default = 1 where uid = {uid} and id = {vdb_id} limit 1"
        logger.info(f"set_default_vdb_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"set_default_vdb_dt {my_dt}")
        sql = f"update vdb_info set is_default = 0 where uid = {uid} and id != {vdb_id}"
        logger.info(f"set_default_vdb_exclude_sql, {sql}")
        my_dt1 = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"set_default_vdb_exclude_dt {my_dt1}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_file_name(file_name: str, uid: int, vdb_id: int) -> list:
        if not uid or not file_name or not vdb_id:
            raise RuntimeError(f"param_null_err {file_name}, {uid}, {vdb_id}")
        sql = f"select * from vdb_file_info where name = '{file_name}' and uid = {uid} and vdb_id = {vdb_id} limit 1"
        logger.info(f"get_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_md5(file_md5: str, uid: int, vdb_id: int) -> list:
        if not uid or not file_md5 or not vdb_id:
            raise RuntimeError(f"param_null_err {file_md5}, {uid}, {vdb_id}")
        sql = f"select * from vdb_file_info where file_md5 = '{file_md5}' and uid = {uid} and vdb_id = {vdb_id} limit 1"
        logger.info(f"get_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_task_id(task_id: int) -> dict:
        if not task_id:
            raise RuntimeError(f"param_null_err {task_id}")
        sql = f"select * from vdb_file_info where task_id = {task_id} limit 1"
        logger.info(f"get_file_info_by_task_id, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_file_info_by_task_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def get_vdb_file_info_by_id(file_id: int):
        if not file_id:
            raise RuntimeError(f"file_id_param_null_err {file_id}")
        sql = f"select * from vdb_file_info where id = {file_id} limit 1"
        logger.info(f"get_file_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"get_file_info_by_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_uid_vbd_id_file_name(file_name: str, uid: int, vdb_id: int):
        sql = f"delete from vdb_file_info where name ='{file_name}' and uid={uid} and vdb_id={vdb_id} limit 1 "
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_file_name_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_file_name_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_task_id(task_id: int):
        sql = f"delete from vdb_file_info where task_id={task_id} limit 1"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_vbd_task_id_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_vbd_task_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_id(file_id: int):
        if not file_id:
            logger.error(f"file_id_null_err, {file_id}")
            return
        sql = f"delete from vdb_file_info where id={file_id} limit 1 "
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_uid_vbd_id_file_id(file_id: int, uid: int, vdb_id: int):
        sql = f"delete from vdb_file_info where id ={file_id} and uid={uid} and vdb_id={vdb_id} limit 1 "
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_file_id_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_file_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def delete_vdb_file_by_uid_vbd_id(uid: int, vdb_id: int):
        sql = f"delete from vdb_file_info where uid={uid} and vdb_id={vdb_id}"
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"delete_file_by_uid_vbd_id_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"delete_file_by_uid_vbd_id_dt {my_dt}")
        return my_dt

    @staticmethod
    def save_vdb_file_info(original_file_name: str, saved_file_name: str, uid: int, vdb_id: int, task_id: int,
                           file_md5: str):
        sql = (f"insert into vdb_file_info (name, uid, vdb_id, file_path, task_id, file_md5) values"
               f" ('{original_file_name}', {uid}, {vdb_id}, '{saved_file_name}', {task_id}, '{file_md5}')")
        with sqlite3.connect(CFG_DB_FILE) as my_conn:
            logger.info(f"save_file_info_sql, {sql}")
            my_dt = DbUtl.sqlite_insert_delete_tool(my_conn, sql)
        logger.info(f"save_file_info_dt, {my_dt}")
        return my_dt

    @staticmethod
    def update_vdb_file_path(file_id: int, file_path: str):
        if not file_id or not file_path:
            raise RuntimeError(f"param_null_err, {file_id}, {file_path}")
        sql = f"update vdb_file_info set file_path = '{file_path}' where id = {file_id} limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"update_file_info_dt {my_dt}")
        return my_dt

    @staticmethod
    def update_vdb_file_process_info(file_id: int, process_info: str):
        if not file_id or not process_info:
            raise RuntimeError(f"param_null_err, {file_id}, {process_info}")
        sql = f"update vdb_file_info set process_info = '{process_info}' where id = {file_id} limit 1"
        logger.info(f"update_file_info_sql, {sql}")
        my_dt = DbUtl.sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
        logger.info(f"update_file_info_dt {my_dt}")
        return my_dt