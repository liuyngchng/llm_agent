#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import os
import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

def init_txt_cfg(cfg_file="env.cfg")-> dict[str, str] | None:
    """
    env.cfg 中， 各行参数如下
    [1] api_uri
    [2] api_key
    [3] model_name
    [4] db_uri
    """
    # global api_uri, api_key, model_name
    _my_cfg = {"api_uri":"http://127.0.0.1:11434", "api_key":"", "model_name":"deepseek-r1"}
    if not os.path.exists(cfg_file):
        raise FileNotFoundError(f"配置文件不存在: {cfg_file}")
    with open(cfg_file) as f:
        lines = f.readlines()
    if len(lines) < 2:
        logger.error("cfg_err_in_file_{}".format(cfg_file))
        return _my_cfg
    try:
        _my_cfg["api_uri"] = lines[0].strip()
        _my_cfg["api_key"] = lines[1].strip()
        _my_cfg["model_name"] = lines[2].strip()
        _my_cfg["db_uri"]= lines[3].strip()
        logger.info(f"init_cfg_info, {_my_cfg}")
    except Exception as e:
        logger.error(f"init_cfg_error: {e}")
        raise e
    return _my_cfg

def init_yml_cfg(cfg_file="config.yml")-> dict[str, str]:
    """
    yaml config.yml file content as following
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
    with open(cfg_file) as f:
        _my_cfg = yaml.safe_load(f)
    return _my_cfg


if __name__ == "__main__":
    my_cfg = init_yml_cfg()

    logger.info(f"cfg {my_cfg}")