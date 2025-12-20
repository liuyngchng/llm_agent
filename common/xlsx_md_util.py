#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import os
from pathlib import Path


from common.const import OUTPUT_DIR

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


def convert_xlsx_to_md(excel_path: str, include_sheet_names: bool = True,
                       output_abs_path: bool = False) -> str:
    """
    高级版本：将Excel转换为更易读的Markdown格式
    """
    import pandas as pd
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        excel_file = Path(excel_path)
        md_filename = excel_file.stem + ".md"
        md_path = os.path.join(OUTPUT_DIR, md_filename)

        excel_file_obj = pd.ExcelFile(excel_path)
        markdown_parts = []

        for sheet_name in excel_file_obj.sheet_names:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine='openpyxl')

            if include_sheet_names:
                markdown_parts.append(f"## 📊 工作表: {sheet_name}")
                markdown_parts.append("")

            if not df.empty:
                df = df.fillna('')
                df = df.replace(r'^Unnamed.*$', '', regex=True)
                df.columns = ['' if 'Unnamed' in str(col) else col
                              for i, col in enumerate(df.columns)]
                df = df.replace(r'\n', '<br>', regex=True)

                # 检查数据维度
                if df.shape[1] <= 3:  # 列数较少时使用更好的格式
                    markdown_parts.extend(dataframe_to_readable_list(df, sheet_name))
                else:
                    # markdown_parts.append("> ⚠️ **表格预览** (复杂表格建议查看原文件)")
                    markdown_parts.append("")
                    markdown_table = df.to_markdown(index=False, tablefmt="pipe")
                    markdown_parts.append(markdown_table)

                markdown_parts.append("")  # 空行分隔

        markdown_content = "\n".join(markdown_parts)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        abs_path = os.path.abspath(md_path)
        logger.info(f"成功转换 Excel 文件: {excel_path} -> {abs_path}")
        return abs_path if output_abs_path else md_path

    except Exception as e:
        logger.exception(f"excel_to_md_error, file {excel_path}, {str(e)}")
        return ""


def dataframe_to_readable_list(df, sheet_name):
    """将DataFrame转换为更易读的列表格式"""
    import pandas as pd
    lines = [f"### {sheet_name} 数据", ""]
    headers = df.columns.tolist()
    for index, row in df.iterrows():
        lines.append(f"**记录 {index + 1}:**")
        for header, value in zip(headers, row):
            if pd.notna(value) and str(value).strip():
                lines.append(f"- **{header}**: {value}")
        lines.append("")

    return lines

# 使用示例
if __name__ == "__main__":
    my_excel_file = "/home/rd/Downloads/2.xlsx"  # 替换为你的 Excel 文件路径
    md_file_path = convert_xlsx_to_md(my_excel_file, True)
    if md_file_path:
        logger.info(f"Markdown文件已保存到: {md_file_path}")

        # 可选：读取并显示部分内容
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"文件前500字符预览:\n{content[:500]}...")
    else:
        logger.info("转换失败")