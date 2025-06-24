#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""
import hashlib
import json
import logging.config
import os
import re
import time

from flask import (Flask, request, jsonify, render_template, Response,
                   send_from_directory, abort, make_response)
from cfg_util import auth_user, get_user_role_by_uid
from csm_service import CsmService
from docx_util import extract_catalogue, fill_doc
from my_enums import ActorRole, AI_SERVICE_STATUS
from agt_util import classify_msg
from sys_init import init_yml_cfg


logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
UPLOAD_FOLDER = 'upload_doc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 确保上传目录存在

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

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
    curl -s --noproxy '*' -X POST 'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "rag_index.html"
    logger.debug(f"request.form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user login: {user}, {t}")
    auth_result = auth_user(user, t, my_cfg)
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
        ctx = {
            "uid": auth_result["uid"],
            "sys_name": my_cfg['sys']['name'],
            "role": auth_result["role"],
            "t": auth_result["t"],
        }
        return render_template(dt_idx, **ctx)


@app.route('/health', methods=['GET'])
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



@app.route('/upload/<file_name>', methods=['POST'])
def upload_file(file_name):
    """
    上传文件，保存在当前目录下的 upload_doc 文件夹下面，文件名称为 "当前时间戳_用户上传文件名的md5值.docx"
    """

    if 'file' not in request.files:
        return '未找到文件', 400
    file = request.files['file']
    if file.filename == '':
        return '空文件名', 400

    # 生成新文件名：时间戳_MD5.docx
    filename_md5 = hashlib.md5(file_name.encode()).hexdigest()
    new_name = f"{int(time.time())}_{filename_md5}.docx"
    save_path = os.path.join(UPLOAD_FOLDER, new_name)
    file.save(save_path)

    doc_ctx = "我正在写一个可行性研究报告"
    doc_catalogue = extract_catalogue(save_path)
    logger.info(f"my_target_doc_catalogue: {doc_catalogue}")

    output_doc = fill_doc(doc_ctx, my_source_dir, my_target_doc, doc_catalogue, my_cfg)
    output_file = 'doc_output.docx'
    output_doc.save(output_file)
    return f'文件已保存为: {new_name}', 200

@app.route('/download/<file_name>', methods=['POST'])
def download_file(file_name):
    """
    按照文件名下载相应的文件
    """
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return '文件不存在', 404
    return send_from_directory(UPLOAD_FOLDER, file_name, as_attachment=True)


@app.route('/get/process/info', methods=['POST'])
def get_doc_process_info():
    """
    获取文件处理进度信息文本，用于在用户前端显示处理信息，前端每隔几秒刷新一次
    """



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=19000)