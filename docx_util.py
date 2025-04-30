#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install python-docx
"""


from docx import Document

doc = Document("文件.docx")
# 提取文本
text = "\n".join([para.text for para in doc.paragraphs])
# 提取表格
for table in doc.tables:
    for row in table.rows:
        print([cell.text for cell in row.cells])