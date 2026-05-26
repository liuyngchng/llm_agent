#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
用户权限认证 HTTP 服务 (代理到 auth_service API)
"""
import json
import os
import re
import time
import logging.config

import requests
from flask import Blueprint, jsonify, redirect, url_for, current_app, make_response
from flask import (request, render_template)
from common import statistic_util
from common import my_enums
from common.const import SESSION_TIMEOUT
from common.html_util import get_html_ctx_from_md
from common.auth_util import auth_info, get_client_ip, get_portal_login_url, redirect_to_portal_login


log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.dirname(current_dir)
template_folder = os.path.join(common_dir, 'common', 'templates')
auth_bp = Blueprint('auth', __name__,template_folder=template_folder)


def _auth_api_base():
    """从配置获取 auth_service 的 API 基础地址"""
    cfg = get_cfg()
    auth_api = cfg.get('api', {}).get('auth_api', '')
    if not auth_api:
        raise RuntimeError(
            "配置缺失: cfg.yml 中未设置 api.auth_api，"
            "请参考 cfg.yml.template 添加 auth_service 的 API 地址"
        )
    return auth_api.rstrip('/')


@auth_bp.route('/captcha/generate', methods=['GET'])
def generate_captcha():
    """生成图形验证码（代理到 auth_service）"""
    try:
        url = f"{_auth_api_base()}/auth/captcha/generate"
        logger.debug(f"GET {url}")
        resp = requests.get(url, timeout=10)
        logger.debug(f"response status={resp.status_code}, body={resp.text[:200]}")
        resp.raise_for_status()
        return jsonify(resp.json())
    except RuntimeError as e:
        logger.error(f"配置错误: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    except requests.RequestException as e:
        logger.error(f"生成图形验证码失败: {e}", exc_info=True)
        return jsonify({"success": False, "message": "生成验证码失败"}), 500


@auth_bp.route('/captcha/image/<captcha_token>', methods=['GET'])
def get_captcha_image(captcha_token):
    """获取验证码图片（代理到 auth_service）"""
    try:
        url = f"{_auth_api_base()}/auth/captcha/image/{captcha_token}"
        logger.debug(f"GET {url}")
        resp = requests.get(url, timeout=10)
        logger.debug(f"response status={resp.status_code}, content_type={resp.headers.get('Content-Type', 'N/A')}")
        if resp.status_code == 404:
            return jsonify({"success": False, "message": "验证码不存在或已过期"}), 404
        resp.raise_for_status()
        response = make_response(resp.content)
        response.headers['Content-Type'] = resp.headers.get('Content-Type', 'image/svg+xml')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except RuntimeError as e:
        logger.error(f"配置错误: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    except requests.RequestException as e:
        logger.error(f"获取验证码图片失败: {e}", exc_info=True)
        return jsonify({"success": False, "message": "获取验证码失败"}), 500


@auth_bp.route('/login', methods=['GET'])
def login_index(app_source=None, app_base_uri=None, warning_info=None):
    # logger.info("login_index")
    if not app_source:
        app_source = request.args.get('app_source', current_app.config.get('APP_SOURCE'))
    if not app_base_uri:
        app_base_uri = request.args.get('app_base_uri','')
    if not warning_info:
        warning_info = request.args.get('warning_info', "")
    if not app_source:
        raise RuntimeError("no_app_info_found")
    sys_name = my_enums.AppType.get_app_type(app_source)

    captcha_token = ""
    try:
        url = f"{_auth_api_base()}/auth/captcha/generate"
        logger.debug(f"GET {url}")
        resp = requests.get(url, timeout=10)
        logger.debug(f"response status={resp.status_code}, body={resp.text[:200]}")
        resp.raise_for_status()
        captcha_token = resp.json().get("captcha_token", "")
    except RuntimeError as e:
        logger.error(f"配置错误: {e}")
        warning_info = str(e)
    except requests.RequestException as e:
        logger.error(f"获取验证码 token 失败: {e}")

    ctx = {
        "uid": -1,
        "sys_name": sys_name,
        "app_source": app_source,
        "app_base_uri": app_base_uri,
        "warning_info": warning_info,
        "captcha_token": captcha_token,
    }
    auth_flag = get_cfg()['sys']['auth']
    if auth_flag:
        login_idx = "login.html"
        # logger.info(f"return_page_for_app_source {app_source}, {login_idx}")
        return render_template(login_idx, **ctx)
    else:
        dt_idx = f"{app_source}_index.html"
        logger.info(f"return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, **ctx)

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    form submit, get data from form
    """
    logger.debug(f"request_form: {request.form}")
    user = request.form.get('usr', '').strip()
    t = request.form.get('t', '').strip()
    app_source = request.form.get('app_source', '').strip()
    app_base_uri = request.form.get('app_base_uri', '').strip()
    captcha_code = request.form.get('captcha_code', '').strip()
    captcha_token = request.form.get('captcha_token', '').strip()

    logger.info(f"user_login: {user}, IP={get_client_ip()}")

    try:
        url = f"{_auth_api_base()}/auth/login"
        params = {"usr": user, "t": t, "captcha_code": captcha_code, "captcha_token": captcha_token}
        safe_params = {**params, "t": "***"}
        logger.debug(f"POST {url}, params {safe_params}")
        resp = requests.post(url, json=params, timeout=10)
        logger.debug(f"response status={resp.status_code}, body={resp.text[:200]}")
    except RuntimeError as e:
        logger.error(f"配置错误: {e}")
        return redirect(url_for('auth.login_index',
                                app_source=app_source,
                                app_base_uri=app_base_uri,
                                warning_info=str(e),
                                usr=user))
    except requests.RequestException as e:
        logger.error(f"auth_service 调用失败: {e}")
        return redirect(url_for('auth.login_index',
                                app_source=app_source,
                                app_base_uri=app_base_uri,
                                warning_info="认证服务暂时不可用，请稍后重试",
                                usr=user))

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", "登录失败")
        except Exception:
            detail = "登录失败"
        logger.error(f"用户认证失败 {user}: {detail}")
        return redirect(url_for('auth.login_index',
                                app_source=app_source,
                                app_base_uri=app_base_uri,
                                warning_info=detail,
                                usr=user))
    result = resp.json()
    uid = result["uid"]
    access_token = result["access_token"]

    logger.info(f"login_success, uid={uid}, app_source={app_source}")
    session_key = f"{uid}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    return redirect(f"/?t={access_token}")


@auth_bp.route('/logout', methods=['GET'])
def logout():
    """
    form submit, get data from form
    """
    dt_idx = "login.html"
    logger.debug(f"request_form: {request.args}")
    uid = request.args.get('uid')
    app_source = request.args.get('app_source')
    sys_name = my_enums.AppType.get_app_type(app_source)
    logger.info(f"user_logout, {uid}, {app_source}")
    session_key = f"{uid}_{get_client_ip()}"
    auth_info.pop(session_key, None)
    return redirect(url_for('auth.login_index',
                            app_source=app_source,
                            warning_info="用户已退出"))

@auth_bp.route('/reg/usr', methods=['GET'])
def reg_user_index():
    """
     A index for reg user
    """
    logger.info(f"request_args_in_reg_usr_index {request.args}")
    app_source = request.args.get('app_source')
    sys_name = my_enums.AppType.get_app_type(app_source)

    captcha_token = ""
    try:
        url = f"{_auth_api_base()}/auth/captcha/generate"
        logger.debug(f"GET {url}")
        resp = requests.get(url, timeout=10)
        logger.debug(f"response status={resp.status_code}, body={resp.text[:200]}")
        resp.raise_for_status()
        captcha_token = resp.json().get("captcha_token", "")
    except RuntimeError as e:
        logger.error(f"配置错误: {e}")
        ctx = {
            "sys_name": sys_name + "_新用户注册",
            "warning_info": str(e),
            "app_source": app_source,
            "captcha_token": "",
        }
        return render_template("reg_usr_index.html", **ctx)
    except requests.RequestException as e:
        logger.error(f"获取验证码 token 失败: {e}")

    ctx = {
        "sys_name": sys_name + "_新用户注册",
        "warning_info": "",
        "app_source": app_source,
        "captcha_token": captcha_token,
    }
    dt_idx = "reg_usr_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@auth_bp.route('/reg/usr', methods=['POST'])
def reg_user():
    """
     A index for reg user
    """
    dt_idx = "reg_usr_index.html"
    logger.info(f"reg_user_req, {request.form}, from_IP {get_client_ip()}")

    captcha_code = request.form.get('captcha_code', '').strip()
    captcha_token = request.form.get('captcha_token', '').strip()
    app_source = request.form.get('app_source')
    usr = request.form.get('usr', '').strip()
    t = request.form.get('t', '').strip()

    sys_name = my_enums.AppType.get_app_type(app_source)
    ctx = {
        "sys_name": sys_name + "_新用户注册",
        "user": usr,
        "warning_info": "",
        "app_source": app_source,
        "captcha_token": captcha_token,
    }

    if not usr:
        ctx["warning_info"] = "用户名不能为空"
        logger.error("reg_user_empty_username")
        return render_template(dt_idx, **ctx)
    if not t:
        ctx["warning_info"] = "密码不能为空"
        logger.error("reg_user_empty_password")
        return render_template(dt_idx, **ctx)
    try:
        url = f"{_auth_api_base()}/auth/register"
        params = {"usr": usr, "t": t, "captcha_code": captcha_code, "captcha_token": captcha_token}
        safe_params = {**params, "t": "***"}
        logger.debug(f"POST {url}, params {safe_params}")
        resp = requests.post(url, json=params, timeout=10)
        logger.debug(f"response status={resp.status_code}, body={resp.text[:200]}")
    except RuntimeError as e:
        logger.error(f"配置错误: {e}")
        ctx["warning_info"] = str(e)
        return render_template(dt_idx, **ctx)
    except requests.RequestException as e:
        logger.error(f"auth_service 调用失败: {e}")
        ctx["warning_info"] = "认证服务暂时不可用，请稍后重试"
        return render_template(dt_idx, **ctx)

    if resp.status_code == 200:
        result = resp.json()
        uid = result["uid"]
        ctx["uid"] = uid
        ctx["sys_name"] = sys_name
        ctx["warning_info"] = f"用户 {usr} 已成功创建，欢迎使用本系统"
        dt_idx = "login.html"
        logger.info(f"reg_user_success, {usr}")
        return render_template(dt_idx, **ctx)
    else:
        try:
            detail = resp.json().get("detail", "用户创建失败")
        except Exception:
            detail = "用户创建失败"
        ctx["warning_info"] = detail
        ctx["captcha_token"] = captcha_token
        logger.error(f"reg_user_fail, {usr}: {detail}")
        return render_template(dt_idx, **ctx)

@auth_bp.route('/usr/statistic/index', methods=['GET'])
def get_statistic_report_index():
    """
    获取系统运营的页面
    """
    logger.info(f"get_statistic_report_index, {request.args}")
    uid = request.args.get('uid')
    app_source = request.args.get('app_source')
    session_key = f"{uid}_{get_client_ip()}"
    if (not auth_info.get(session_key, None)
            or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
        warning_info = "用户会话信息已失效，请重新登录"
        logger.warning(f"{uid}, {warning_info}")
        return redirect(url_for(
            'auth.login_index',
            app_source=app_source,
            warning_info=warning_info

        ))
    app_source = request.args.get('app_source')
    warning_info = request.args.get('warning_info', "")
    sys_name = my_enums.AppType.get_app_type(app_source)
    ctx = {
        "uid": uid,
        "sys_name": sys_name,
        "app_source": app_source,
        "warning_info": warning_info,
    }
    dt_idx = "statistics.html"
    logger.info(f"{uid}, return_page_with_no_auth {dt_idx}")
    return render_template(dt_idx, **ctx)

@auth_bp.route('/usr/statistic/report', methods=['POST'])
def get_statistic_report():
    """
    统计用户的系统使用数据
    """
    data = request.json
    uid = int(data.get('uid'))
    app_source = data.get('app_source')
    logger.info(f"{uid}, get_statistic_report, {data}")
    session_key = f"{uid}_{get_client_ip()}"
    if (not auth_info.get(session_key, None)
            or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
        warning_info = "用户会话信息已失效，请重新登录"
        logger.warning(f"{uid}, {warning_info}")
        return redirect(url_for(
            'auth.login_index',
            app_source=app_source,
            warning_info=warning_info

        ))
    statistics_list = statistic_util.get_statistics_list()
    if statistics_list is None:
        return json.dumps({"error": "数据统计服务异常，请稍后重试"}, ensure_ascii=False), 503
    return json.dumps(statistics_list, ensure_ascii=False), 200

@auth_bp.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    """
    logger.info("health_check")
    return jsonify({"status": 200}), 200

@auth_bp.route('/usr/mnl', methods=['GET'])
def get_usr_manual():
    """
    get user manual
    """
    logger.debug(f"request_args_in_get_usr_manual {request.args}")
    app_source = request.args.get('app_source')
    sys_name = my_enums.AppType.get_app_type(app_source)
    markdown_content = ""
    markdown_file_name = f"./user_manual/{app_source}_user_manual.md"
    abs_path = os.path.abspath(markdown_file_name)
    if not os.path.exists(abs_path):
        markdown_file_name = f"./apps/{app_source}/" + markdown_file_name
        abs_path = os.path.abspath(markdown_file_name)
    else:
        logger.info(f"file_exist, {abs_path}")
    html_content, toc_content = get_html_ctx_from_md(abs_path)
    ctx = {
        "sys_name": sys_name + "_用户使用说明",
        "warning_info": "",
        "app_source": app_source,
        "html_content": html_content,
        "toc_content": toc_content,
    }
    dt_idx = "md.html"
    logger.debug(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)


def get_cfg():
    """获取配置，优先从应用上下文获取，如果没有则直接初始化"""
    try:
        from flask import current_app
        cfg = current_app.config.get('CFG')
        return cfg
    except RuntimeError:
        pass
    from common.sys_init import init_yml_cfg
    return init_yml_cfg()