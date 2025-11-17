#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os

import markdown
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def get_html_ctx_from_md(abs_path: str) -> tuple[str, str]:
    """
    读取 markdown 文件的内容，转换为可在 html页面模板进行渲染的内容
    :param abs_path markdown 文件的绝对路径
    return
        toc_content 目录信息
        html_content 文本信息
    """
    toc_content = ""
    html_content = ""
    try:
        if os.path.exists(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            md = markdown.Markdown(
                extensions=[
                    'markdown.extensions.extra',
                    'markdown.extensions.codehilite',
                    'markdown.extensions.tables',
                    'markdown.extensions.toc'
                ]
            )
            html_content = md.convert(markdown_content)
            toc_content = md.toc if hasattr(md, 'toc') else ""
        else:
            html_content = f"<p>读取的文件不存在</p>"
    except Exception as e:
        logger.error(f"Error reading markdown file: {e}")
        html_content = f"<p>读取文件时出错: {str(e)}</p>"
    return html_content, toc_content