#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
在线文档生成工具
pip install flask
"""
import logging.config
import os
import threading
import time

from flask import (Flask, request, jsonify, send_from_directory,
                   abort, redirect, url_for, stream_with_context, Response, render_template)

import docx_util
import my_enums
from agt_util import generate_outline_stream
from db_util import DbUtl
from docx_cmt_util import get_para_comment_dict, modify_para_with_comment_prompt_in_process
from docx_util import extract_catalogue, fill_doc_with_prompt_in_progress
from sys_init import init_yml_cfg
from bp_auth import auth_bp
from bp_vdb import vdb_bp, VDB_PREFIX
from utils import get_console_arg1

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.register_blueprint(auth_bp)
app.register_blueprint(vdb_bp)
UPLOAD_FOLDER = 'upload_doc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
# 数据结构
"""
task_progress = {
   "uid1": {
        "taskId1": {
            "percent": 0.0,
            "text": "目前的状况是个啥？",
            "timestamp": time.time(),
            "elapsed_time": "xxx分xxx秒",
        }
   },
   "uid2": {
        "taskId2": {
            "percent": 0.0,
            "text": "目前的状况是个啥？",
            "timestamp": time.time(),
            "elapsed_time": "xxx分xxx秒",
        }
   }
"""
task_progress = {}
thread_lock = threading.Lock()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=my_enums.AppType.DOCX.name.lower()))


@app.route('/docx/task', methods=['GET'])
def my_docx_task():
    logger.info("my_docx_task")
    uid = request.args.get('uid')
    app_source = request.args.get('app_source')
    warning_info = request.args.get('warning_info', "")
    sys_name = my_enums.AppType.get_app_type(app_source)
    ctx = {
        "uid": uid,
        "sys_name": sys_name,
        "app_source": app_source,
        "warning_info": warning_info,
    }
    dt_idx = "docx_my_task.html"
    logger.info(f"return_page_with_no_auth {dt_idx}")
    return render_template(dt_idx, **ctx)

@app.route('/docx/generate/outline', methods=['POST'])
def generate_outline():
    """
    生成文档目录
    return outline like
    # 1.一级标题
    ## 1.1 二级标题
    ### 1.1.1 三级标题
    ### 1.1.2 三级标题
    """
    logger.info(f"gen_doc_outline {request.json}")
    doc_type = request.json.get("doc_type")
    doc_type_chinese = my_enums.WriteDocType.get_doc_type(doc_type)
    doc_title = request.json.get("doc_title")
    if not doc_type_chinese or not doc_title:
        return jsonify({"error": "未提交待写作文档的标题或文档类型，请补充"}), 400
    return Response(
        stream_with_context(generate_outline_stream(doc_type_chinese, doc_title, my_cfg)),
        mimetype='text/event-stream'
    )

@app.route('/docx/upload', methods=['POST'])  # 修正路由路径
def upload_file():
    logger.info(f"upload_file_req, {request}")
    if 'file' not in request.files:
        return jsonify({"error": "未找到文件"}), 400
    file = request.files['file']
    uid = request.form.get('uid')
    if file.filename == '':
        return jsonify({"error": "空文件名"}), 400

    # 生成任务ID和文件名
    task_id = f"{uid}_{int(time.time())}"
    filename = f"{task_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # 初始化进度
    with thread_lock:
        task_progress[task_id] = {}
    logger.info(f"upload_file_saved_as {filename}, {task_id}")
    outline = docx_util.get_outline(save_path)
    logger.info(f"get_file_outline,task_id {task_id}, {outline}")
    info = {
        "task_id": task_id,
        "file_name": filename,
        "outline": outline
    }
    logger.info(f"upload_file, {info}")
    return jsonify(info), 200

@app.route("/docx/write/outline", methods=['POST'])
def write_doc_with_outline_txt():
    """
    按照提供的三级目录文本,生成文档，这里的文档模板只有三级目录，具体的段落中没有写作要求
    文档目录参数 doc_outline 传递的文本格式如下： 1.标题1 \n1.1 标题1.1 \n1.2 标题1.2
    """
    data = request.json
    logger.info(f"write_doc_with_outline_txt , data{data}")
    uid = data.get("uid")
    doc_title = data.get("doc_title")
    doc_outline = data.get("doc_outline")
    doc_type = data.get("doc_type")
    doc_type_chinese = my_enums.WriteDocType.get_doc_type(doc_type)
    if not doc_type_chinese or not doc_title or not doc_outline:
        err_info = {"error": "缺少参数"}
        logger.error(f"err_occurred, {err_info}")
        return jsonify(err_info), 400
    task_id = str(int(time.time()))
    file_name = docx_util.gen_docx_template_with_outline(task_id, UPLOAD_FOLDER, doc_title, doc_outline)
    logger.info(f"gen_docx_template_file_name, {file_name}")
    threading.Thread(
        target=prs_doc_with_template,
        args=(uid,  doc_type, doc_title, task_id, file_name, False)
    ).start()
    info = {"status": "started", "task_id": task_id}
    logger.info(f"write_doc_with_outline_txt, {info}")
    return jsonify(info), 200

@app.route("/docx/write/template", methods=['POST'])
def write_doc_with_docx_template():
    """
    按照一定的 Word 文件模板, 生成文档
    在word文档模板中，有三级目录，在每个小节中，有用户提供的写作要求
    """
    data = request.json
    logger.info(f"write_doc_with_docx_template, {data}")
    task_id = data.get("task_id")
    doc_type = data.get("doc_type")
    doc_type_chinese = my_enums.WriteDocType.get_doc_type(doc_type)
    doc_title = data.get("doc_title")
    if not doc_type_chinese or not doc_title:
        err_info = {"error": "缺少参数"}
        logger.error(f"err_occurred, {err_info}")
        return jsonify(err_info), 400
    template_file_name = data.get("file_name")
    uid = data.get("uid")
    if not task_id or not template_file_name or not uid:
        err_info = {"error": "缺少参数"}
        logger.error(f"err_occurred, {err_info}")
        return jsonify(err_info), 400
    threading.Thread(
        target=prs_doc_with_template,
        args=(uid, doc_type_chinese, doc_title, task_id, template_file_name, True)
    ).start()

    info = {"status": "started", "task_id": task_id}
    logger.info(f"write_doc_with_docx_template, {info}")
    return jsonify(info), 200

@app.route('/docx/download/<filename>', methods=['GET'])
def download_file_by_filename(filename):
    """
    下载文件
    ：param filename: 文件名， 格式如下 f"output_{task_id}.docx"
    """
    logger.info(f"download_file, {filename}")
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        logger.error(f"文件 {filename} 不存在")
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/docx/download/task/<task_id>', methods=['GET'])
def download_file_by_task_id(task_id):
    """
    根据任务ID下载文件
    ：param task_id: 任务ID，其对应的文件名格式如下 f"output_{task_id}.docx"
    """
    logger.info(f"download_file_task_id, {task_id}")
    filename = f"output_{task_id}.docx"
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        logger.error(f"文件 {filename} 不存在")
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/docx/process/info', methods=['POST'])
def get_doc_process_info():
    # logger.info(f"get_doc_process_info {request}")
    task_id = request.json.get("task_id")
    uid = request.json.get("uid")
    if not task_id or not uid:
        return jsonify({"error": "缺少任务ID或用户ID"}), 400
    uid_str = str(uid)
    with thread_lock:
        user_tasks = task_progress.get(uid_str, {})
        task_info = user_tasks.get(task_id, {
            "text": "任务不存在或已过期",
            "percent": 0,
            "timestamp": time.time(),
            "elapsed_time": "0秒"
        })
    info = {
        "task_id": task_id,
        "progress": task_info.get("text", ""),
        "percent": task_info.get("percent", 0),
        "elapsed_time": task_info.get("elapsed_time", "")
    }
    # logger.info(f"get_doc_process_info, {info}")
    return jsonify(info), 200


def clean_tasks():
    while True:
        with thread_lock:
            now = time.time()
            expired_uids = []  # 记录待删除的空uid

            # 遍历所有用户
            for uid, tasks in list(task_progress.items()):
                expired_tasks = []  # 记录当前用户待删除的task_id

                # 遍历用户的所有任务
                for task_id, task_info in tasks.items():
                    if now - task_info['timestamp'] > 7200:  # 2小时过期
                        expired_tasks.append(task_id)
                # 删除过期任务
                for task_id in expired_tasks:
                    del tasks[task_id]

                # 如果用户无任务则标记删除
                if not tasks:
                    expired_uids.append(uid)

            # 删除空用户
            for uid in expired_uids:
                del task_progress[uid]
        time.sleep(1000)


def prs_doc_with_template(uid: int, doc_type: str, doc_title: str, task_id: str,
                          file_name: str, is_include_prompt = False):
    """
    处理无模板的文档，三级目录自动生成，每个段落无写作要求
    :param uid: 用户ID
    :param doc_type: 文档类型
    :param doc_title: 文档标题
    :param task_id: 任务ID
    :param file_name: Word template 模板文件名, 其中包含三级目录，可能含有段落写作的提示词，也可能没有
    :param is_include_prompt: 各小节是否包含有写作提示词语
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {doc_title}, "
                f"task_id: {task_id}, file_name: {file_name}, is_include_prompt = {is_include_prompt}")
    start_time = time.time()
    try:
        docx_util.update_process_info(start_time, thread_lock, uid, task_id, task_progress, "开始解析文档结构...", 0.0)
        my_target_doc = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(my_target_doc)
        output_file_name = f"output_{task_id}.docx"
        output_file = os.path.join(UPLOAD_FOLDER, output_file_name)
        logger.info(f"doc_output_file_name_for_task_id:{task_id} {output_file_name}")
        docx_util.update_process_info(start_time, thread_lock, uid, task_id, task_progress, "开始处理文档...", 0.0)
        doc_ctx = f"我正在写一个 {doc_type} 类型的文档, 文档标题是 {doc_title}"
        para_comment_dict = get_para_comment_dict(my_target_doc)
        default_vdb = DbUtl.get_default_vdb(uid)
        logger.info(f"my_default_vdb_dir_for_gen_doc: {default_vdb}")
        if default_vdb:
            my_vdb_dir = f"{VDB_PREFIX}{uid}_{default_vdb[0]['id']}"
        else:
            my_vdb_dir = ""
        logger.info(f"my_vdb_dir_for_gen_doc: {my_vdb_dir}")
        if para_comment_dict:
            logger.info("process_word_comment_doc")
            modify_para_with_comment_prompt_in_process(
                uid, task_id, thread_lock, task_progress,
                my_target_doc, doc_ctx, para_comment_dict, my_vdb_dir, my_cfg,
                output_file
            )
        elif is_include_prompt:
            logger.info("fill_doc_with_prompt_in_progress")
            fill_doc_with_prompt_in_progress(
                start_time, uid, task_id, thread_lock, task_progress, doc_ctx,
                my_target_doc, catalogue, my_vdb_dir, my_cfg, output_file,
            )
        else:
            logger.info("fill_doc_without_prompt_in_progress")
            docx_util.fill_doc_without_prompt_in_progress(
                start_time, uid, task_id, thread_lock, task_progress, doc_ctx,
                my_target_doc, catalogue, my_vdb_dir, my_cfg, output_file,
            )
    except Exception as e:
        docx_util.update_process_info(thread_lock, uid, task_id, task_progress, f"任务处理失败: {str(e)}", 0.0)
        logger.exception("文档生成异常", e)



if __name__ == '__main__':
    threading.Thread(target=clean_tasks, daemon=True).start()
    port = get_console_arg1()
    app.run(host='0.0.0.0', port=port)