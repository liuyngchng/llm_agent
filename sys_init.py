#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

def init_cfg(cfg_file="env.cfg")-> dict[str, str] | None:
    """
    env.cfg 中， 各行参数如下
    [1] api_uri
    [2] api_key
    [3] model_name
    [4] db_uri
    """
    # global api_uri, api_key, model_name
    _my_cfg = {"api_uri":"http://127.0.0.1:11434", "api_key":"", "model_name":"deepseek-r1"}
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