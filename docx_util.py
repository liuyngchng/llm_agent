#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
"""
import logging.config
import os
import re

from docx import Document
from docx.shared import RGBColor
from docx.text.paragraph import Paragraph
from vdb_oa_util import search_txt
from txt_util import get_txt_in_dir_by_keywords, strip_prefix_no

from sys_init import init_yml_cfg
from agt_util import classify_txt, gen_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

catalogue = ""

def process_paragraph(paragraph: Paragraph, sys_cfg: dict) -> str:
    prompt = paragraph.text
    gen_txt = search_txt(prompt, 0.5, sys_cfg, 1).strip()
    logging.info(f"vdb_get_txt:\n{gen_txt}\nby_search_{prompt}")
    return gen_txt

def get_catalogue(target_doc: str) -> str:
    doc = Document(target_doc)
    for my_para in doc.paragraphs:
        logger.info(f"is heading or not")
    return ""
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

def fill_doc_with_pdf(source_dir: str, target_doc: str, sys_cfg: dict, catalogue: str) -> Document:
    """
    :param source_dir: 提供的样本文档
    :param target_doc: 需要写的文档三级目录，以及各个章节的具体写作需求
    :param sys_cfg: 系统配置信息
    :param catalogue: 需要写的文档的三级目录文本信息
    """
    doc = Document(target_doc)
    current_heading = []
    for my_para in doc.paragraphs:
        llm_txt = ""
        try:
            is_prompt = is_prompt_para(my_para, current_heading, sys_cfg)
            if not is_prompt:
                continue
            logger.info(f"prompt_txt_of_heading {current_heading}, {my_para.text}")
            search_result = process_paragraph(my_para, sys_cfg['api'])
            source_para_txt = get_txt_in_dir_by_keywords(strip_prefix_no(current_heading[0]), source_dir)
            llm_ctx_txt = f"{source_para_txt}\n{search_result}"
            llm_ctx_txt = llm_ctx_txt.replace("\n", " ").strip()
            llm_txt = gen_txt(llm_ctx_txt, my_para.text, sys_cfg, catalogue)
            logger.info(f"llm_txt_for_instruction[{my_para.text}]\n===gen_llm_txt===\n{llm_txt}")
        except Exception as ex:
            logger.error("fill_doc_job_err_to_break")
            break
        # if len(my_txt) > 0:
        new_para = doc.add_paragraph()
        red_run = new_para.add_run(llm_txt)
        red_run.font.color.rgb = RGBColor(255, 0, 0)
        my_para._p.addnext(new_para._p)
    return doc


if __name__ == "__main__":
    my_cfg = init_yml_cfg()
    my_source_dir = "/home/rd/doc/文档生成/knowledge_base"
    # my_target_doc = "/home/rd/doc/文档生成/template.docx"
    my_target_doc = "/home/rd/doc/文档生成/2.docx"
    catalogue_file = "my_catalogue.txt"
    if os.path.exists(catalogue_file):
        logger.info(f"文件 {catalogue_file} 已存在")
        with open(catalogue_file, 'w', encoding='utf-8') as f:
            my_catalogue = f.read()
            logger.info(f"目录内容已从文件 {catalogue_file} 读取")
    else:
        logger.info(f"文件 {catalogue_file} 不存在，将创建")
        my_catalogue = get_catalogue(my_target_doc)
        with open(catalogue_file, 'w', encoding='utf-8') as f:
            f.write(my_catalogue)
            logger.info(f"目录内容已写入 {catalogue_file}")

    output_doc = fill_doc_with_pdf(my_source_dir, my_target_doc, my_cfg, my_catalogue)

    # for test purpose only
    output_doc.add_heading("新增标题Test", 1)
    output_doc.add_paragraph('新增段落Test')
    output_file = 'doc_output.docx'
    output_doc.save(output_file)
    logger.info(f"save_content_to_file: {output_file}")
