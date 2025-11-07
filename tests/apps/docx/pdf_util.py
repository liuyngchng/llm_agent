#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from PyPDF2 import PdfReader

reader = PdfReader("file.pdf")
for outline in reader.outline:
    if isinstance(outline, list): continue
    page = reader.get_page(outline.page)  # 获取该目录项对应页码
    text = page.extract_text()