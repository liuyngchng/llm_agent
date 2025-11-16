#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os

from common import docx_meta_util
from common.docx_md_util import get_md_file_content, convert_md_to_docx, save_content_to_md_file
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output_doc"


def generate_review_report(uid: int, doc_type: str, review_topic: str, task_id: int,
                           criteria_file: str, paper_file: str):
    """
    生成评审报告
    :param uid: 用户ID
    :param doc_type: 生成文档的内容类型
    :param review_topic: 文档标题
    :param task_id: 任务ID
    :param criteria_file: 评审标准文件的绝对路径
    :param paper_file: 评审材料文件的绝对路径
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {review_topic}, "
                f"task_id: {task_id}, criteria_file: {criteria_file}, "
                f"review_file: {paper_file}")
    try:
        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始解析评审标准...", 0)

        # 获取评审标准的文件内容，格式为 Markdown
        criteria_data = get_md_file_content(criteria_file)
        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始分析评审材料...", 30)



        docx_meta_util.update_process_info_by_task_id(uid, task_id, "生成评审报告...", 60)

        # TODO: 根据评审标准和评审材料生成评审报告
        review_result = generate_ai_review(criteria_data, paper_file)

        # 生成输出文件
        output_file_name = f"output_{task_id}.md"
        output_md_file = save_content_to_md_file(review_result, output_file_name, output_abs_path=True)

        docx_file_full_path = convert_md_to_docx(output_md_file, output_abs_path=True)
        logger.info(f"{uid}, {task_id}, 评审报告生成成功, {docx_file_full_path}")

        docx_meta_util.update_process_info_by_task_id(uid, task_id, "评审报告生成完毕", 100)

    except Exception as e:
        docx_meta_util.update_process_info_by_task_id(uid, task_id, f"任务处理失败: {str(e)}")
        logger.exception("评审报告生成异常", e)

def get_md_file_catalogue(md_file_path: str) -> dict:
    """
    从 Markdown 文件中获取目录
    :param md_file_path: Markdown 文件路径
    :return: 目录内容字典，多级目录嵌套
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        catalog = {}
        current_levels = {0: catalog}  # 用于跟踪各级别的当前节点
        last_level = 0

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # 检查标题行 (从 # 到 ######)
            if line.startswith('#'):
                # 计算标题级别
                level = 0
                for char in line:
                    if char == '#':
                        level += 1
                    else:
                        break

                if level > 6:  # Markdown 最多支持6级标题
                    continue

                # 提取标题文本
                title = line[level:].strip()
                if not title:  # 跳过空标题
                    continue

                # 创建标题节点
                node = {
                    'title': title,
                    'level': level,
                    'line': line_num,
                    'children': {}
                }

                # 找到父级别
                parent_level = level - 1
                while parent_level >= 0 and parent_level not in current_levels:
                    parent_level -= 1

                if parent_level >= 0:
                    # 添加到父级的children中
                    parent_node = current_levels[parent_level]
                    if 'children' not in parent_node:
                        parent_node['children'] = {}
                    parent_node['children'][title] = node
                else:
                    # 作为根节点
                    catalog[title] = node

                # 更新当前级别
                current_levels[level] = node
                last_level = level

        logger.info(f"成功提取目录结构，共找到 {len(catalog)} 个根级标题")
        return catalog

    except FileNotFoundError:
        logger.error(f"Markdown文件不存在: {md_file_path}")
        return {}
    except Exception as e:
        logger.error(f"提取目录失败: {md_file_path}, 错误: {str(e)}")
        return {}

def generate_ai_review(criteria_data: str, review_file_path: str) -> str:
    """
    :param criteria_data: 评审标准的文本内容，格式为markdown
    :param review_file_path: 评审文件的绝对路径, 格式人诶 markdown
    """
    # TODO: 根据评审标准文本和评审材料生成评审报告
    # 解析评审材料文件的目录
    catalogue = get_md_file_catalogue(review_file_path)
    return ""