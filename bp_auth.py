#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify
import logging.config
from flask import (request, render_template)
import time
import cfg_util as cfg_utl
from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)
auth_info = {}
my_cfg = init_yml_cfg()

@auth_bp.route('/login', methods=['GET'])
def login_index():
    logger.info("login_index")
    app_source = request.args.get('app_source')
    if not app_source:
        raise RuntimeError("no_app_info_found")
    ctx = {
        "uid": "foo",
        "sys_name": my_cfg['sys']['name'],
        "app_source": app_source,
        "waring_info": "",
    }
    auth_flag = my_cfg['sys']['auth']
    if auth_flag:
        login_idx = "login.html"
        logger.info(f"return page {login_idx} for app_source {app_source}")
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
    logger.info(f"user_login: {user}, {t}, {app_source}")
    auth_result = cfg_utl.auth_user(user, t, my_cfg)
    logger.info(f"user_login_result: {user}, {t}, {auth_result}")
    if not auth_result["pass"]:
        logger.error(f"用户名或密码输入错误 {user}, {t}")
        ctx = {
            "user" : user,
            "sys_name" : my_cfg['sys']['name'],
            "waring_info" : "用户名或密码输入错误",
        }
        return render_template("login.html", **ctx)
    dt_idx = f"{app_source}_index.html"
    logger.info(f"return_page {dt_idx}")
    ctx = {
        "uid": auth_result["uid"],
        "t": auth_result["t"],
        "sys_name": my_cfg['sys']['name'],
        "greeting": cfg_utl.get_const("greeting", app_source),
        "app_source": app_source,
    }
    session_key = f"{auth_result['uid']}_{get_client_ip()}"
    auth_info[session_key] = time.time()
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
    logger.info(f"user_logout, {uid}, {app_source}")
    session_key = f"{uid}_{get_client_ip()}"
    auth_info.pop(session_key, None)
    usr_info = cfg_utl.get_user_info_by_uid(uid)
    usr_name = usr_info.get('name', '')
    ctx = {
        "user": usr_name,
        "sys_name": my_cfg['sys']['name'],
        "waring_info":f"用户 {usr_name} 已退出",
        "app_source": app_source,
    }
    return render_template(dt_idx, **ctx)

@auth_bp.route('/reg/usr', methods=['GET'])
def reg_user_index():
    """
     A index for reg user
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_reg_usr_index {request.args}")
    app_source = request.args.get('app_source')
    ctx = {
        "sys_name": my_cfg['sys']['name'] + "_新用户注册",
        "waring_info":"",
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
    logger.info(f"reg_user_req, {request.form}, from_IP {get_client_ip()}")
    ctx = {
        "sys_name": my_cfg['sys']['name']+ "_新用户注册"
    }
    try:
        usr = request.form.get('usr').strip()
        ctx["user"] = usr
        ctx["app_source"] = request.form.get('app_source')
        t = request.form.get('t').strip()
        usr_info = cfg_utl.get_uid_by_user(usr)
        if usr_info:
            ctx["waring_info"]= f"用户 {usr} 已存在，请重新输入用户名"
            logger.error(f"reg_user_exist_err {usr}")
        else:
            cfg_utl.save_usr(usr, t)
            uid = cfg_utl.get_uid_by_user(usr)
            if uid:
                ctx["uid"] = uid
                ctx["sys_name"] = my_cfg['sys']['name']
                ctx["waring_info"] = f"用户 {usr} 已成功创建，欢迎使用本系统"
                dt_idx = "login.html"
                logger.error(f"reg_user_success, {usr}")
                return render_template(dt_idx, **ctx)
            else:
                ctx["waring_info"] = f"用户 {usr} 创建失败"
                logger.error(f"reg_user_fail, {usr}")
    except Exception as e:
        ctx["waring_info"] = "创建用户发生异常"
        logger.error(f"reg_user_exception, {ctx['waring_info']}, url: {request.url}", exc_info=True)
    dt_idx = "reg_usr_index.html"
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


def get_client_ip():
    """获取客户端真实 IP"""
    if forwarded_for := request.headers.get('X-Forwarded-For'):
        return forwarded_for.split(',')[0]
    return request.headers.get('X-Real-IP', request.remote_addr)