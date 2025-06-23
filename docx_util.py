#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
"""
import logging.config
import os
import re

from docx import Document
from collections import defaultdict
from docx.shared import RGBColor
from docx.text.paragraph import Paragraph
from vdb_oa_util import search_txt
from txt_util import get_txt_in_dir_by_keywords, strip_prefix_no

from sys_init import init_yml_cfg
from agt_util import classify_txt, gen_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def process_paragraph(paragraph: Paragraph, sys_cfg: dict) -> str:
    prompt = paragraph.text
    gen_txt = search_txt(prompt, 0.5, sys_cfg, 1).strip()
    logging.info(f"vdb_get_txt:\n{gen_txt}\nby_search_{prompt}")
    return gen_txt


def extract_catalogue(target_doc: str) -> str:
    """
    生成docx 的三级目录清单
    """
    doc = Document(target_doc)
    catalogue_lines = []
    # 初始化各级标题计数器 [一级, 二级, 三级]
    level_counters = [0, 0, 0]

    for para in doc.paragraphs:
        style_name = para.style.name.lower()  # 统一转为小写

        # 检查是否为标题（兼容中英文样式名）
        if style_name.startswith(('heading', '标题')):
            # 提取标题级别数字
            level_str = ''.join(filter(str.isdigit, style_name))
            if level_str:
                level = int(level_str)
                if 1 <= level <= 3:  # 仅处理1-3级标题
                    # 更新计数器：当前级别+1，更低级别清零
                    level_index = level - 1
                    level_counters[level_index] += 1
                    for i in range(level_index + 1, 3):
                        level_counters[i] = 0

                    # 生成编号 (如 "2.1.1")
                    number_parts = []
                    for i in range(level):
                        number_parts.append(str(level_counters[i]))
                    number_str = '.'.join(number_parts)

                    # 添加缩进和目录行
                    indent = "  " * (level - 1)
                    catalogue_lines.append(f"{indent}{number_str} {para.text}")

    return "\n".join(catalogue_lines)

def is_prompt_para(para: Paragraph, current_heading:list, sys_cfg: dict) -> bool:
    """
    判断写作要求文档中的每段文本，是否为用户所提的写作要求文本
    :param para: 写作要求word文档中的一个段落
    :param current_heading: 当前para 所在的目录
    :param sys_cfg: 系统配置，涉及大模型的地址等
    return False： 不是写作要求； True： 是写作要求
    """
    headings = {1: [], 2: [], 3: [], 4: [], 5: []}  # 按需扩展层级
    pattern = r'^(图|表)\s*\d+[\.\-\s]'  # 匹配"图1."/"表2-"等开头
    labels = ["需要生成文本", "不需要生成文本"]
    if "Heading" in para.style.name:
        level = int(para.style.name.split()[-1])  # 提取数字
        headings[level].append(para.text)
        logger.info(f"heading_part: H{level}: {para.text}")
        if len(current_heading) != 0:
            current_heading.pop()
        current_heading.append(para.text)
        return False
    if "TOC" in para.style.name or para._element.xpath(".//w:instrText[contains(.,'TOC')]"):
        logger.info(f"doc_table_of_content: {para.text}")
        return False
    if "Caption" in para.style.name or re.match(pattern, para.text):
        logger.info(f"table_or_picture_title: {para.text}")
        return False
    if not para.text:
        return False
    if len(para.text.strip()) < 20:
        logger.info(f"ignored_short_txt {para.text}")
        return False
    if len(current_heading) == 0 or len(current_heading[0]) < 2:
        logger.info(f"heading_err_for_para, {current_heading}, {para.text}")
        return False
    classify_result = classify_txt(labels, para.text, sys_cfg, True)
    if labels[1] in classify_result:
        logger.info(f"classify={classify_result}, tile={current_heading}, para={para.text}")
        return False
    logger.info(f"classify={classify_result}, tile={current_heading}, para={para.text}")
    return True

def fill_doc_with_demo(source_dir: str, target_doc: str, target_doc_catalogue: str, sys_cfg: dict) -> Document:
    """
    :param source_dir: 提供的样本文档
    :param target_doc: 需要写的文档三级目录，以及各个章节的具体写作需求
    :param sys_cfg: 系统配置信息
    :param target_doc_catalogue: 需要写的文档的三级目录文本信息
    """
    doc = Document(target_doc)
    current_heading = []
    target_doc_catalogue_list = target_doc_catalogue.split('\n')
    for my_para in doc.paragraphs:
        try:
            is_prompt = is_prompt_para(my_para, current_heading, sys_cfg)
            if current_heading and len(current_heading) > 0:
                process_percent = calc_process_percent(current_heading[0], target_doc_catalogue_list)
                print_progress(process_percent)
            if not is_prompt:
                continue
            logger.info(f"prompt_txt_of_heading {current_heading}, {my_para.text}")
            search_result = process_paragraph(my_para, sys_cfg['api'])
            source_para_txt = get_txt_in_dir_by_keywords(strip_prefix_no(current_heading[0]), source_dir)
            demo_txt = f"{source_para_txt}\n{search_result}"
            demo_txt = demo_txt.replace("\n", " ").strip()
            llm_txt = gen_txt(demo_txt, my_para.text, target_doc_catalogue, current_heading[0], sys_cfg, )
            logger.info(f"llm_txt_for_instruction[{my_para.text}]\n===gen_llm_txt===\n{llm_txt}")
        except Exception as ex:
            logger.error("fill_doc_job_err_to_break", ex)
            break
        # if len(my_txt) > 0:
        new_para = doc.add_paragraph()
        red_run = new_para.add_run(llm_txt)
        red_run.font.color.rgb = RGBColor(255, 0, 0)
        my_para._p.addnext(new_para._p)
    return doc


def get_catalogue(target_doc: str) -> str:

    catalogue_file = "my_catalogue.txt"
    if os.path.exists(catalogue_file):
        logger.info(f"文件 {catalogue_file} 已存在")
        with open(catalogue_file, 'r', encoding='utf-8') as f:
            my_catalogue = f.read()
            logger.info(f"目录内容已从文件 {catalogue_file} 读取")
    else:
        logger.info(f"文件 {catalogue_file} 不存在，将创建")
        my_catalogue = extract_catalogue(target_doc)
        with open(catalogue_file, 'w', encoding='utf-8') as f:
            f.write(my_catalogue)
            logger.info(f"目录内容已写入 {catalogue_file}")
    return my_catalogue


def print_progress(percentage):
    """
    提取百分比数值（支持"30%"或直接30）
    """
    try:
        percent = float(percentage.strip('%')) if isinstance(percentage, str) else percentage
    except Exception as ex:
        logger.error("err_occurred", ex)
        percent = 0
    bar_length = 50
    filled = int(bar_length * percent / 100)
    bar = '[' + '#' * filled + '-' * (bar_length - filled) + ']'
    # print(f"当前进度： {bar} {percent:.0f}%", end='', flush=True)
    logger.info(f"process_percent： {bar} {percent:.0f}%")


def calc_process_percent(sub_title: str, target_doc_catalogue: list) -> str:
    """
    计算匹配行在文件中的位置百分比
    :param sub_title: 子标题
    :param target_doc_catalogue: 三集标题目录清单 list
    """
    try:
        total = len(target_doc_catalogue)
        for i, line in enumerate(target_doc_catalogue, 1):
            if sub_title in line:
                percent = (i / total) * 100
                return f"{percent:.1f}%"
        return "0%"
    except Exception as ex:
        logger.error("err_in_calc_process_percent", ex)
        return "0%"


import zipfile
from xml.etree import ElementTree as ET
from collections import defaultdict


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

def test_get_comment():
    my_file = "/home/rd/doc/文档生成/comment_test.docx"
    comments_dict = get_comments_dict(my_file)
    logger.info(f"comments_dict={comments_dict}")
    for id, comment in comments_dict.items():
        logger.info(f"id:{id}, comment: {comment}")
        para_id = comment.get('paragraph_id')
        para_txt = get_paragraph_by_id(my_file, para_id)
        logger.info(f"para_id:{para_id}, para_txt:{para_txt}")



if __name__ == "__main__":
    # inspect_docx_structure()
    test_get_comment()
    # my_cfg = init_yml_cfg()
    # my_source_dir = "/home/rd/doc/文档生成/knowledge_base"
    # # my_target_doc = "/home/rd/doc/文档生成/template.docx"
    # my_target_doc = "/home/rd/doc/文档生成/2.docx"
    # # test = extract_catalogue(my_target_doc)
    # doc_catalogue = get_catalogue(my_target_doc)
    # logger.info(f"my_target_doc_catalogue: {doc_catalogue}")
    # output_doc = fill_doc_with_demo(my_source_dir, my_target_doc, doc_catalogue, my_cfg)
    #
    # # for test purpose only
    # output_doc.add_heading("新增标题Test", 1)
    # output_doc.add_paragraph('新增段落Test')
    # output_file = 'doc_output.docx'
    # output_doc.save(output_file)
    # logger.info(f"save_content_to_file: {output_file}")
