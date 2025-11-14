#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def get_docx_md_txt(docx_path: str) -> str:
    """
    # 使用前需要安装 pandoc: https://pandoc.org/installing.html
    # pip install pypandoc
    """
    import pypandoc
    try:
        output = pypandoc.convert_file(docx_path, 'md', format='docx')
        return output
    except Exception as e:
        logger.error(f"docx_to_md_error, file {docx_path}, {str(e)}")
        return ""





