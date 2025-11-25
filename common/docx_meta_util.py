#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
处理 docx 文档相关的元数据， 存储在 DB 中
"""
import json
import logging.config
import sqlite3

from common.cfg_util import insert_del_sqlite, sqlite_output
from common.const import CFG_DB_URI, CFG_DB_FILE
from common.my_enums import DataType
from common.cm_utils import get_time_str

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def save_doc_info(uid: int, task_id: int, doc_type: str, doc_title: str, doc_outline:str,
                  keywords: str, input_file_path: str, vdb_id: int, is_include_para_txt: int,
                  doc_ctx: str, output_file_path: str, vdb_dir: str, output_file_type: int =0) -> dict:
    """
    保存docx文件处理任务的相关元数据信息
    :param uid: user id
    :param task_id: process task id
    :param doc_type: docx content type
    :param doc_title: docx content title
    :param doc_outline: 文档的目录（默认三级目录）
    :param keywords: 其他通用的写作要求/或者评审的要求
    :param input_file_path: docx template file name/或者评审的材料, 这里可能是多个文档，多个文档的路径以','进行分割
    :param vdb_id: vector db id
    :param is_include_para_txt: 写作的 Word 文档模板中是否包含有文本段落
    :param doc_ctx: 进行文本写作的上下文
    :param output_file_path: 写作完成下载的文档的磁盘绝对路径
    :param output_file_type: 输出文件的类型， 0： docx; 1： xlsx
    :param vdb_dir: 向量知识库的磁盘物理绝对路径
    :return:
    """
    logger.debug(f"save_doc_info, {uid}, {task_id}, {doc_type}, {doc_title}, {keywords}, {input_file_path}")
    create_time = get_time_str()
    esc_doc_type = doc_type.replace("'", "''") if doc_type else ""
    esc_doc_title = doc_title.replace("'", "''") if doc_title else ""
    esc_doc_outline = doc_outline.replace("'", "''") if doc_outline else ""
    esc_keywords = keywords.replace("'", "''") if keywords else ""
    esc_input_file_path = input_file_path.replace("'", "''") if input_file_path else ""
    esc_doc_ctx = doc_ctx.replace("'", "''") if doc_ctx else ""
    esc_output_file_path = output_file_path.replace("'", "''") if output_file_path else ""
    escaped_vdb_dir = vdb_dir.replace("'", "''") if vdb_dir else ""
    sql = (f"insert into doc_file_info(uid, task_id, doc_type, doc_title, doc_outline, "
           f"keywords, input_file_path, vdb_id, is_include_para_txt, "
           f"doc_ctx, output_file_path, vdb_dir, output_file_type, create_time) values "
           f"({uid}, {task_id}, '{esc_doc_type}', '{esc_doc_title}', '{esc_doc_outline}',"
           f"'{esc_keywords}', '{esc_input_file_path}', {vdb_id}, {is_include_para_txt}, "
           f"'{esc_doc_ctx}', '{esc_output_file_path}', '{escaped_vdb_dir}', {output_file_type},'{create_time}')")
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        logger.debug(f"save_doc_info_sql, {sql}")
        my_dt = insert_del_sqlite(my_conn, sql)
        return my_dt

def get_doc_info(task_id: int) -> dict:
    """
    根据任务id获取docx文件处理任务的相关元数据信息
    :param task_id: process task id
    :return:
    """
    if not task_id:
        raise RuntimeError(f"param_null_err {task_id}")
    sql = f"select * from doc_file_info where task_id = {task_id} limit 1"
    logger.info(f"get_docx_info_by_task_id_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_docx_info_by_task_id_dt {my_dt}")
    return my_dt

def get_user_task_list(uid: int) -> dict:
    """
    根据任务id获取docx文件处理任务的相关元数据信息
    :param uid: process task id
    :return:
    """
    if not uid:
        raise RuntimeError(f"param_uid_null_err {uid}")
    sql = f"select * from doc_file_info where uid = {uid} order by task_id desc limit 100"
    # logger.info(f"get_user_docx_task_list_by_uid_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    # logger.info(f"get_user_docx_task_list_by_uid_dt {my_dt}")
    return my_dt

def get_processing_file_list()-> list:
    """
    获取需要处理的docx任务信息清单
    """
    sql = f"select * from doc_file_info where percent != 100 limit 100"
    # logger.info(f"get_docx_processing_file_list_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    # logger.info(f"get_docx_processing_file_list_dt {my_dt}")
    return my_dt

def delete_task(task_id: int):
    """
    根据任务id删除docx文件处理任务的相关元数据信息
    :param task_id: process task id
    :return:
    """
    sql = f"delete from doc_file_info where task_id ={task_id} limit 1 "
    with sqlite3.connect(CFG_DB_FILE) as my_conn:
        logger.info(f"delete_docx_info_by_task_id_sql, {sql}")
        my_dt = insert_del_sqlite(my_conn, sql)
    logger.info(f"delete_docx_info_by_task_id_dt {my_dt}")
    return my_dt


def update_process_info(uid: int, task_id: int, process_info: str, percent = -1):
    """
    更新docx文件处理任务的处理进度信息
    :param uid: user id
    :param task_id: process task id
    :param process_info: process info
    :param percent: process percent
    :return:
    """
    if not task_id or not process_info:
        raise RuntimeError(f"{uid}, param_null_err, {task_id}, {process_info}")
    if percent == -1:
        sql = f"update doc_file_info set process_info = '{process_info}' where uid = {uid} and task_id = {task_id} limit 1"
    else:
        sql = f"update doc_file_info set process_info = '{process_info}', percent= {percent} where uid = {uid} and task_id = {task_id} limit 1"
    logger.debug(f"{uid}, {task_id}, update_doc_file_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.debug(f"{uid}, {task_id}, update_doc_file_info_dt, {my_dt}")
    return my_dt

def set_doc_info_para_task_created_flag(uid: int, task_id: int):
    """
    在 doc_file_info 中记录 段落生成任务已创建，置位标记位
    :param uid: user id
    :param task_id: process task idt
    :return:
    """
    if not task_id:
        raise RuntimeError(f"{uid}, param_null_err, {task_id}")
    sql = f"update doc_file_info set is_para_task_created = 1 where task_id = {task_id} limit 1"
    logger.info(f"{uid}, update_doc_file_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"{uid}, update_doc_file_info_dt, {my_dt}")
    return my_dt

def save_para_task(uid: int, task_id: int, tasks: list):
    """
    保存用户文档生成任务的各个段落生成的子任务清单,
    一个文档写作任务的任务ID task_id 对应多个 doc_para_info 记录
    :param uid: user id
    :param task_id: process task id
    :param tasks: 单个文档生成任务的段落生成任务清单
    :return:
    """
    if not task_id or not tasks:
        raise RuntimeError(f"{uid}, save_para_task_param_null_err, {task_id}, {tasks}")
    my_values = ""
    for task in tasks:
        if isinstance(task['current_heading'], list):
            heading_str = json.dumps(task['current_heading'], ensure_ascii=False)
        else:
            heading_str = str(task['current_heading'])
        heading = heading_str.replace("'", "''")
        unique_key = task['unique_key'].replace("'", "''")
        para_text = task['para_text'].replace("'", "''")
        user_comment = task['user_comment'].replace("'", "''")
        current_sub_title = task['current_sub_title'].replace("'", "''")
        namespaces = task.get('namespaces', '')
        if namespaces is None:
            namespaces = ''
        namespaces = str(namespaces).replace("'", "''")
        create_time = get_time_str()
        value_item = (f"({uid}, {task_id},{task['para_id']},'{heading}','{unique_key}',"
                      f"'{para_text}','{user_comment}','{current_sub_title}',"
                      f"'{namespaces}','{create_time}')")  # 注意 namespaces 和 create_time 之间用逗号分隔

        if my_values:
            my_values = f"{my_values}, {value_item}"
        else:
            my_values = value_item

    sql = (f"insert into doc_para_info (uid, task_id, para_id, heading, unique_key, "
           f"para_text, user_comment, current_sub_title, namespaces, create_time) values {my_values}")
    logger.debug(f"save_doc_para_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.debug(f"save_doc_para_info_dt, {my_dt}")
    return my_dt

def save_gen_para_txt(task_id: int, para_id: int, gen_txt: str, word_count: int, contains_mermaid: int):
    """
    保存用户文档生成任务的系统子任务清单,,一个文档写作任务的任务ID task_id 对应多个 doc_para_info 记录
    :param task_id: process task id
    :param para_id: 文档段落 ID
    :param gen_txt: 当前段落生成的文本，后续将会将文本插入  para_id 之后
    :param word_count: 生成文本的字数
    :param contains_mermaid: 是否包含mermaid脚本
    :return:
    """
    if not task_id or not para_id or not gen_txt:
        raise RuntimeError(f"param_null_err, {task_id}, {para_id}, {gen_txt}")
    escaped_gen_txt = gen_txt.replace("'", "''")
    update_time = get_time_str()
    sql = (f"update doc_para_info set gen_txt='{escaped_gen_txt}',word_count={word_count},contains_mermaid={contains_mermaid},"
       f"update_time='{update_time}',status=1 where task_id={task_id} and para_id = {para_id} limit 1")
    logger.info(f"save_gen_para_txt_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"save_gen_para_txt_dt, {my_dt}")
    return my_dt

def get_para_info(task_id: int, para_id: int=-1)-> list:
    """
    查询用户文档生成需求的并行子任务清单,一个文档写作任务的任务ID task_id 对应多个para_info
    :param task_id: 文档处理的任务 ID
    :param para_id: 文档段落 ID
    :return:
    """
    if not task_id:
        raise RuntimeError(f"param_null_err, {task_id}")
    if para_id == -1:
        sql = f"select * from doc_para_info where task_id = {task_id}"
    else:
        sql = f"select * from doc_para_info where task_id = {task_id} and para_id = {para_id} limit 1"
    logger.info(f"get_para_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_para_info_dt, {my_dt}")
    return my_dt

def get_para_list_with_status(task_id: int, status: int, is_order_by_para_id_desc: bool=True)-> list:
    """
    查询用户文档生成需求的并行子任务清单,一个文档写作任务的任务ID task_id 对应多个para_info
    :param task_id: 文档处理的任务 ID
    :param status: 是否已经完成， 0： LLM 尚未生成对应的文本， 1:LLM 已生成对应的文本
    :param is_order_by_para_id_desc: 是否按照 pard_id 倒序排列，默认倒序
    :return:
    """
    if not task_id:
        raise RuntimeError(f"param_null_err, {task_id}")
    base_sql = f"select * from doc_para_info where task_id = {task_id} and status = {status}"
    if is_order_by_para_id_desc:
        sql = f"{base_sql} order by para_id desc"
    else:
        sql = f"{base_sql} order by para_id"
    logger.info(f"get_para_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_para_info_dt, {my_dt}")
    return my_dt

def count_para_task(task_id: int)-> list:
    """
    查询用户文档生成需求的并行子任务清单,一个文档写作任务的任务ID task_id 对应多个para_info
    :param task_id: 文档处理的任务 ID
    :return:
    """
    if not task_id:
        raise RuntimeError(f"param_null_err, {task_id}")
    sql = f"select count(1) from doc_para_info where task_id = {task_id}"
    logger.info(f"get_para_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_para_info_dt, {my_dt}")
    return my_dt

def count_mermaid_para(task_id: int)-> list:
    """
    查询用户文档生成需求的并行子任务清单,一个文档写作任务的任务ID task_id 对应多个para_info
    :param task_id: 文档处理的任务 ID
    :return:
    """
    if not task_id:
        raise RuntimeError(f"param_null_err, {task_id}")
    sql = f"select count(1) from doc_para_info where task_id = {task_id} and contains_mermaid = 1"
    logger.info(f"get_para_info_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_para_info_dt, {my_dt}")
    return my_dt

def update_gen_txt_count_by_task_id(task_id: int, word_count: int):
    """
    更新docx文件处理任务中生成的字数统计
    :param task_id: process task id
    :param word_count: 字数统计
    :return:
    """
    if not task_id or not word_count:
        raise RuntimeError(f"param_null_err, {task_id}, {word_count}")
    sql = f"update doc_file_info set word_count = {word_count} where task_id = {task_id} limit 1"
    logger.info(f"update_docx_gen_txt_count_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_docx_gen_txt_count_dt {my_dt}")
    return my_dt
def save_outline_by_task_id(task_id: int, outline: str):
    """
    保存输出的Word文档的三级目录
    """
    if not task_id or not outline:
        raise RuntimeError(f"param_null_err, {task_id}, {outline}")
    sql = f"update doc_file_info set outline = '{outline}' where task_id = {task_id} limit 1"
    logger.info(f"update_docx_outline_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_docx_outline_dt {my_dt}")
    return my_dt

def update_img_count_by_task_id(task_id: int, img_count: int):
    """
    更新需要处理的docx任务中的图片数量
    """
    if not task_id or not img_count:
        raise RuntimeError(f"param_null_err, {task_id}, {img_count}")
    sql = f"update doc_file_info set img_count = {img_count} where task_id = {task_id} limit 1"
    logger.info(f"update_img_count_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"update_img_count_dt {my_dt}")
    return my_dt

def get_img_count_by_task_id(task_id: int)-> int:
    """
    获取需要处理的docx任务中的图片数量
    """
    sql = f"select img_count from doc_file_info where task_id = {task_id} limit 1"
    logger.info(f"get_img_count_sql, {sql}")
    my_dt = sqlite_output(CFG_DB_URI, sql, DataType.JSON.value)
    logger.info(f"get_img_count_dt, {my_dt}")
    if my_dt and my_dt[0]:
        return int(my_dt[0][0])
    else:
        return 0