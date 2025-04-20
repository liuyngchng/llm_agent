#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""

import logging.config
import os
import re

from flask import Flask, request, jsonify, render_template, Response, send_from_directory, abort

from config_util import auth_user
from semantic_search import search, classify_question, fill_table
from sys_init import init_yml_cfg
from utils import rmv_think_block

# 加载配置
logging.config.fileConfig('logging.conf', encoding="utf-8")

# 创建 logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
person_info = {}

bill_addr = '''
<svg width="41mm" height="41mm" version="1.1" viewBox="0 0 41 41" xmlns="http://www.w3.org/2000/svg"><path d="M4,4H5V5H4zM5,4H6V5H5zM6,4H7V5H6zM7,4H8V5H7zM8,4H9V5H8zM9,4H10V5H9zM10,4H11V5H10zM13,4H14V5H13zM15,4H16V5H15zM16,4H17V5H16zM18,4H19V5H18zM22,4H23V5H22zM23,4H24V5H23zM24,4H25V5H24zM27,4H28V5H27zM30,4H31V5H30zM31,4H32V5H31zM32,4H33V5H32zM33,4H34V5H33zM34,4H35V5H34zM35,4H36V5H35zM36,4H37V5H36zM4,5H5V6H4zM10,5H11V6H10zM13,5H14V6H13zM15,5H16V6H15zM19,5H20V6H19zM20,5H21V6H20zM22,5H23V6H22zM25,5H26V6H25zM26,5H27V6H26zM30,5H31V6H30zM36,5H37V6H36zM4,6H5V7H4zM6,6H7V7H6zM7,6H8V7H7zM8,6H9V7H8zM10,6H11V7H10zM12,6H13V7H12zM14,6H15V7H14zM15,6H16V7H15zM18,6H19V7H18zM20,6H21V7H20zM23,6H24V7H23zM24,6H25V7H24zM25,6H26V7H25zM26,6H27V7H26zM30,6H31V7H30zM32,6H33V7H32zM33,6H34V7H33zM34,6H35V7H34zM36,6H37V7H36zM4,7H5V8H4zM6,7H7V8H6zM7,7H8V8H7zM8,7H9V8H8zM10,7H11V8H10zM12,7H13V8H12zM15,7H16V8H15zM22,7H23V8H22zM23,7H24V8H23zM28,7H29V8H28zM30,7H31V8H30zM32,7H33V8H32zM33,7H34V8H33zM34,7H35V8H34zM36,7H37V8H36zM4,8H5V9H4zM6,8H7V9H6zM7,8H8V9H7zM8,8H9V9H8zM10,8H11V9H10zM12,8H13V9H12zM13,8H14V9H13zM14,8H15V9H14zM16,8H17V9H16zM18,8H19V9H18zM19,8H20V9H19zM20,8H21V9H20zM24,8H25V9H24zM26,8H27V9H26zM27,8H28V9H27zM28,8H29V9H28zM30,8H31V9H30zM32,8H33V9H32zM33,8H34V9H33zM34,8H35V9H34zM36,8H37V9H36zM4,9H5V10H4zM10,9H11V10H10zM12,9H13V10H12zM14,9H15V10H14zM15,9H16V10H15zM18,9H19V10H18zM21,9H22V10H21zM22,9H23V10H22zM23,9H24V10H23zM25,9H26V10H25zM30,9H31V10H30zM36,9H37V10H36zM4,10H5V11H4zM5,10H6V11H5zM6,10H7V11H6zM7,10H8V11H7zM8,10H9V11H8zM9,10H10V11H9zM10,10H11V11H10zM12,10H13V11H12zM14,10H15V11H14zM16,10H17V11H16zM18,10H19V11H18zM20,10H21V11H20zM22,10H23V11H22zM24,10H25V11H24zM26,10H27V11H26zM28,10H29V11H28zM30,10H31V11H30zM31,10H32V11H31zM32,10H33V11H32zM33,10H34V11H33zM34,10H35V11H34zM35,10H36V11H35zM36,10H37V11H36zM12,11H13V12H12zM13,11H14V12H13zM14,11H15V12H14zM15,11H16V12H15zM18,11H19V12H18zM20,11H21V12H20zM23,11H24V12H23zM24,11H25V12H24zM25,11H26V12H25zM26,11H27V12H26zM28,11H29V12H28zM4,12H5V13H4zM6,12H7V13H6zM7,12H8V13H7zM8,12H9V13H8zM9,12H10V13H9zM10,12H11V13H10zM13,12H14V13H13zM16,12H17V13H16zM18,12H19V13H18zM21,12H22V13H21zM23,12H24V13H23zM26,12H27V13H26zM28,12H29V13H28zM30,12H31V13H30zM31,12H32V13H31zM32,12H33V13H32zM33,12H34V13H33zM34,12H35V13H34zM4,13H5V14H4zM6,13H7V14H6zM7,13H8V14H7zM8,13H9V14H8zM9,13H10V14H9zM11,13H12V14H11zM12,13H13V14H12zM13,13H14V14H13zM16,13H17V14H16zM17,13H18V14H17zM18,13H19V14H18zM19,13H20V14H19zM20,13H21V14H20zM21,13H22V14H21zM22,13H23V14H22zM23,13H24V14H23zM25,13H26V14H25zM26,13H27V14H26zM27,13H28V14H27zM30,13H31V14H30zM31,13H32V14H31zM33,13H34V14H33zM34,13H35V14H34zM36,13H37V14H36zM4,14H5V15H4zM5,14H6V15H5zM6,14H7V15H6zM7,14H8V15H7zM10,14H11V15H10zM12,14H13V15H12zM14,14H15V15H14zM15,14H16V15H15zM16,14H17V15H16zM17,14H18V15H17zM18,14H19V15H18zM19,14H20V15H19zM20,14H21V15H20zM21,14H22V15H21zM24,14H25V15H24zM25,14H26V15H25zM26,14H27V15H26zM30,14H31V15H30zM32,14H33V15H32zM34,14H35V15H34zM35,14H36V15H35zM4,15H5V16H4zM6,15H7V16H6zM9,15H10V16H9zM14,15H15V16H14zM16,15H17V16H16zM17,15H18V16H17zM20,15H21V16H20zM21,15H22V16H21zM22,15H23V16H22zM25,15H26V16H25zM27,15H28V16H27zM29,15H30V16H29zM32,15H33V16H32zM33,15H34V16H33zM34,15H35V16H34zM35,15H36V16H35zM36,15H37V16H36zM5,16H6V17H5zM6,16H7V17H6zM8,16H9V17H8zM10,16H11V17H10zM11,16H12V17H11zM12,16H13V17H12zM14,16H15V17H14zM16,16H17V17H16zM18,16H19V17H18zM19,16H20V17H19zM20,16H21V17H20zM24,16H25V17H24zM29,16H30V17H29zM31,16H32V17H31zM33,16H34V17H33zM35,16H36V17H35zM36,16H37V17H36zM4,17H5V18H4zM5,17H6V18H5zM6,17H7V18H6zM8,17H9V18H8zM9,17H10V18H9zM14,17H15V18H14zM15,17H16V18H15zM16,17H17V18H16zM17,17H18V18H17zM19,17H20V18H19zM21,17H22V18H21zM22,17H23V18H22zM26,17H27V18H26zM30,17H31V18H30zM34,17H35V18H34zM35,17H36V18H35zM36,17H37V18H36zM4,18H5V19H4zM6,18H7V19H6zM10,18H11V19H10zM12,18H13V19H12zM14,18H15V19H14zM17,18H18V19H17zM18,18H19V19H18zM19,18H20V19H19zM20,18H21V19H20zM21,18H22V19H21zM24,18H25V19H24zM25,18H26V19H25zM28,18H29V19H28zM29,18H30V19H29zM30,18H31V19H30zM33,18H34V19H33zM35,18H36V19H35zM6,19H7V20H6zM7,19H8V20H7zM8,19H9V20H8zM9,19H10V20H9zM11,19H12V20H11zM12,19H13V20H12zM15,19H16V20H15zM17,19H18V20H17zM19,19H20V20H19zM25,19H26V20H25zM28,19H29V20H28zM29,19H30V20H29zM30,19H31V20H30zM31,19H32V20H31zM32,19H33V20H32zM33,19H34V20H33zM34,19H35V20H34zM4,20H5V21H4zM7,20H8V21H7zM8,20H9V21H8zM10,20H11V21H10zM12,20H13V21H12zM14,20H15V21H14zM15,20H16V21H15zM16,20H17V21H16zM17,20H18V21H17zM18,20H19V21H18zM19,20H20V21H19zM20,20H21V21H20zM21,20H22V21H21zM24,20H25V21H24zM26,20H27V21H26zM29,20H30V21H29zM31,20H32V21H31zM32,20H33V21H32zM36,20H37V21H36zM4,21H5V22H4zM7,21H8V22H7zM8,21H9V22H8zM11,21H12V22H11zM12,21H13V22H12zM13,21H14V22H13zM14,21H15V22H14zM15,21H16V22H15zM16,21H17V22H16zM18,21H19V22H18zM20,21H21V22H20zM22,21H23V22H22zM23,21H24V22H23zM24,21H25V22H24zM25,21H26V22H25zM27,21H28V22H27zM30,21H31V22H30zM31,21H32V22H31zM33,21H34V22H33zM34,21H35V22H34zM35,21H36V22H35zM9,22H10V23H9zM10,22H11V23H10zM13,22H14V23H13zM15,22H16V23H15zM16,22H17V23H16zM17,22H18V23H17zM19,22H20V23H19zM20,22H21V23H20zM22,22H23V23H22zM24,22H25V23H24zM25,22H26V23H25zM28,22H29V23H28zM31,22H32V23H31zM32,22H33V23H32zM34,22H35V23H34zM35,22H36V23H35zM4,23H5V24H4zM7,23H8V24H7zM8,23H9V24H8zM9,23H10V24H9zM12,23H13V24H12zM13,23H14V24H13zM15,23H16V24H15zM17,23H18V24H17zM20,23H21V24H20zM25,23H26V24H25zM26,23H27V24H26zM27,23H28V24H27zM29,23H30V24H29zM30,23H31V24H30zM31,23H32V24H31zM32,23H33V24H32zM33,23H34V24H33zM34,23H35V24H34zM4,24H5V25H4zM5,24H6V25H5zM6,24H7V25H6zM7,24H8V25H7zM10,24H11V25H10zM13,24H14V25H13zM14,24H15V25H14zM16,24H17V25H16zM22,24H23V25H22zM27,24H28V25H27zM29,24H30V25H29zM32,24H33V25H32zM33,24H34V25H33zM4,25H5V26H4zM7,25H8V26H7zM8,25H9V26H8zM9,25H10V26H9zM11,25H12V26H11zM12,25H13V26H12zM16,25H17V26H16zM18,25H19V26H18zM19,25H20V26H19zM20,25H21V26H20zM21,25H22V26H21zM24,25H25V26H24zM26,25H27V26H26zM34,25H35V26H34zM36,25H37V26H36zM4,26H5V27H4zM6,26H7V27H6zM7,26H8V27H7zM8,26H9V27H8zM10,26H11V27H10zM11,26H12V27H11zM12,26H13V27H12zM14,26H15V27H14zM15,26H16V27H15zM16,26H17V27H16zM18,26H19V27H18zM23,26H24V27H23zM25,26H26V27H25zM29,26H30V27H29zM30,26H31V27H30zM33,26H34V27H33zM34,26H35V27H34zM35,26H36V27H35zM4,27H5V28H4zM7,27H8V28H7zM8,27H9V28H8zM11,27H12V28H11zM12,27H13V28H12zM14,27H15V28H14zM20,27H21V28H20zM23,27H24V28H23zM24,27H25V28H24zM25,27H26V28H25zM26,27H27V28H26zM27,27H28V28H27zM28,27H29V28H28zM29,27H30V28H29zM33,27H34V28H33zM34,27H35V28H34zM35,27H36V28H35zM4,28H5V29H4zM6,28H7V29H6zM8,28H9V29H8zM10,28H11V29H10zM11,28H12V29H11zM16,28H17V29H16zM17,28H18V29H17zM21,28H22V29H21zM22,28H23V29H22zM23,28H24V29H23zM24,28H25V29H24zM26,28H27V29H26zM28,28H29V29H28zM29,28H30V29H29zM30,28H31V29H30zM31,28H32V29H31zM32,28H33V29H32zM33,28H34V29H33zM34,28H35V29H34zM12,29H13V30H12zM15,29H16V30H15zM18,29H19V30H18zM21,29H22V30H21zM22,29H23V30H22zM23,29H24V30H23zM24,29H25V30H24zM25,29H26V30H25zM28,29H29V30H28zM32,29H33V30H32zM34,29H35V30H34zM35,29H36V30H35zM36,29H37V30H36zM4,30H5V31H4zM5,30H6V31H5zM6,30H7V31H6zM7,30H8V31H7zM8,30H9V31H8zM9,30H10V31H9zM10,30H11V31H10zM14,30H15V31H14zM16,30H17V31H16zM18,30H19V31H18zM19,30H20V31H19zM20,30H21V31H20zM21,30H22V31H21zM25,30H26V31H25zM27,30H28V31H27zM28,30H29V31H28zM30,30H31V31H30zM32,30H33V31H32zM34,30H35V31H34zM4,31H5V32H4zM10,31H11V32H10zM12,31H13V32H12zM14,31H15V32H14zM17,31H18V32H17zM21,31H22V32H21zM22,31H23V32H22zM23,31H24V32H23zM24,31H25V32H24zM25,31H26V32H25zM26,31H27V32H26zM28,31H29V32H28zM32,31H33V32H32zM33,31H34V32H33zM34,31H35V32H34zM35,31H36V32H35zM4,32H5V33H4zM6,32H7V33H6zM7,32H8V33H7zM8,32H9V33H8zM10,32H11V33H10zM12,32H13V33H12zM13,32H14V33H13zM15,32H16V33H15zM16,32H17V33H16zM17,32H18V33H17zM18,32H19V33H18zM19,32H20V33H19zM20,32H21V33H20zM23,32H24V33H23zM25,32H26V33H25zM26,32H27V33H26zM28,32H29V33H28zM29,32H30V33H29zM30,32H31V33H30zM31,32H32V33H31zM32,32H33V33H32zM33,32H34V33H33zM4,33H5V34H4zM6,33H7V34H6zM7,33H8V34H7zM8,33H9V34H8zM10,33H11V34H10zM12,33H13V34H12zM14,33H15V34H14zM18,33H19V34H18zM19,33H20V34H19zM21,33H22V34H21zM22,33H23V34H22zM26,33H27V34H26zM28,33H29V34H28zM29,33H30V34H29zM32,33H33V34H32zM33,33H34V34H33zM34,33H35V34H34zM35,33H36V34H35zM36,33H37V34H36zM4,34H5V35H4zM6,34H7V35H6zM7,34H8V35H7zM8,34H9V35H8zM10,34H11V35H10zM12,34H13V35H12zM14,34H15V35H14zM16,34H17V35H16zM17,34H18V35H17zM19,34H20V35H19zM20,34H21V35H20zM21,34H22V35H21zM24,34H25V35H24zM26,34H27V35H26zM28,34H29V35H28zM29,34H30V35H29zM30,34H31V35H30zM31,34H32V35H31zM33,34H34V35H33zM34,34H35V35H34zM4,35H5V36H4zM10,35H11V36H10zM13,35H14V36H13zM15,35H16V36H15zM19,35H20V36H19zM25,35H26V36H25zM27,35H28V36H27zM29,35H30V36H29zM30,35H31V36H30zM32,35H33V36H32zM33,35H34V36H33zM34,35H35V36H34zM4,36H5V37H4zM5,36H6V37H5zM6,36H7V37H6zM7,36H8V37H7zM8,36H9V37H8zM9,36H10V37H9zM10,36H11V37H10zM12,36H13V37H12zM14,36H15V37H14zM17,36H18V37H17zM19,36H20V37H19zM20,36H21V37H20zM21,36H22V37H21zM27,36H28V37H27zM28,36H29V37H28zM29,36H30V37H29zM30,36H31V37H30zM31,36H32V37H31zM34,36H35V37H34zM35,36H36V37H35z" id="qr-path" fill="#000000" fill-opacity="1" fill-rule="nonzero" stroke="none"/></svg>
'''
@app.route('/', methods=['GET'])
def login_index():
    auth_flag = my_cfg['sys']['auth']
    if auth_flag:
        login_idx = "login.html"
        logger.info(f"return page {login_idx}")
        return render_template(login_idx, waring_info="", sys_name=my_cfg['sys']['name'])
    else:
        dt_idx = "rag_index.html"
        logger.info(f"return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, uid='foo', sys_name=my_cfg['sys']['name'])

@app.route('/login', methods=['POST'])
def login():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "rag_index.html"
    logger.debug(f"request.form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user login: {user}, {t}")
    auth_result = auth_user(user, t)
    logger.info(f"user login result: {user}, {t}, {auth_result}")
    if not auth_result["pass"]:
        logger.error(f"用户名或密码输入错误 {user}, {t}")
        ctx = {
            "user" : user,
            "sys_name" : my_cfg['sys']['name'],
            "waring_info" : "用户名或密码输入错误",
        }
        return render_template("login.html", **ctx)
    else:
        logger.info(f"return_page {dt_idx}")
        return render_template(dt_idx, uid=auth_result["uid"], sys_name=my_cfg['sys']['name'])


@app.route('/health', methods=['GET'])
def get_data():
    """
    JSON submit, get data from application JSON
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/ask' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'
    :return:
    """
    data = request.get_json()
    print(data)
    return jsonify({"message": "Data received successfully!", "data": data}), 200

@app.route('/static/<file_name>', methods=['GET'])
def get_img(file_name):
    """
    返回静态文件
    """
    if not re.match(r'^[\w\-\\.]+\.(png|jpg|jpeg|css|js|woff2?|ttf|ico|svg)$', file_name):  # 限制文件名格式
        logger.error(f"return_400_for_file_request {file_name}")
        abort(400)
    if not file_name or '/' in file_name:  # 防止路径遍历
        logger.error(f"return_400_for_file_request {file_name}")
        abort(400)
    static_dir = os.path.join(app.root_path, 'static')
    if not os.path.exists(os.path.join(static_dir, file_name)):
        logger.error(f"return_404_for_file_request {file_name}")
        abort(404)
    logger.info(f"return static file {file_name}")
    return send_from_directory(static_dir, file_name)

@app.route('/rag/submit', methods=['POST'])
def submit():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/rag/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
    :return:
    """
    msg = request.form.get('msg')
    uid = request.form.get('uid')
    logger.info("rcv_msg: {}".format(msg))
    labels = ["缴费", "上门服务", "个人资料", "自我介绍", "个人信息", "身份登记", "其他"]
    classify_result = classify_question(labels, msg, my_cfg, True)
    logger.info(f"classify_result: {classify_result}")
    content_type='text/markdown; charset=utf-8'
    if labels[0] in classify_result:
        answer = search(msg, my_cfg, True)
        # answer = rmv_think_block(answer)
        txt = '''<div>请通过微信小程序搜索"昆仑惠享+" 小程序，或者扫描以下二维码了解相关缴费信息</div>'''
        answer = f'''{txt}<div style="width: 200px; height: 200px">{bill_addr}</div>'''
        logger.info(f"answer_for_classify {labels[0]}:\n{txt}")
    elif labels[1] in classify_result:
        with open('static/dor_srv.html', 'r', encoding='utf-8') as file:
            content = file.read()
        if uid in person_info and person_info[uid]:
            answer_html = fill_table(person_info[uid], content, my_cfg, True)
            logger.info(f"html_table_with_personal_info_filled_in for {labels[1]}")
        else:
            logger.info(f"{uid},current_id_not_in person_info, {person_info}")
            answer_html = content
        content_type = 'text/html; charset=utf-8'
        txt = "<div>请填写以下信息，我们将安排工作人员上门为您提供服务</div>"
        answer = f"{txt} {answer_html}"
        logger.info(f"answer_for_classify {labels[1]}:\n{txt}")
    elif any(label in classify_result for label in labels[2:6]):
        if uid not in person_info:
            person_info[uid] = msg
        else:
            person_info[uid] += ", " + msg
        logger.info(f"person_info[{uid}] = {person_info[uid]} ")
        answer = "您提供的信息我们已经记下来了，您接着说"
        logger.info(f"answer_for_classify {labels[2:6]}:\n{answer}")
    else:
        answer = "目前暂无有的信息提供给您"
        logger.info(f"answer_for_classify_result {classify_result}:\n{answer}")
    return Response(answer, content_type=content_type, status=200)
def test_req():
    """
    ask the LLM for some private question not public to outside,
    let LLM retrieve the information from local vector database, 
    and the output the answer.
    """
    logger.info(f"config {my_cfg}")
    my_question = "我想充值缴费？"
    logger.info(f"invoke question: {my_question}")

    answer = search(my_question, my_cfg, True)
    logger.info(f"answer is \r\n{answer}")

@app.route('/door/srv', methods=['POST'])
def door_service():
    """
    form submit, get data from form
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "rag_index.html"
    serviceType = request.form.get("serviceType")
    customerName = request.form.get("customerName")
    contactNumber = request.form.get("contactNumber")
    address = request.form.get("address")
    preferredDate = request.form.get("preferredDate")
    preferredTime = request.form.get("preferredTime")
    problemDescription = request.form.get("problemDescription")
    content = (f"<div>[1]服务类型:{serviceType}</div><div>[2]客户姓名:{customerName}</div>"
               f"<div>[3]客户电话:{contactNumber}</div>"
               f"<div>[4]客户地址:{address}</div><div>[5]期望时间:{preferredDate} {preferredTime}</div>"
               f"<div>[6]问题描述:{problemDescription}</div>")
    logger.debug(f"request.form: {content}")
    content_type = 'text/html; charset=utf-8'
    answer = f"{content}<div>感谢您提供以上详细信息，我们将尽快安排工作人员上门为您提供服务</div>"
    return Response(answer, content_type=content_type, status=200)



if __name__ == '__main__':
    # test_req()
    app.run(host='0.0.0.0', port=19000)
