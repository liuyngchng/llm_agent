#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
用户权限认证 HTTP 服务
"""
import hashlib
import json
import os
import random
import re
import string
import time
import logging.config
from io import BytesIO
from flask import Blueprint, jsonify, redirect, url_for, current_app, make_response
from flask import (request, render_template)
from common import cfg_util as cfg_utl, statistic_util
from common import my_enums
from common.const import get_const, SESSION_TIMEOUT
from common.html_util import get_html_ctx_from_md
import svgwrite


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
auth_info = {}

# 图形验证码存储字典（存储验证码值和相关信息）
captcha_codes = {}


@auth_bp.route('/captcha/generate', methods=['GET'])
def generate_captcha():
    """
    生成图形验证码
    """
    try:
        # 生成4位数字验证码
        captcha_text = ''.join(random.choices(string.digits, k=4))
        # 生成唯一token
        captcha_token = hashlib.md5(f"{captcha_text}{time.time()}".encode()).hexdigest()[:16]
        # 存储验证码信息（有效期5分钟）
        captcha_codes[captcha_token] = {
            'text': captcha_text,
            'expires_at': time.time() + 300,  # 5分钟有效期
            'attempts': 0  # 尝试次数
        }

        # 清理过期的验证码
        cleanup_expired_captchas()

        logger.debug(f"生成图形验证码 - Token: {captcha_token}, 验证码: {captcha_text}")

        return jsonify({
            "success": True,
            "captcha_token": captcha_token
        })

    except Exception as e:
        logger.error(f"生成图形验证码失败: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "生成验证码失败"}), 500


@auth_bp.route('/captcha/image/<captcha_token>', methods=['GET'])
def get_captcha_image(captcha_token):
    """
    获取验证码图片
    """
    try:
        if captcha_token not in captcha_codes:
            return jsonify({"success": False, "message": "验证码不存在或已过期"}), 404

        captcha_info = captcha_codes[captcha_token]
        captcha_text = captcha_info['text']

        # 生成SVG图片
        svg_content = generate_captcha_svg(captcha_text)

        response = make_response(svg_content)
        response.headers['Content-Type'] = 'image/svg+xml'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except Exception as e:
        logger.error(f"获取验证码图片失败: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": "获取验证码失败"}), 500


@auth_bp.route('/login', methods=['GET'])
def login_index():
    # logger.info("login_index")
    app_source = request.args.get('app_source', current_app.config.get('APP_SOURCE'))
    warning_info = request.args.get('warning_info', "")
    if not app_source:
        raise RuntimeError("no_app_info_found")
    sys_name = my_enums.AppType.get_app_type(app_source)

    captcha_text = ''.join(random.choices(string.digits, k=4))
    captcha_token = hashlib.md5(f"{captcha_text}{time.time()}".encode()).hexdigest()[:16]
    captcha_codes[captcha_token] = {
        'text': captcha_text,  # 这里设置验证码文本
        'expires_at': time.time() + 300,
        'attempts': 0
    }

    ctx = {
        "uid": -1,
        "sys_name": sys_name,
        "app_source": app_source,
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
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    app_source = request.form.get('app_source')
    captcha_code = request.form.get('captcha_code', '').strip()
    captcha_token = request.form.get('captcha_token', '').strip()

    logger.info(f"user_login: {user}, IP={get_client_ip()}")

    # 先验证图形验证码
    if not verify_captcha(captcha_code, captcha_token):
        warning_info = "图形验证码错误"
        logger.warning(f"图形验证码验证失败 - 用户: {user}, 验证码: {captcha_code}")
        return redirect(url_for('auth.login_index',
                                app_source=app_source,
                                warning_info=warning_info,
                                usr=user))

    # 然后验证用户密码
    auth_result = cfg_utl.auth_user(user, t, current_app.config.get('CFG'))
    logger.info(f"user_login_result: {user}, {auth_result}")

    sys_name = my_enums.AppType.get_app_type(app_source)
    if not auth_result["pass"]:
        logger.error(f"用户认证失败 {user}")
        warning_info = auth_result['msg']
        return redirect(url_for('auth.login_index',
                                app_source=app_source,
                                warning_info=warning_info,
                                usr=user))

    dt_idx = f"{app_source}_index.html"
    logger.info(f"return_page {dt_idx}")

    # 验证成功后清理验证码
    if captcha_token in captcha_codes:
        del captcha_codes[captcha_token]

    uid = auth_result["uid"]
    statistic_util.add_access_count_by_uid(uid, 1)

    if auth_result["role"] == 2:
        hack_admin = "1"
    else:
        hack_admin = "0"

    greeting = get_const("greeting", app_source)
    arg1 = get_const("arg1", app_source)
    arg2 = get_const("arg2", app_source)
    arg3 = get_const("arg3", app_source)

    ctx = {
        "uid": uid,
        "usr": user,
        "role": auth_result["role"],
        "t": auth_result["t"],
        "sys_name": sys_name,
        "greeting": greeting,
        "app_source": app_source,
        "hack_admin": hack_admin,
        "arg1": arg1,
        "arg2": arg2,
        "arg3": arg3,
    }

    session_key = f"{auth_result['uid']}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)


@auth_bp.route('/logout', methods=['GET'])
def logout():
    """
    form submit, get data from form
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
    """
    logger.info(f"request_args_in_reg_usr_index {request.args}")
    app_source = request.args.get('app_source')
    sys_name = my_enums.AppType.get_app_type(app_source)

    captcha_text = ''.join(random.choices(string.digits, k=4))
    captcha_token = hashlib.md5(f"{captcha_text}{time.time()}".encode()).hexdigest()[:16]
    captcha_codes[captcha_token] = {
        'text': captcha_text,  # 这里设置验证码文本
        'expires_at': time.time() + 300,
        'attempts': 0
    }

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

    # 获取验证码信息
    captcha_code = request.form.get('captcha_code', '').strip()
    captcha_token = request.form.get('captcha_token', '').strip()

    ctx = {
        "sys_name": current_app.config.get('CFG')['sys']['name'] + "_新用户注册",
        "user": "",
        "warning_info": "",
        "app_source": request.form.get('app_source'),
        "captcha_token": captcha_token,
    }

    try:
        # 先验证图形验证码
        if not verify_captcha(captcha_code, captcha_token):
            ctx["warning_info"] = "图形验证码错误"
            logger.warning(f"注册页面图形验证码验证失败 - 验证码: {captcha_code}")
            return render_template(dt_idx, **ctx)

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
            ctx["warning_info"] = f"用户 {usr} 已存在，请重新输入用户名"
            logger.error(f"reg_user_exist_err {usr}")
            return render_template(dt_idx, **ctx)

        cfg_utl.save_usr(usr, t)
        uid = cfg_utl.get_uid_by_user(usr)

        if uid:
            # 注册成功后清理验证码
            if captcha_token in captcha_codes:
                del captcha_codes[captcha_token]

            ctx["uid"] = uid
            ctx["sys_name"] = sys_name
            ctx["warning_info"] = f"用户 {usr} 已成功创建，欢迎使用本系统"
            dt_idx = "login.html"
            logger.info(f"reg_user_success, {usr}")
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
    statistic_util.add_access_count_by_uid(int(uid), 1)
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


def generate_captcha_svg(captcha_text):
    """
    生成SVG格式的验证码图片
    """
    try:
        # 调整尺寸为100x44像素以匹配新样式
        width = 100
        height = 44

        # 创建SVG画布
        dwg = svgwrite.Drawing(size=(width, height))

        # 添加背景矩形
        dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill='#f8f9fa', stroke='#dee2e6', stroke_width=1))

        # 添加干扰线（减少数量以适应更小的尺寸）
        for i in range(3):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            dwg.add(dwg.line(start=(x1, y1), end=(x2, y2),
                             stroke=random.choice(['#adb5bd', '#6c757d', '#495057']),
                             stroke_width=random.uniform(0.5, 1)))

        # 添加干扰点（减少数量以适应更小的尺寸）
        for i in range(15):
            x = random.randint(0, width)
            y = random.randint(0, height)
            radius = random.uniform(0.3, 1)
            dwg.add(dwg.circle(center=(x, y), r=radius,
                               fill=random.choice(['#adb5bd', '#6c757d', '#495057'])))

        # 添加验证码文本（调整字体大小和位置）
        font_size = 20
        text_x = 5  # 减少左边距

        for i, char in enumerate(captcha_text):
            # 每个字符稍微旋转和位移（减小旋转角度）
            rotation = random.uniform(-8, 8)
            y_offset = random.uniform(-2, 2)

            # 添加字符阴影（轻微偏移）
            dwg.add(dwg.text(char, insert=(text_x + 0.5, 28 + y_offset + 0.5),
                             font_size=font_size,
                             font_family="Arial, sans-serif",
                             fill='#adb5bd',
                             font_weight="bold"))

            # 添加主字符
            dwg.add(dwg.text(char, insert=(text_x, 28 + y_offset),
                             font_size=font_size,
                             font_family="Arial, sans-serif",
                             fill='#212529',
                             font_weight="bold",
                             transform=f"rotate({rotation},{text_x},{28 + y_offset})"))

            text_x += 18  # 减少字符间距

        # 添加边框
        dwg.add(dwg.rect(insert=(0, 0), size=(width, height),
                         fill='none', stroke='#ced4da', stroke_width=1))

        return dwg.tostring()

    except Exception as e:
        logger.error(f"生成SVG验证码失败: {str(e)}", exc_info=True)
        # 返回简单的SVG作为后备（调整尺寸）
        return f'''<svg width="100" height="44" xmlns="http://www.w3.org/2000/svg">
            <rect width="100" height="44" fill="#f8f9fa" stroke="#dee2e6" stroke-width="1"/>
            <text x="50" y="28" font-family="Arial" font-size="18" text-anchor="middle" fill="#212529">{captcha_text}</text>
        </svg>'''


def verify_captcha(code, token):
    """
    验证图形验证码
    """
    if not token or token not in captcha_codes:
        return False

    captcha_info = captcha_codes.get(token)

    # 检查是否过期
    if time.time() > captcha_info['expires_at']:
        del captcha_codes[token]
        return False

    # 如果验证码文本为空，说明还没生成，需要先生成
    if not captcha_info['text']:
        # 生成4位数字验证码
        captcha_text = ''.join(random.choices(string.digits, k=4))
        captcha_info['text'] = captcha_text
        logger.debug(f"首次使用时生成验证码 - Token: {token}, 验证码: {captcha_text}")

    # 检查验证码是否正确
    if captcha_info['text'] != code:
        # 增加尝试次数
        captcha_info['attempts'] += 1
        if captcha_info['attempts'] >= 3:
            del captcha_codes[token]  # 超过3次尝试，删除验证码
        return False

    return True


def cleanup_expired_captchas():
    """清理过期的图形验证码"""
    current_time = time.time()
    expired_tokens = []

    for token, captcha_info in captcha_codes.items():
        if current_time > captcha_info['expires_at']:
            expired_tokens.append(token)

    for token in expired_tokens:
        del captcha_codes[token]

    if expired_tokens:
        logger.debug(f"清理了 {len(expired_tokens)} 个过期的图形验证码")