#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
"""
import logging.config
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

# def get_numbering_text(para):
#     num_pr = para._element.xpath(".//w:numPr")
#     if not num_pr: return ""
#
#     # 提取编号层级和ID
#     ilvl = num_pr[0].xpath(".//w:ilvl/@w:val")[0]
#     num_id = num_pr[0].xpath(".//w:numId/@w:val")[0]
#
#     # 在文档的numbering.xml部分查找对应格式
#     numbering = doc.part.numbering_part._element
#     nums = numbering.xpath(f"//w:num[contains(@w:numId,'{num_id}')]",
#                           namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
#     if not nums:
#         return ""
#     num = nums[0]
#     abstract_id = num.xpath(".//w:abstractNumId/@w:val")[0]
#
#     # 根据abstractNum定义生成编号字符串
#     abstract_num = numbering.xpath(f"//w:abstractNum[@w:abstractNumId='{abstract_id}']")[0]
#     lvl = abstract_num.xpath(f".//w:lvl[@w:ilvl='{ilvl}']")[0]
#     fmt = lvl.xpath(".//w:numFmt/@w:val")[0]  # 获取格式类型如decimal/roman等
#
#     # 此处需根据fmt和实际计数生成编号(需完整实现计数逻辑)
#     return "[编号占位]"def get_numbering_text(para):
#     num_pr = para._element.xpath(".//w:numPr")
#     if not num_pr: return ""
#
#     # 提取编号层级和ID
#     ilvl = num_pr[0].xpath(".//w:ilvl/@w:val")[0]
#     num_id = num_pr[0].xpath(".//w:numId/@w:val")[0]
#
#     # 在文档的numbering.xml部分查找对应格式
#     numbering = doc.part.numbering_part._element
#     nums = numbering.xpath(f"//w:num[contains(@w:numId,'{num_id}')]",
#                           namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
#     if not nums:
#         return ""
#     num = nums[0]
#     abstract_id = num.xpath(".//w:abstractNumId/@w:val")[0]
#
#     # 根据abstractNum定义生成编号字符串
#     abstract_num = numbering.xpath(f"//w:abstractNum[@w:abstractNumId='{abstract_id}']")[0]
#     lvl = abstract_num.xpath(f".//w:lvl[@w:ilvl='{ilvl}']")[0]
#     fmt = lvl.xpath(".//w:numFmt/@w:val")[0]  # 获取格式类型如decimal/roman等
#
#     # 此处需根据fmt和实际计数生成编号(需完整实现计数逻辑)
#     return "[编号占位]"

def process_paragraph(paragraph: Paragraph, sys_cfg: dict) -> str:
    prompt = paragraph.text
    gen_txt = search_txt(prompt, 0.5, sys_cfg, 1).strip()
    logging.info(f"vdb_get_txt:\n{gen_txt}\nby_search_{prompt}")
    return gen_txt

def is_prompt_para(para: Paragraph, current_heading:list, sys_cfg: dict) -> bool:
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

def fill_doc_with_pdf(source_dir: str, target_doc: str, sys_cfg: dict) -> Document:
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
            llm_txt = gen_txt(llm_ctx_txt, my_para.text, sys_cfg)
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
    # doc = Document("/home/rd/doc/文档生成/template.docx")
    my_source_dir = "/home/rd/doc/文档生成/knowledge_base"
    my_target_doc = "/home/rd/doc/文档生成/template.docx"
    output_doc = fill_doc_with_pdf(my_source_dir, my_target_doc, my_cfg)

    # for test purpose only
    output_doc.add_heading("新增标题Test", 1)
    output_doc.add_paragraph('新增段落Test')
    output_file = 'doc_output.docx'
    output_doc.save(output_file)
    logger.info(f"save_content_to_file: {output_file}")
