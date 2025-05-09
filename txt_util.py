#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def get_txt_in_dir_by_keywords(keywords: str, dir_path: str, word_count = 500) -> str:
    logger.info(f"get_txt_by_keywords({keywords}, {dir_path})")
    result = ""
    for filename in os.listdir(dir_path):
        if not filename.endswith('.txt'):
            continue
        file_full_path = os.path.join(dir_path, filename)
        file_result = get_txt_in_file_by_keywords(keywords, file_full_path, word_count)
        if "" != file_result:
            result += f"\n\n[{file_full_path}]\n{file_result}"
    logger.info(f"get_txt_in_dir_by_keywords_return, [{result}]")
    return result


def get_txt_in_file_by_keywords(keywords: str, file_name: str, word_count: int) -> str:
    with open(file_name, 'r', encoding='utf-8') as f:
        lines = [line for line in f if line.strip()]
        full_text = ''.join(lines)
        result = []
        for raw_line in lines:
            clean_line = strip_prefix_no(raw_line)
            if keywords == clean_line:
                pos = full_text.find(raw_line)
                result.append(full_text[pos: pos + len(raw_line) + word_count])
        return '\n'.join(result).strip()

def strip_prefix_no(txt: str) -> str:
    return re.sub(r'^\d+(\.\d+)*\s*', '', txt.strip())


if __name__ == "__main__":
    txt = "2.1.2.2数据管理现状分析"
    print(strip_prefix_no(txt))