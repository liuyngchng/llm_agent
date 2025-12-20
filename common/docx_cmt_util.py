#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install python-docx
处理word 文档批注功能（docx，修订模式）的一些工具
"""
import logging.config
import os
import time
import zipfile

from xml.etree import ElementTree as ET
from docx import Document

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

def get_comments_dict(target_doc: str) -> dict:
    """
    获取文档中所有批注及其关联的段落ID，如果一个段落有多个批注，则应将多个批注合并为一个；
    返回格式: {
        paragraph_index: comment_text
    }
    """
    if not os.path.exists(target_doc):
        logger.error(f"文件不存在: {target_doc}")
        return {}

    comments_dict = {}
    try:
        with zipfile.ZipFile(target_doc) as z:
            # 1. 解析批注 (comments.xml)
            if 'word/comments.xml' not in z.namelist():
                logger.warning("文档中没有批注")
                return {}

            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

            # 先解析文档结构，建立段落索引
            if 'word/document.xml' not in z.namelist():
                logger.warning("无法解析正文内容")
                return {}

            with z.open('word/document.xml') as f:
                doc_xml = ET.fromstring(f.read())
                paragraphs = doc_xml.findall('.//w:p', namespaces)

                # 建立段落ID到评论IDs的映射
                para_to_comments = {}
                for i, paragraph in enumerate(paragraphs):
                    # 提取段落文本内容
                    para_text = ' '.join(
                        t.text.strip()
                        for t in paragraph.findall('.//w:t', namespaces)
                        if t.text and t.text.strip()
                    )
                    logger.debug(
                        f"段落ID: {i}, 段落内容: {para_text}")
                    # 查找当前段落中的批注引用
                    comment_refs = paragraph.findall('.//w:commentReference', namespaces)
                    comment_ids = []
                    for ref in comment_refs:
                        ref_id = ref.get(f'{{{namespaces["w"]}}}id')
                        if ref_id:
                            comment_ids.append(ref_id)
                    if comment_ids:
                        para_to_comments[i] = comment_ids
                        # 打印段落ID、段落内容和批注引用信息
                        logger.debug(f"段落ID: {i}, 段落内容: {para_text[:50]}{'...' if len(para_text) > 50 else ''}, 批注引用ID: {comment_ids}")

            # 2. 解析批注内容
            with z.open('word/comments.xml') as f:
                comments_xml = ET.fromstring(f.read())

                comment_texts = {}
                for comment in comments_xml.findall('.//w:comment', namespaces):
                    comment_id = comment.get(f'{{{namespaces["w"]}}}id')
                    if not comment_id:
                        continue

                    # 提取批注文本
                    comment_text_parts = []
                    for t in comment.findall('.//w:t', namespaces):
                        if t.text:
                            comment_text_parts.append(t.text.strip())

                    # 修复：确保正确合并多个文本部分
                    comment_texts[comment_id] = ' '.join(comment_text_parts).strip()
                    # 打印批注ID和批注内容
                    logger.debug(f"批注ID: {comment_id}, 批注内容: {comment_texts[comment_id]}")

                # 建立段落索引到合并后的批注文本的映射
                for para_idx, comment_ids in para_to_comments.items():
                    # 修复：正确合并同一段落的多个批注
                    merged_comment_text = ' '.join(
                        comment_texts[cid] for cid in comment_ids if cid in comment_texts
                    ).strip()
                    if merged_comment_text:
                        comments_dict[para_idx] = merged_comment_text
                        # 打印段落ID和最终合并的批注内容
                        logger.debug(f"段落 {para_idx} 关联批注: {merged_comment_text}")

    except Exception as e:
        logger.error(f"解析文档时出错: {str(e)}", exc_info=True)

    logger.info(f"提取到批注信息: {comments_dict}")
    return comments_dict

def get_paragraph_by_id(target_doc: str, paragraph_id: int) -> str:
    """
    通过段落ID获取段落文本
    :param target_doc: Word文档路径
    :param paragraph_id: 段落ID（索引或实际ID）
    :return: 段落文本（如未找到返回空字符串）
    """
    if not os.path.exists(target_doc):
        logger.error(f"文件不存在: {target_doc}")
        return ""

    try:
        with zipfile.ZipFile(target_doc) as z:
            if 'word/document.xml' not in z.namelist():
                logger.warning("无法解析正文内容")
                return ""

            with z.open('word/document.xml') as f:
                doc_xml = ET.fromstring(f.read())
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                paragraphs = doc_xml.findall('.//w:p', namespaces)

                if paragraph_id < 0 or paragraph_id >= len(paragraphs):
                    logger.warning(f"段落ID {paragraph_id} 超出范围")
                    return ""

                # 提取段落文本
                paragraph = paragraphs[paragraph_id]
                text = ' '.join(
                    t.text.strip()
                    for t in paragraph.findall('.//w:t', namespaces)
                    if t.text and t.text.strip()
                )
                return text

    except Exception as e:
        logger.error(f"解析段落时出错: {str(e)}", exc_info=True)
        return ""

def inspect_docx_structure():
    target_doc = "/home/rd/doc/文档生成/comment_test.docx"
    with zipfile.ZipFile(target_doc) as z:
        logger.info(f"文档包含的文件:{z.namelist()}")
        if 'word/comments.xml' not in z.namelist():
            logger.error("no word/comments.xml file")
            return
        with z.open('word/comments.xml') as f:
            logger.info(f"comments.xml内容:{f.read().decode('utf-8')}")

def get_para_comment_dict(file_full_path: str) -> dict:
    """
    获取文档中所有用户修改批注（修订模式）及其关联的段落ID
    返回格式: {
        comment_id: {
            "author": 作者,
            "date": 日期,
            "text": 批注内容,
            "paragraph_id": 段落ID  # 新增
        }
    """

    comments_dict = get_comments_dict(file_full_path)
    para_comments = {}
    for cid, data in comments_dict.items():
        para_id = data["paragraph_id"]
        if not para_id:
            continue
        para_comments[para_id] = data["text"]  # 一个段落只保留最后一条批注
    return para_comments

def refresh_current_heading_xml(paragraph, current_heading: list, namespaces: dict):
    """
    从 XML 段落更新当前标题结构
    根据段落样式判断标题级别，维护当前标题层级
    """
    # 查找段落样式
    pPr = paragraph.find('.//w:pPr', namespaces)
    if pPr is None:
        return  # 没有段落属性，不是标题
    # 查找段落样式
    pStyle = pPr.find('.//w:pStyle', namespaces)
    if pStyle is None:
        return  # 没有样式，不是标题
    style_val = pStyle.get(f'{{{namespaces["w"]}}}val', '')
    if not style_val:
        return
    # 提取段落文本内容
    heading_text = ' '.join(
        t.text.strip() for t in paragraph.findall('.//w:t', namespaces)
        if t.text and t.text.strip()
    )
    if not heading_text:
        return  # 空标题，不处理
    # 判断标题级别
    if 'Heading1' in style_val or '标题1' in style_val or '1' in style_val:
        # 一级标题：清空当前结构，重新开始
        current_heading.clear()
        current_heading.append(heading_text)
        logger.debug(f"更新为一级标题: {heading_text}")
    elif 'Heading2' in style_val or '标题2' in style_val or '2' in style_val:
        # 二级标题：保留一级标题，更新二级标题
        if len(current_heading) > 0:
            if len(current_heading) > 1:
                current_heading[1] = heading_text
            else:
                current_heading.append(heading_text)
        else:
            # 如果没有一级标题，直接设为一级标题
            current_heading.append(heading_text)
        logger.debug(f"更新为二级标题: {current_heading}")
    elif 'Heading3' in style_val or '标题3' in style_val or '3' in style_val:
        # 三级标题：保留一二级标题，更新三级标题
        if len(current_heading) > 1:
            if len(current_heading) > 2:
                current_heading[2] = heading_text
            else:
                current_heading.append(heading_text)
        elif len(current_heading) > 0:
            # 如果只有一级标题，添加二级标题（用空字符串占位）
            current_heading.append("")
            current_heading.append(heading_text)
        else:
            # 如果没有上级标题，直接设为一级标题
            current_heading.append(heading_text)
        logger.debug(f"更新为三级标题: {current_heading}")
    elif 'Heading4' in style_val or '标题4' in style_val or '4' in style_val:
        # 四级标题：保留上级标题，更新四级标题
        while len(current_heading) < 3:
            current_heading.append("")  # 用空字符串填充缺失的中间级别
        if len(current_heading) > 3:
            current_heading[3] = heading_text
        else:
            current_heading.append(heading_text)
        logger.debug(f"更新为四级标题: {current_heading}")
    # 其他 Heading5-9 可以类似扩展
    elif any(f'Heading{i}' in style_val for i in range(5, 10)) or any(f'标题{i}' in style_val for i in range(5, 10)):
        # 处理5-9级标题
        heading_level = None
        for i in range(5, 10):
            if f'Heading{i}' in style_val or f'标题{i}' in style_val or str(i) in style_val:
                heading_level = i
                break
        if heading_level:
            # 确保标题层级完整
            while len(current_heading) < heading_level:
                current_heading.append("")

            if len(current_heading) >= heading_level:
                current_heading[heading_level - 1] = heading_text
            logger.debug(f"更新为{heading_level}级标题: {current_heading}")


def get_elapsed_time(start_timestamp: int) -> str:
    """
    计算任务处理时间
    :param start_timestamp: 任务开始时间戳
    """
    current_time = int(time.time())
    elapsed_seconds = current_time - start_timestamp
    minutes = elapsed_seconds // 60
    seconds = elapsed_seconds % 60
    return f"用时 {minutes} 分 {seconds} 秒"


def test_get_comment():
    my_file = "/home/rd/Desktop/1.docx"
    doc = Document(my_file)
    for para_idx, para in enumerate(doc.paragraphs):
        logger.debug(f"para_idx: {para_idx}, para_text: '{para.text}'")
    comments_dict = get_comments_dict(my_file)
    logger.info(f"comments_dict={comments_dict}")
    for para_id, comment in comments_dict.items():
        logger.info(f"id:{para_id}, comment: {comment}")
if __name__ == "__main__":
    test_get_comment()
    # input_file = "/home/rd/doc/文档生成/comment_test.docx"
    # para_comment_dict = get_para_comment_dict(input_file)
    # logger.info(f"para_comment_dict: {para_comment_dict}")
    # test_modify_para_with_comment()

