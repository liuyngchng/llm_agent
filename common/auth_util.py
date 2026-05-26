#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
通用认证工具函数
"""
import re
import logging.config
import os

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

auth_info = {}


def get_client_ip():
    """获取客户端真实 IP，并清理潜在恶意输入"""
    from flask import request

    x_forwarded_for = request.headers.get('X-Forwarded-For', '')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr

    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'

    if ip in ['127.0.0.1', 'localhost', '::1']:
        return ip

    if re.match(ipv4_pattern, ip):
        parts = ip.split('.')
        if all(0 <= int(part) <= 255 for part in parts):
            return ip

    if re.match(ipv6_pattern, ip):
        return ip
    waring_info = f"invalid_IP_format_detected: {repr(ip)[:50]}"
    print(waring_info)
    logger.warning(waring_info)
    return "INVALID_IP"


def get_portal_login_url(app_source, warning_info=None):
    """生成 portal 统一登录页面的 URL"""
    from common.const import PORTAL_BASE_URL
    from urllib.parse import urlencode
    params = {'app_source': app_source}
    if warning_info:
        params['warning_info'] = warning_info
    return f"{PORTAL_BASE_URL}/login?{urlencode(params)}"


def redirect_to_portal_login(app_source, warning_info=None):
    """跳转到 portal 统一登录页面"""
    from flask import redirect
    return redirect(get_portal_login_url(app_source, warning_info))
