#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import os
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

def init_yml_cfg(cfg_file="cfg.yml")-> dict[str, any]:
    """
    yaml cfg.yml, you can copy cfg.yml.template and rewrite to your own cfg.yml
    """
    if not os.path.exists(cfg_file):
        raise FileNotFoundError(f"配置文件不存在: {cfg_file},请根据根目录下的 {cfg_file}.template 设置环境配置信息，完成后将文件重命名为 {cfg_file}")
    # 读取配置
    _my_cfg = {}
    with open(cfg_file, 'r', encoding='utf-8') as f:
        _my_cfg = yaml.safe_load(f)
    return _my_cfg


if __name__ == "__main__":
    my_cfg = init_yml_cfg()

    logger.info(f"cfg {my_cfg}")