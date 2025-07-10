#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
"""
import logging.config
import os
import threading
import time

from flask import (Flask, request, jsonify, send_from_directory, abort, redirect, url_for, render_template)

import docx_util
import my_enums
from agt_util import gen_doc_outline
from docx_cmt_util import get_para_comment_dict, modify_para_with_comment_prompt_in_process
from docx_util import extract_catalogue, fill_doc_with_prompt_in_progress
from sys_init import init_yml_cfg
from bp_auth import auth_bp
from bp_vdb import vdb_bp

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
task_progress = {}
thread_lock = threading.Lock()

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source='docx'))


@app.route('/docx/generate/outline', methods=['POST'])
def generate_outline():
    """
    生成文档目录
    return outline like
    [
        {
            "title": "1. 背景",
            "items": [
                {"title": "1.1 概述", "items": ["1.1.1 项目背景", "1.1.2 核心问题", "1.1.3 关键数据"]},
                {"title": "1.2 项目进展", "items": ["1.2.1 项目进展", "1.2.2 里程碑节点", "1.2.3 关键技术"]},
                {"title": "1.3 关键数据", "items": ["1.3.1 数据类型", "1.3.2 数据存储", "1.3.3 数据价值"]}
            ]
        },
        {
            "title": "2. 问题分析",
            "items": [
                {"title": "2.1 面临挑战", "items": ["2.1.1 国内外现状", "2.1.2 解决的问题", "2.1.3 面临的问题"]},
                {"title": "2.2 解决思路", "items": ["2.2.1 基础研究投入", "2.2.2 样品试制", "2.2.3 工程环境应用"]},
                {"title": "2.3 经验总结", "items": ["2.3.1 理论研究支持", "2.3.2 专利限制突破", "2.2.3 自有技术积累"]}
            ]
        }
    ]
    """
    logger.info(f"gen_doc_outline {request}")
    doc_type = request.json.get("doc_type")
    doc_type_chinese = my_enums.WriteDocType.get_doc_type(doc_type)
    doc_title = request.json.get("doc_title")
    if not doc_type_chinese or not doc_title:
        return jsonify({"error": "缺少参数"}), 400
    doc_outline = gen_doc_outline(doc_type_chinese, doc_title, my_cfg)
    return jsonify({"status": "success", "outline": doc_outline}), 200


@app.route('/docx/upload', methods=['POST'])  # 修正路由路径
def upload_file():
    logger.info(f"upload_file {request}")
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
    with thread_lock:
        task_progress[task_id] = 0
    logger.info(f"upload_file_saved_as {filename}")
    return jsonify({
        "task_id": task_id,
        "file_name": filename
    }), 200


@app.route("/docx/write/outline", methods=['POST'])
def write_doc_without_template():
    """
    按照提供的三级目录文本,生成文档
    """
    data = request.json
    logger.info(f"write_doc , data{data}")
    uid = data.get("uid")
    doc_title = data.get("docTitle")
    doc_outline = data.get("docOutline")
    doc_type = data.get("docType")
    doc_type_chinese = my_enums.WriteDocType.get_doc_type(doc_type)
    if not doc_type_chinese or not doc_title or not doc_outline:
        return jsonify({"error": "缺少参数"}), 400
    task_id = str(int(time.time()))
    file_name = docx_util.gen_docx_template_with_outline(task_id, UPLOAD_FOLDER, doc_outline)
    logger.info(f"gen_docx_template_file_name {file_name}")
    threading.Thread(
        target=process_document_without_template,
        args=(uid,  doc_type, doc_title, task_id, file_name)
    ).start()

    return jsonify({"status": "started", "task_id": task_id}), 200

@app.route("/docx/write/template", methods=['POST'])
def write_doc_with_template():
    """
    按照一定的 Word 文件模板, 生成文档
    """
    data = request.json
    logger.info(f"write_doc , data{data}")
    task_id = data.get("task_id")
    file_name = data.get("file_name")
    uid = data.get("uid")
    if not task_id or not file_name or not uid:
        return jsonify({"error": "缺少参数"}), 400

    threading.Thread(
        target=process_document_with_template,
        args=(uid, task_id, file_name)
    ).start()

    return jsonify({"status": "started", "task_id": task_id}), 200


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


@app.route('/docx/download/task/<taskId>', methods=['GET'])
def download_file_by_task_id(taskId):
    """
    根据任务ID下载文件
    ：param taskId: 任务ID，其对应的文件名格式如下 f"output_{taskId}.docx"
    """
    logger.info(f"download_file_task_id, {taskId}")
    filename = f"output_{taskId}.docx"
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        logger.error(f"文件 {filename} 不存在")
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@app.route('/docx/process/info', methods=['POST'])
def get_doc_process_info():
    logger.info(f"get_doc_process_info {request}")
    task_id = request.json.get("task_id")
    if not task_id:
        return jsonify({"error": "缺少任务ID"}), 400
    with thread_lock:
        progress_info = task_progress.get(task_id, {"text": "未知状态"})
    info = {
        "task_id": task_id,
        "progress": progress_info["text"]
    }
    logger.info(f"get_doc_process_info, {info}")
    return jsonify(info), 200


def clean_tasks():
    while True:
        with thread_lock:
            now = time.time()
            expired = [k for k, v in task_progress.items()
                      if now - v['timestamp'] > 3600]  # 1小时过期
            for k in expired:
                del task_progress[k]
        time.sleep(300)


def process_document_without_template(uid: str, doc_type: str, doc_title: str, task_id: str, file_name: str):
    """
    处理无模板的文档，三级目录自动生成，每个段落无写作要求
    :param uid: 用户ID
    :param doc_type: 文档类型
    :param doc_title: 文档标题
    :param task_id: 任务ID
    :param file_name: 文件名
    """
    try:
        task_progress[task_id] = {"text": "开始解析文档结构...", "timestamp": time.time()}
        my_target_doc = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(my_target_doc)
        output_file_name = f"output_{task_id}.docx"
        output_file = os.path.join(UPLOAD_FOLDER, output_file_name)
        logger.info(f"doc_output_file_name_for_task_id:{task_id} {output_file_name}")
        with thread_lock:
            task_progress[task_id] = {"text": "开始处理文档...","timestamp": time.time()}
        doc_ctx = f"我正在写一个{doc_type}, 题目是{doc_title}"
        para_comment_dict = get_para_comment_dict(my_target_doc)

        if para_comment_dict:
            logger.info("process_word_comment_doc")
            modify_para_with_comment_prompt_in_process(
                uid,
                task_id,
                thread_lock,
                task_progress,
                my_target_doc,
                doc_ctx,
                para_comment_dict,
                my_cfg,
                output_file
            )
        else:
            logger.info("fill_doc_without_prompt_in_progress")
            docx_util.fill_doc_without_prompt_in_progress(
                task_id,
                thread_lock,
                task_progress,
                doc_ctx,
                my_target_doc,
                catalogue,
                my_cfg,
                output_file,
            )
    except Exception as e:
        with thread_lock:
            task_progress[task_id] = {
                "text": f"任务处理失败: {str(e)}",
                "timestamp": time.time()
            }
        logger.exception("文档生成异常", e)


def process_document_with_template(uid: str, task_id: str, file_name: str):
    """
    处理有模板的文档, 三级目录及写作要求已有要求
    :param uid: 用户ID
    :param task_id: 任务ID
    :param file_name: 文件名
    """
    try:
        task_progress[task_id] = {"text": "开始解析文档结构...", "timestamp": time.time()}
        my_target_doc = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(my_target_doc)
        output_file = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.docx")
        with thread_lock:
            task_progress[task_id] = {"text": "开始处理文档...","timestamp": time.time()}
        para_comment_dict = get_para_comment_dict(my_target_doc)
        if para_comment_dict:
            logger.info("process_word_comment_doc")
            modify_para_with_comment_prompt_in_process(
                uid,
                task_id,
                thread_lock,
                task_progress,
                my_target_doc,
                "我正在写一个可行性研究报告",
                para_comment_dict,
                my_cfg,
                output_file
            )
        else:
            logger.info("fill_doc_with_prompt_in_progress")
            fill_doc_with_prompt_in_progress(
                task_id,
                thread_lock,
                task_progress,
                "我正在写一个可行性研究报告",
                my_target_doc,
                catalogue,
                my_cfg,
                output_file,
            )
    except Exception as e:
        with thread_lock:
            task_progress[task_id] = {
                "text": f"任务处理失败: {str(e)}",
                "timestamp": time.time()
            }
        logger.exception("文档生成异常", e)

if __name__ == '__main__':
    threading.Thread(target=clean_tasks, daemon=True).start()
    app.run(host='0.0.0.0', port=19000)