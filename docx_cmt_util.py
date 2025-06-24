#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
通过zipfile组件处理 docx 文档的批注信息，根据段落ID获取段落内容等
通过获取段落的批注，然后根据段落批注修改段落内容
"""
import logging.config
import os
import zipfile
from xml.etree import ElementTree as ET
from docx import Document
from docx.shared import RGBColor

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def get_comments_dict(target_doc: str) -> dict:
    """
    获取文档中所有批注及其关联的段落ID
    返回格式: {
        comment_id: {
            "author": 作者,
            "date": 日期,
            "text": 批注内容,
            "paragraph_id": 段落ID  # 新增
        }
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
            with z.open('word/comments.xml') as f:
                comments_xml = ET.fromstring(f.read())
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

                for comment in comments_xml.findall('.//w:comment', namespaces):
                    comment_id = comment.get(f'{{{namespaces["w"]}}}id')
                    if not comment_id:
                        continue

                    author = comment.get(f'{{{namespaces["w"]}}}author', '未知作者')
                    date = comment.get(f'{{{namespaces["w"]}}}date', '未知日期')
                    for t in comment.findall('.//w:t', namespaces):

                        if t.text:
                            text = ' '.join(t.text.strip())
                        else:
                            text = ""
                    comments_dict[comment_id] = {
                        "author": author,
                        "date": date,
                        "text": text,
                        "paragraph_id": None  # 初始化为None，后续填充
                    }

                    # 2. 解析正文 (document.xml)，关联批注和段落ID
                    if 'word/document.xml' not in z.namelist():
                        logger.warning("无法解析正文内容")

            with z.open('word/document.xml') as f:
                doc_xml = ET.fromstring(f.read())
                paragraphs = doc_xml.findall('.//w:p', namespaces)

                # 为每个段落生成唯一ID（如果没有现成的ID，用索引代替）
                for para_idx, paragraph in enumerate(paragraphs):
                    # 查找当前段落中的批注引用
                    comment_refs = paragraph.findall('.//w:commentReference', namespaces)
                    if not comment_refs:
                        continue

                    # 关联批注ID和段落ID（这里用索引作为段落ID）
                    for ref in comment_refs:
                        ref_id = ref.get(f'{{{namespaces["w"]}}}id')
                        if ref_id in comments_dict:
                            comments_dict[ref_id]["paragraph_id"] = para_idx
    except Exception as e:
        logger.error(f"解析文档时出错: {str(e)}", exc_info=True)
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
        if 'word/comments.xml' in z.namelist():
            with z.open('word/comments.xml') as f:
                logger.info(f"comments.xml内容:{f.read().decode('utf-8')}")

def get_para_comment_dict(file_fullpath: str) -> dict:
    comments_dict = get_comments_dict(file_fullpath)
    para_comments = {}
    for cid, data in comments_dict.items():
        para_id = data["paragraph_id"]
        if para_id is not None:
            para_comments[para_id] = data["text"]  # 一个段落只保留最后一条批注
    return para_comments

def test_get_comment():
    my_file = "/home/rd/doc/文档生成/comment_test.docx"
    comments_dict = get_comments_dict(my_file)
    logger.info(f"comments_dict={comments_dict}")
    for id, comment in comments_dict.items():
        logger.info(f"id:{id}, comment: {comment}")
        para_id = comment.get('paragraph_id')
        para_txt = get_paragraph_by_id(my_file, para_id)
        logger.info(f"para_id:{para_id}, para_txt:{para_txt}")


def modify_para_with_comment(target_doc: str, comments_dict: dict) -> Document:
    """
    将批注内容替换到对应段落，并将新文本设为红色
    :param target_doc: 需要修改的文档路径
    """
    if not os.path.exists(target_doc):
        logger.error(f"输入文件不存在: {target_doc}")
        return
    if not comments_dict:
        logger.warning(f"文件批注信息为空")
        return
    logger.info(f"comments: {comments_dict}")
    doc = Document(target_doc)
    try:
        for para_idx, para in enumerate(doc.paragraphs):
            if para_idx not in comments_dict:
                continue
            logger.info(f"matched_comment_for_para_idx {para_idx}")
            comment_text = comments_dict[para_idx]
            # TODO: 这里可以根据大模型对文本进行处理之后，生成新的文本，添加至文档中
            para.clear()
            run = para.add_run(comment_text)
            run.font.color.rgb = RGBColor(255, 0, 0)
    except Exception as e:
        logger.error(f"替换失败: {str(e)}", exc_info=True)
    return doc


def test_modify_para_with_comment():
    input_file = "/home/rd/doc/文档生成/comment_test.docx"
    para_comment_dict = get_para_comment_dict(input_file)
    output_doc = modify_para_with_comment(input_file, para_comment_dict)
    output_file = "modify_comment_test.docx"
    output_doc.save(output_file)
    logger.info(f"处理完成，输出文件: {output_file}")

if __name__ == "__main__":
    # test_get_comment()
    input_file = "/home/rd/doc/文档生成/comment_test.docx"
    # para_comment_dict = get_para_comment_dict(input_file)
    # logger.info(f"para_comment_dict: {para_comment_dict}")
    test_modify_para_with_comment()

