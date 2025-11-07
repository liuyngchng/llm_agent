#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def change_list(my_list: list):
    my_list.append("append_txt_in_change_list")

def change_txt(source: str):
    source += "append_txt_in_change_txt"


if __name__ =="__main__":
    answer = "origin_txt"
    change_txt(answer)
    logger.info(f"changed_txt:{answer}")
    my_list = ["origin_item"]
    change_list(my_list)
    logger.info(f"changed_list:{my_list}")