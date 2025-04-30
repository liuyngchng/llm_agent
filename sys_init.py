#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import os
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def init_yml_cfg(cfg_file="config.yml")-> dict[str, any]:
    """
    yaml config.yml txt_file content as following
    database:
      name: ***
      user: **
      password: **

    ai:
      api_uri: **
      api_key: **
      model_name: **
      prompts:
        sql_gen_sys_msg: |
          你是一个专业的SQL生成助手。已知数据库结构：
          {schema}

          请严格按以下要求生成SQL：
          (1) 仅输出标准SQL代码块，不要任何解释
          (2) ***
        nl_gen_sys_msg: |
          你是一个专业的数据解读助手。已知 Markdown格式的数据清单：
          {markdown_dt}

          (1)请输出对数据的简洁解读，以及可以渲染为表格的原始数据
    """
    if not os.path.exists(cfg_file):
        raise FileNotFoundError(f"配置文件不存在: {cfg_file}")
    # 读取配置
    _my_cfg = {}
    with open(cfg_file, 'r', encoding='utf-8') as f:
        _my_cfg = yaml.safe_load(f)
    return _my_cfg


if __name__ == "__main__":
    my_cfg = init_yml_cfg()

    logger.info(f"cfg {my_cfg}")