#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
"""
import logging.config

from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.ns import nsdecls

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def get_numbering_text(para):
    num_pr = para._element.xpath(".//w:numPr")
    if not num_pr: return ""

    # 提取编号层级和ID
    ilvl = num_pr[0].xpath(".//w:ilvl/@w:val")[0]
    num_id = num_pr[0].xpath(".//w:numId/@w:val")[0]

    # 在文档的numbering.xml部分查找对应格式
    numbering = doc.part.numbering_part._element
    nums = numbering.xpath(f"//w:num[contains(@w:numId,'{num_id}')]",
                          namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
    if not nums:
        return ""
    num = nums[0]
    abstract_id = num.xpath(".//w:abstractNumId/@w:val")[0]

    # 根据abstractNum定义生成编号字符串
    abstract_num = numbering.xpath(f"//w:abstractNum[@w:abstractNumId='{abstract_id}']")[0]
    lvl = abstract_num.xpath(f".//w:lvl[@w:ilvl='{ilvl}']")[0]
    fmt = lvl.xpath(".//w:numFmt/@w:val")[0]  # 获取格式类型如decimal/roman等

    # 此处需根据fmt和实际计数生成编号(需完整实现计数逻辑)
    return "[编号占位]"

def process_paragraph(para: Paragraph):

    logging.info(f"para txt:\n{para.text}")

if __name__ == "__main__":

    doc = Document("/home/rd/doc/文档生成/template.docx")
    headings = {1: [], 2: [], 3: [], 4:[], 5:[]}  # 按需扩展层级

    for para in doc.paragraphs:
        if "Heading" not in para.style.name:
            if not para.text:
                continue
            logging.info(f"it is a text content under heading")
            process_paragraph(para)
        else:
            level = int(para.style.name.split()[-1])  # 提取数字
            headings[level].append(para.text)
            logging.info(f"H{level}: {para.text}")
            # get_numbering_text(para)
