#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
用户权限认证 HTTP 服务
"""
import os
import time
import markdown
import logging.config
from flask import Blueprint, jsonify, redirect, url_for, current_app
from flask import (request, render_template)
from common import cfg_util as cfg_utl, statistic_util
from common import my_enums
from common.html_util import get_html_ctx_from_md
from common.sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.dirname(current_dir)
template_folder = os.path.join(common_dir, 'common', 'templates')
auth_bp = Blueprint('auth', __name__,
                   template_folder=template_folder)
auth_info = {}
my_cfg = init_yml_cfg()

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours

@auth_bp.route('/login', methods=['GET'])
def login_index():
    # logger.info("login_index")
    app_source = request.args.get('app_source', current_app.config.get('APP_SOURCE'))
    warning_info = request.args.get('warning_info', "")
    if not app_source:
        raise RuntimeError("no_app_info_found")
    sys_name = my_enums.AppType.get_app_type(app_source)
    ctx = {
        "uid": -1,
        "sys_name": sys_name,
        "app_source": app_source,
        "warning_info": warning_info,
    }
    auth_flag = my_cfg['sys']['auth']
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
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    logger.debug(f"request_form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    app_source = request.form.get('app_source')
    logger.info(f"user_login: {user}, {t}, {app_source}, IP={get_client_ip()}")
    auth_result = cfg_utl.auth_user(user, t, my_cfg)
    logger.info(f"user_login_result: {user}, {t}, {auth_result}")
    sys_name = my_enums.AppType.get_app_type(app_source)
    if not auth_result["pass"]:
        logger.error(f"用户认证失败 {user}, {t}")
        warning_info=auth_result['msg']
        return redirect(url_for('auth.login_index', app_source=app_source, warning_info=warning_info, usr=user))
    dt_idx = f"{app_source}_index.html"

    logger.info(f"return_page {dt_idx}")
    uid = auth_result["uid"]
    statistic_util.add_access_count_by_uid(uid, 1)
    if auth_result["role"] == 2:
        hack_admin = "1"
    else:
        hack_admin = "0"
    greeting = "欢迎使用本系统"
    cfg_greeting = cfg_utl.get_const("greeting", app_source)
    if cfg_greeting:
        greeting = cfg_greeting

    ctx = {
        "uid": uid,
        "usr": user,
        "role": auth_result["role"],
        "t": auth_result["t"],
        "sys_name": sys_name,
        "greeting": greeting,
        "app_source": app_source,
        "hack_admin": hack_admin,
    }
    session_key = f"{auth_result['uid']}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)


@auth_bp.route('/logout', methods=['GET'])
def logout():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "login.html"
    logger.debug(f"request_form: {request.args}")
    uid = request.args.get('uid').strip()
    app_source = request.args.get('app_source')
    sys_name = my_enums.AppType.get_app_type(app_source)
    logger.info(f"user_logout, {uid}, {app_source}")
    session_key = f"{uid}_{get_client_ip()}"
    auth_info.pop(session_key, None)
    usr_info = cfg_utl.get_user_info_by_uid(int(uid))
    usr_name = usr_info.get('name', '')
    return redirect(url_for('auth.login_index',
                           app_source=app_source,
                           warning_info=f"用户 {usr_name} 已退出"))

@auth_bp.route('/reg/usr', methods=['GET'])
def reg_user_index():
    """
     A index for reg user
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_reg_usr_index {request.args}")
    app_source = request.args.get('app_source')
    sys_name = my_enums.AppType.get_app_type(app_source)
    ctx = {
        "sys_name": sys_name + "_新用户注册",
        "warning_info":"",
        "app_source": app_source,
    }
    dt_idx = "reg_usr_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@auth_bp.route('/reg/usr', methods=['POST'])
def reg_user():
    """
     A index for reg user
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    dt_idx = "reg_usr_index.html"
    logger.info(f"reg_user_req, {request.form}, from_IP {get_client_ip()}")
    ctx = {
        "sys_name": my_cfg['sys']['name']+ "_新用户注册",
        "user": "",
        "warning_info": "",
        "app_source": request.form.get('app_source')
    }
    try:
        usr = request.form.get('usr').strip()
        ctx["user"] = usr
        sys_name = my_enums.AppType.get_app_type(ctx["app_source"])
        ctx["sys_name"] = sys_name
        t = request.form.get('t').strip()
        if not usr:
            ctx["warning_info"] = "用户名不能为空"
            logger.error("reg_user_empty_username")
            return render_template(dt_idx, **ctx)
        if not t:
            ctx["warning_info"] = "密码不能为空"
            logger.error("reg_user_empty_password")
            return render_template(dt_idx, **ctx)
        usr_info = cfg_utl.get_uid_by_user(usr)
        if usr_info:
            ctx["warning_info"]= f"用户 {usr} 已存在，请重新输入用户名"
            logger.error(f"reg_user_exist_err {usr}")
            return render_template(dt_idx, **ctx)
        cfg_utl.save_usr(usr, t)
        uid = cfg_utl.get_uid_by_user(usr)
        if uid:
            ctx["uid"] = uid
            ctx["sys_name"] = sys_name
            ctx["warning_info"] = f"用户 {usr} 已成功创建，欢迎使用本系统"
            dt_idx = "login.html"
            logger.error(f"reg_user_success, {usr}")
            return render_template(dt_idx, **ctx)
        else:
            ctx["warning_info"] = f"用户 {usr} 创建失败"
            logger.error(f"reg_user_fail, {usr}")
            return render_template(dt_idx, **ctx)
    except Exception as e:
        ctx["warning_info"] = "系统异常，创建用户失败"
        logger.error(f"reg_user_exception, {ctx['warning_info']}, url: {request.url}", exc_info=True)
        logger.info(f"return_page {dt_idx}, ctx {ctx}")
        return render_template(dt_idx, **ctx)

@auth_bp.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' \
        -H "Content-Type: application/json" \
        -d '{"msg":"who are you?"}'
    :return:
    """
    logger.info("health_check")
    return jsonify({"status": 200}), 200
    # return Response({"status":200}, content_type=content_type, status=200)

@auth_bp.route('/usr/mnl', methods=['GET'])
def get_usr_manual():
    """
    get user manual
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
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





def get_client_ip():
    """获取客户端真实 IP"""
    # 如果有X-Forwarded-For，取第一个IP（因为可能是代理链）
    x_forwarded_for = request.headers.get('X-Forwarded-For', '')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip
