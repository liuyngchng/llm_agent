#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
数据统计客户端 — 调用 statistics_service HTTP API
"""

import logging.config
import os

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


def _get_stats_api_base() -> str:
    """获取 statistics_service 的 API 基础地址"""
    try:
        from flask import current_app
        cfg = current_app.config.get('CFG')
    except RuntimeError:
        from common.sys_init import init_yml_cfg
        cfg = init_yml_cfg()
    return cfg['api']['stats_api'].rstrip('/')


def _post(endpoint: str, body: dict) -> bool:
    """通用 POST 请求"""
    try:
        url = f"{_get_stats_api_base()}{endpoint}"
        resp = requests.post(url, json=body, timeout=10, verify=False)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"stats_api_post_failed, endpoint={endpoint}, err={e}")
        return False


def _get(endpoint: str) -> list | dict | None:
    """通用 GET 请求"""
    try:
        url = f"{_get_stats_api_base()}{endpoint}"
        resp = requests.get(url, timeout=10, verify=False)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"stats_api_get_failed, endpoint={endpoint}, err={e}")
    return None


def get_statistics_list() -> list[dict] | None:
    """获取用户的统计数据清单，服务不可用时返回 None"""
    result = _get("/statistics/list")
    return result


def get_statistics_by_uid(uid: int) -> dict | None:
    """获取用户的统计数据"""
    return _get(f"/statistics/user/{uid}")


def get_access_count_by_uid(uid: int) -> int:
    """统计一个用户的累计访问次数（当天）"""
    info = _get(f"/statistics/user/{uid}")
    if info and info.get('uid') == uid:
        return info.get('access_count', 0)
    return -1


def add_access_count_by_uid(uid: int, access_count: int, app_name: str = "") -> bool:
    """
    更新用户的访问次数
    """
    body = {"uid": uid, "count": access_count, "app":""}
    if app_name:
        body["app"] = app_name
    return _post("/statistics/access", body)


def get_input_token_by_uid(uid: int) -> int | None:
    """获取用户当天输入 Token 用量"""
    info = _get(f"/statistics/user/{uid}")
    if info and info.get('uid') == uid:
        return info.get('input_token', 0)
    return -1


def add_input_token_by_uid(uid: int, input_token: int, app_name: str = "") -> bool:
    """更新用户输入 Token 用量"""
    body = {"uid": uid, "count": input_token, "app":""}
    if app_name:
        body["app"] = app_name
    return _post("/statistics/input-token", body)


def get_embedding_token_by_uid(uid: int) -> int | None:
    """获取用户当天嵌入 Token 用量"""
    info = _get(f"/statistics/user/{uid}")
    if info and info.get('uid') == uid:
        return info.get('embedding_token', 0)
    return -1


def add_embedding_token_by_uid(uid: int, embedding_token: int, app_name: str = "") -> bool:
    """更新用户嵌入 Token 用量"""
    body = {"uid": uid, "count": embedding_token, "app":""}
    if app_name:
        body["app"] = app_name
    return _post("/statistics/embedding-token", body)


def get_output_token_by_uid(uid: int) -> int | None:
    """获取用户当天输出 Token 用量"""
    info = _get(f"/statistics/user/{uid}")
    if info and info.get('uid') == uid:
        return info.get('output_token', 0)
    return -1


def add_output_token_by_uid(uid: int, output_token: int, app_name: str = "") -> bool:
    """更新用户输出 Token 用量"""
    body = {"uid": uid, "count": output_token, "app":""}
    if app_name:
        body["app"] = app_name
    return _post("/statistics/output-token", body)
