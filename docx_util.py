#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
处理docx的段落、标题、标题下的文本、文档目录、
修改docx的文档内容、设定新增的docx文档的文本格式等
"""
import logging.config
import os
import re
import time

from docx import Document
from docx.shared import RGBColor
from docx.text.paragraph import Paragraph
from vdb_oa_util import search_txt
from txt_util import get_txt_in_dir_by_keywords, strip_prefix_no

from sys_init import init_yml_cfg
from agt_util import classify_txt, gen_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

MIN_PROMPT_LEN = 20


def process_paragraph(paragraph: Paragraph, sys_cfg: dict) -> str:
    searched_txt = search_txt(paragraph.text, 0.5, sys_cfg, 1).strip()
    # logging.info(f"vdb_get_txt:\n{searched_txt}\nby_search_{paragraph.text}")
    return searched_txt


def extract_catalogue(target_doc: str) -> str:
    """
    生成 docx 文档的三级目录清单
    """
    doc = Document(target_doc)
    catalogue_lines = []
    # 初始化各级标题计数器 [一级, 二级, 三级]
    level_counters = [0, 0, 0]
    for para in doc.paragraphs:
        style_name = para.style.name.lower()  # 统一转换为小写
        # 检查是否为标题（兼容中英文样式名）
        if not style_name.startswith(('heading', '标题')):
            continue
        # 提取标题级别数字
        level_str = ''.join(filter(str.isdigit, style_name))
        if not level_str:
            continue
        level = int(level_str)
        if level <1 or level > 3:
            continue
        # 仅处理1-3级标题
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

def refresh_current_heading(para: Paragraph, heading: list) -> bool:
    if "Heading" not in para.style.name:
        return False

    level = int(para.style.name.split()[-1])  # 提取数字
    headings = {1: [], 2: [], 3: [], 4: [], 5: []}  # 按需扩展层级
    headings[level].append(para.text)
    logger.info(f"heading_part_caught: H{level}: {para.text}")
    if None == heading:
        logger.error("heading_list_cant't_be_refresh")
        return True
    if len(heading) != 0:
        heading.pop()
    heading.append(para.text)
    return True

def is_prompt_para(para: Paragraph, current_heading:list, sys_cfg: dict) -> bool:
    """
    判断写作要求文档中的每段文本，是否为用户所提的写作要求文本
    :param para: 写作要求word文档中的一个段落
    :param current_heading: 当前para 所在的目录
    :param sys_cfg: 系统配置，涉及大模型的地址等
    return False： 不是写作要求； True： 是写作要求
    """

    pattern = r'^(图|表)\s*\d+[\.\-\s]'  # 匹配"图1."/"表2-"等开头
    labels = ["需要生成文本", "不需要生成文本"]
    if refresh_current_heading(para, current_heading):
        return False
    if "TOC" in para.style.name or para._element.xpath(".//w:instrText[contains(.,'TOC')]"):
        logger.info(f"doc_table_of_content: {para.text}")
        return False
    if "Caption" in para.style.name or re.match(pattern, para.text):
        logger.info(f"table_or_picture_title: {para.text}")
        return False
    if not para.text:
        return False
    if len(para.text.strip()) < MIN_PROMPT_LEN:
        logger.info(f"ignored_short_txt {para.text}")
        return False
    if len(current_heading) == 0 or len(current_heading[0]) < 2:
        logger.info(f"heading_err_for_para, {current_heading}, {para.text}")
        return False
    classify_result = classify_txt(labels, para.text, sys_cfg, True)
    if labels[1] in classify_result:
        # logger.debug(f"classify={classify_result}, tile={current_heading}, para={para.text}")
        return False
    # logger.debug(f"classify={classify_result}, tile={current_heading}, para={para.text}")
    return True

def fill_doc_with_progress(task_id:str, progress_lock, task_progress:dict, doc_ctx: str, target_doc: str,
                           target_doc_catalogue: str, sys_cfg: dict, output_file_name:str):
    """
    :param task_id: 执行任务的ID
    :param progress_lock: A thread lock
    :param task_progress: task process information dict with task_id as key
    :param doc_ctx: 文档写作背景信息
    :param target_doc: 需要写的文档三级目录，以及各个章节的具体写作需求
    :param sys_cfg: 系统配置信息
    :param target_doc_catalogue: 需要写的文档的三级目录文本信息
    :param output_file_name: 输出文档的文件名
    """
    doc = Document(target_doc)
    gen_txt_count = 0
    current_heading = []
    total_paragraphs = len(doc.paragraphs)
    for index, my_para in enumerate(doc.paragraphs):
        percent = index / total_paragraphs * 100
        process_percent_bar_info = f"正在处理第 {index+1}/{total_paragraphs} 段文字，已生成 {gen_txt_count} 段文本，进度 {percent:.1f}%"
        logger.info(process_percent_bar_info)
        with progress_lock:
            task_progress[task_id] = {
                "text": process_percent_bar_info,
                "timestamp": time.time()
            }
        try:
            is_prompt = is_prompt_para(my_para, current_heading, sys_cfg)
            if not is_prompt:
                continue
            # logger.info(f"prompt_txt_of_heading {current_heading}, {my_para.text}")
            search_result = process_paragraph(my_para, sys_cfg['api'])
            demo_txt = f"{search_result}"
            # with progress_lock:
            #     task_progress[task_id] = f"正在处理文本[{my_para.text}]"
            llm_txt = gen_txt(doc_ctx, demo_txt, my_para.text, target_doc_catalogue, current_heading[0], sys_cfg, )
            gen_txt_count += 1
            # with progress_lock:
            #     task_progress[task_id] = f"生成文本：{llm_txt}"
        except Exception as ex:
            logger.error("fill_doc_job_err_to_break", ex)
            with progress_lock:
                task_progress[task_id] = {
                    "text": f"在处理文档的过程中出现了异常，任务已中途退出",
                    "timestamp": time.time()
                }
            break
        new_para = doc.add_paragraph()
        red_run = new_para.add_run(llm_txt)
        red_run.font.color.rgb = RGBColor(255, 0, 0)
        my_para._p.addnext(new_para._p)
        doc.save(output_file_name)
        if gen_txt_count > 0:
            txt_info = f"任务已完成，共处理 {total_paragraphs} 段文字，已生成 {gen_txt_count} 段文本，进度 100%"
        else:
            txt_info = f"任务已完成，共处理 {total_paragraphs} 段文字，进度 100%，未检测到创作需求描述，您可以尝试在需要创作的段落处填写： 描述/列出/简述xxxxx, 写作需求描述文字数量大于20个汉字"
        with progress_lock:
            task_progress[task_id] = {
                "text": txt_info,
                "timestamp": time.time()
            }

def fill_doc(doc_ctx: str, source_dir: str, target_doc: str, target_doc_catalogue: str, sys_cfg: dict) -> Document:
    """
    :param doc_ctx: 文档写作背景信息
    :param source_dir: 提供的样本文档
    :param target_doc: 需要写的文档三级目录，以及各个章节的具体写作需求
    :param sys_cfg: 系统配置信息
    :param target_doc_catalogue: 需要写的文档的三级目录文本信息
    """
    doc = Document(target_doc)
    current_heading = []
    total_paragraphs = len(doc.paragraphs)
    for index, my_para in enumerate(doc.paragraphs):
        percent = (index + 1) / total_paragraphs * 100
        process_percent_bar_info = f"正在处理第 {index+1}/{total_paragraphs} 段文字，进度 {percent:.1f}%"
        logger.info(f"percent: {process_percent_bar_info}")
        try:
            is_prompt = is_prompt_para(my_para, current_heading, sys_cfg)
            if not is_prompt:
                continue
            # logger.info(f"prompt_txt_of_heading {current_heading}, {my_para.text}")
            search_result = process_paragraph(my_para, sys_cfg['api'])
            if source_dir and os.path.exists(source_dir):
                source_para_txt = get_txt_in_dir_by_keywords(strip_prefix_no(current_heading[0]), source_dir)
                demo_txt = f"{source_para_txt}\n{search_result}"
                demo_txt = demo_txt.replace("\n", " ").strip()
            else:
                demo_txt = f"{search_result}"

            llm_txt = gen_txt(doc_ctx, demo_txt, my_para.text, target_doc_catalogue, current_heading[0], sys_cfg, )
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


if __name__ == "__main__":
    my_cfg = init_yml_cfg()
    my_source_dir = "/home/rd/doc/文档生成/knowledge_base"
    # my_target_doc = "/home/rd/doc/文档生成/output_template.docx"
    my_target_doc = "/home/rd/doc/文档生成/2.docx"
    # test_catalogue = extract_catalogue(my_target_doc)
    # logger.info(f"doc_catalogue: {test_catalogue}")
    doc_ctx = "我正在写一个可行性研究报告"
    doc_catalogue = get_catalogue(my_target_doc)
    logger.info(f"my_target_doc_catalogue: {doc_catalogue}")

    output_doc = fill_doc(doc_ctx, my_source_dir, my_target_doc, doc_catalogue, my_cfg)
    output_file = 'doc_output.docx'
    output_doc.save(output_file)
    logger.info(f"save_content_to_file: {output_file}")
