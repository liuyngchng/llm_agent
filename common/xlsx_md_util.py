#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import os
from pathlib import Path

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

OUTPUT_DIR = "output_doc"


def convert_xlsx_to_md(excel_path: str, include_sheet_names: bool = True, output_abs_path: bool = False) -> str:
    """
    将 Excel 中的多个 sheet 转换为 markdown 格式的文本并保存到文件
    :param excel_path: Excel 文件路径
    :param include_sheet_names: 是否包含工作表名称
    :return: markdown 文件的磁盘路径
    """
    import pandas as pd
    try:
        # 确保输出目录存在
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 获取原文件名（不含扩展名）并生成 markdown 文件名
        excel_file = Path(excel_path)
        md_filename = excel_file.stem + ".md"
        md_path = os.path.join(OUTPUT_DIR, md_filename)

        # 读取所有工作表
        excel_file_obj = pd.ExcelFile(excel_path)
        markdown_parts = []

        for sheet_name in excel_file_obj.sheet_names:
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

        # 将内容写入文件
        markdown_content = "\n".join(markdown_parts)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        abs_path = os.path.abspath(md_path)
        logger.info(f"成功转换 Excel 文件: {excel_path} -> {abs_path}, 包含 {len(excel_file_obj.sheet_names)} 个工作表")
        if output_abs_path:
            return abs_path
        else:
            return md_path

    except Exception as e:
        logger.error(f"excel_to_md_error, file {excel_path}, {str(e)}")
        return ""


# 使用示例
if __name__ == "__main__":
    my_excel_file = "/home/rd/Downloads/1.xlsx"  # 替换为你的 Excel 文件路径
    md_file_path = convert_xlsx_to_md(my_excel_file)
    if md_file_path:
        logger.info(f"Markdown文件已保存到: {md_file_path}")

        # 可选：读取并显示部分内容
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"文件前500字符预览:\n{content[:500]}...")
    else:
        logger.info("转换失败")