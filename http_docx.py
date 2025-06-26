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
import threading
import time
import cfg_util as cfg_utl

from flask import (Flask, request, jsonify, render_template, Response,
                   send_from_directory, abort, make_response)
from docx_util import extract_catalogue, fill_doc_with_progress

from sys_init import init_yml_cfg



logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
UPLOAD_FOLDER = 'upload_doc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 确保上传目录存在
auth_info = {}
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
task_progress = {}  # 存储文本进度信息
progress_lock = threading.Lock()

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
    curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/login' \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d '{"user":"test"}'
    :return:
    echo -n 'my_str' |  md5sum
    """
    dt_idx = "docx_index.html"
    logger.debug(f"request_form: {request.form}")
    user = request.form.get('usr').strip()
    t = request.form.get('t').strip()
    logger.info(f"user_login: {user}, {t}")
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

    logger.info(f"return_page {dt_idx}")
    ctx = {
        "uid": auth_result["uid"],
        "t": auth_result["t"],
        "sys_name": my_cfg['sys']['name'],
        "greeting": cfg_utl.get_const("greeting")
    }
    session_key = f"{auth_result['uid']}_{get_client_ip()}"
    auth_info[session_key] = time.time()
    return render_template(dt_idx, **ctx)


@app.route('/logout', methods=['GET'])
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
    logger.info(f"user_logout: {uid}")
    session_key = f"{uid}_{get_client_ip()}"
    auth_info.pop(session_key, None)
    usr_info = cfg_utl.get_user_info_by_uid(uid)
    usr_name = usr_info.get('name', '')
    ctx = {
        "user": usr_name,
        "sys_name": my_cfg['sys']['name'],
        "waring_info":f"用户 {usr_name} 已退出"
    }
    return render_template(dt_idx, **ctx)

@app.route('/reg/usr', methods=['GET'])
def reg_user_index():
    """
     A index for reg user
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_reg_usr_index {request.args}")
    ctx = {
        "sys_name": my_cfg['sys']['name'] + "_新用户注册",
        "waring_info":""
    }
    dt_idx = "reg_usr_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@app.route('/reg/usr', methods=['POST'])
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


@app.route('/upload', methods=['POST'])  # 修正路由路径
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "未找到文件"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400

    # 生成任务ID和文件名
    task_id = str(int(time.time()))
    filename = f"{task_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # 初始化进度
    with progress_lock:
        task_progress[task_id] = 0
    logger.info(f"upload_file_saved_as {filename}")
    return jsonify({
        "task_id": task_id,
        "file_name": filename
    }), 200


@app.route("/write/doc", methods=['POST'])
def write_doc():
    data = request.json
    task_id = data.get("task_id")
    file_name = data.get("file_name")

    if not task_id or not file_name:
        return jsonify({"error": "缺少参数"}), 400

    threading.Thread(
        target=process_document,
        args=(task_id, file_name)
    ).start()

    return jsonify({"status": "started", "task_id": task_id}), 200


@app.route('/download/<filename>', methods=['GET'])
def download_output(filename):
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        logger.error(f"文件 {filename} 不存在")
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.route('/get/process/info', methods=['POST'])
def get_doc_process_info():
    task_id = request.json.get("task_id")
    if not task_id:
        return jsonify({"error": "缺少任务ID"}), 400
    with progress_lock:
        progress_info = task_progress.get(task_id, {"text": "未知状态"})
    return jsonify({
        "task_id": task_id,
        "progress": progress_info["text"]
    }), 200

def clean_tasks():
    while True:
        with progress_lock:
            now = time.time()
            expired = [k for k, v in task_progress.items()
                      if now - v['timestamp'] > 3600]  # 1小时过期
            for k in expired:
                del task_progress[k]
        time.sleep(300)

def get_client_ip():
    """获取客户端真实 IP"""
    if forwarded_for := request.headers.get('X-Forwarded-For'):
        return forwarded_for.split(',')[0]
    return request.headers.get('X-Real-IP', request.remote_addr)


def process_document(task_id, file_name):
    try:
        task_progress[task_id] = {"text": "开始解析文档结构...", "timestamp": time.time()}
        my_target_doc = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(my_target_doc)
        output_file = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.docx")
        with progress_lock:
            task_progress[task_id] = {
                "text": "开始处理文档...",
                "timestamp": time.time()
            }

        # 实际处理函数（需改造为更新task_progress）
        fill_doc_with_progress(
            task_id,
            progress_lock,
            task_progress,
            "我正在写一个可行性研究报告",
            my_target_doc,
            catalogue,
            my_cfg,
            output_file,
        )
    except Exception as e:
        with progress_lock:
            task_progress[task_id] = {
                "text": f"任务处理失败: {str(e)}",
                "timestamp": time.time()
            }
        logger.exception("文档生成异常", e)

if __name__ == '__main__':
    threading.Thread(target=clean_tasks, daemon=True).start()
    app.run(host='0.0.0.0', port=19000)