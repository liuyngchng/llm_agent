#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
处理 pptx 文档相关的元数据， 存储在 DB 中
"""
import logging.config
import sqlite3
import time

from common.cfg_util import CFG_DB_URI, CFG_DB_FILE, insert_del_sqlite, sqlite_output
from common.my_enums import DataType

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def save_meta_info(uid: int, task_id: int, doc_type: str, doc_title: str,
                   keywords: str, template_file_name: str) -> dict:
    """
    保存pptx文件处理任务的相关元数据信息
    :param uid: user id
    :param task_id: process task id
    :param doc_type: pptx content type
    :param doc_title: pptx content title
    :param keywords: 其他通用的写作要求
    :param template_file_name: pptx template file name
    :return:
    """
    logger.info(f"save_pptx_info {uid}, {task_id}, {doc_type}, {doc_title}, {keywords}, {template_file_name}")
    timestamp = time.time()
    # 生成类似格式（UTC时间）
    iso_str = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp))
    sql = (f"insert into pptx_file_info(uid, task_id, doc_type, doc_title, keywords, template_path, create_time) values "
           f"({uid}, {task_id}, '{doc_type}', '{doc_title}', '{keywords}', '{template_file_name}','{iso_str}')")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        logger.info(f"save_file_info_sql, {sql}")
        my_dt = insert_del_sqlite(my_conn, sql)
        return my_dt

def get_info_by_task_id(task_id: int) -> dict:
    """
    根据任务id获取pptx文件处理任务的相关元数据信息
    :param task_id: process task id
    :return:
    """
    if not task_id:
        raise RuntimeError(f"param_null_err {task_id}")
    sql = f"select * from pptx_file_info where task_id = {task_id} limit 1"
    logger.info(f"get_pptx_info_by_task_id_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_pptx_info_by_task_id_dt {my_dt}")
    return my_dt

def get_user_task_list(uid: int) -> dict:
    """
    根据任务id获取pptx文件处理任务的相关元数据信息
    :param uid: process task id
    :return:
    """
    if not uid:
        raise RuntimeError(f"param_uid_null_err {uid}")
    sql = f"select * from pptx_file_info where uid = {uid} order by task_id desc limit 100"
    # logger.info(f"get_user_pptx_task_list_by_uid_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    # logger.info(f"get_user_pptx_task_list_by_uid_dt {my_dt}")
    return my_dt

def get_processing_file_list()-> list:
    """
    获取需要处理的pptx任务信息清单
    """
    sql = f"select * from pptx_file_info where percent != 100 limit 100"
    # logger.info(f"get_pptx_processing_file_list_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    # logger.info(f"get_pptx_processing_file_list_dt {my_dt}")
    return my_dt

def delete_task(task_id: int):
    """
    根据任务id删除pptx文件处理任务的相关元数据信息
    :param task_id: process task id
    :return:
    """
    sql = f"delete from pptx_file_info where task_id ={task_id} limit 1 "
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        logger.info(f"delete_pptx_info_by_task_id_sql, {sql}")
        my_dt = insert_del_sqlite(my_conn, sql)
    logger.info(f"delete_pptx_info_by_task_id_dt {my_dt}")
    return my_dt


def update_process_info_by_task_id(task_id: int, process_info: str, percent = 0):
    """
    更新pptx文件处理任务的处理进度信息
    :param task_id: process task id
    :param process_info: process info
    :param percent: process percent
    :return:
    """
    if not task_id or not process_info:
        raise RuntimeError(f"param_null_err, {task_id}, {process_info}")
    if percent == 0:
        sql = f"update pptx_file_info set process_info = '{process_info}' where task_id = {task_id} limit 1"
    else:
        sql = f"update pptx_file_info set process_info = '{process_info}', percent= {percent} where task_id = {task_id} limit 1"
    logger.info(f"update_pptx_file_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_pptx_file_info_dt {my_dt}")
    return my_dt

def update_gen_txt_count_by_task_id(task_id: int, word_count: int):
    """
    更新pptx文件处理任务中生成的字数统计
    :param task_id: process task id
    :param word_count: 字数统计
    :return:
    """
    if not task_id or not word_count:
        raise RuntimeError(f"param_null_err, {task_id}, {word_count}")
    sql = f"update pptx_file_info set word_count = {word_count} where task_id = {task_id} limit 1"
    logger.info(f"update_pptx_gen_txt_count_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_pptx_gen_txt_count_dt {my_dt}")
    return my_dt

def save_output_file_path_by_task_id(task_id: int, file_path: str):
    """
    保存输出文档物理文件路径信息
    """
    if not task_id or not file_path:
        raise RuntimeError(f"param_null_err, {task_id}, {file_path}")
    sql = f"update pptx_file_info set file_path = '{file_path}' where task_id = {task_id} limit 1"
    logger.info(f"update_pptx_file_path_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_pptx_file_path_dt {my_dt}")
    return my_dt

def save_outline_by_task_id(task_id: int, outline: str):
    """
    保存输出的Word文档的三级目录
    """
    if not task_id or not outline:
        raise RuntimeError(f"param_null_err, {task_id}, {outline}")
    sql = f"update pptx_file_info set outline = '{outline}' where task_id = {task_id} limit 1"
    logger.info(f"update_pptx_outline_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_pptx_outline_dt {my_dt}")
    return my_dt

def update_img_count_by_task_id(task_id: int, img_count: int):
    """
    更新需要处理的pptx任务中的图片数量
    """
    if not task_id or not img_count:
        raise RuntimeError(f"param_null_err, {task_id}, {img_count}")
    sql = f"update pptx_file_info set img_count = {img_count} where task_id = {task_id} limit 1"
    logger.info(f"update_img_count_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_img_count_dt {my_dt}")
    return my_dt

def get_img_count_by_task_id(task_id: int)-> int:
    """
    获取需要处理的pptx任务中的图片数量
    """
    sql = f"select img_count from pptx_file_info where task_id = {task_id} limit 1"
    logger.info(f"get_img_count_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_img_count_dt, {my_dt}")
    if my_dt and my_dt[0]:
        return int(my_dt[0][0])
    else:
        return 0