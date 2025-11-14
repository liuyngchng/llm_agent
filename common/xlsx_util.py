#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def get_xlsx_md_txt(excel_path:str, include_sheet_names=True) -> str:
    """
    将 Excel 中的多个 sheet 转换为 markdown 格式的文本
    """
    import pandas as pd
    try:
        # 读取所有工作表
        excel_file = pd.ExcelFile(excel_path)
        markdown_parts = []

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)

            if include_sheet_names:
                markdown_parts.append(f"## 工作表: {sheet_name}")
                markdown_parts.append("")

            if not df.empty:
                # 处理 NaN 值
                df = df.fillna('')
                markdown_table = df.to_markdown(index=False)
                markdown_parts.append(markdown_table)
                markdown_parts.append("")  # 空行分隔

        return "\n".join(markdown_parts)
    except Exception as e:
        logger.error(f"excel_to_md_error, file {excel_path}, {str(e)}")
        return ""