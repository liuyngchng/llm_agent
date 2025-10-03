#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
在线文档生成工具
pip install flask
"""
import json
import logging.config
import os
import threading
import time

from flask import (Flask, request, jsonify, send_from_directory,
                   abort, redirect, url_for, stream_with_context, Response, render_template)

import docx_cmt_util
import docx_meta_util
import docx_util
import mermaid_render
import my_enums
from agt_util import gen_docx_outline_stream
from docx_gen_parallel import DocxGenerator
from docx_cmt_util import get_para_comment_dict, modify_para_with_comment_prompt_in_process
from docx_util import extract_catalogue, fill_doc_with_prompt_in_progress, fill_doc_without_prompt_in_progress
from sys_init import init_yml_cfg
from bp_auth import auth_bp
from bp_vdb import vdb_bp, VDB_PREFIX, clean_expired_vdb_file_task, process_vdb_file_task
from utils import get_console_arg1
from vdb_meta_util import VdbMeta

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.register_blueprint(auth_bp)
app.register_blueprint(vdb_bp)
UPLOAD_FOLDER = 'upload_doc'
TASK_EXPIRE_TIME_MS =7200 *1000  # 任务超时时间，默认2小时
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)


@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=my_enums.AppType.DOCX.name.lower()))


@app.route('/docx/task', methods=['GET'])
def docx_task_index():
    """
    获取当前在进行的写作任务，渲染页面
    """
    logger.info(f"docx_task_index, {request.args}")
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

@app.route('/docx/my/task', methods=['POST'])
def my_docx_task():
    """
    获取当前在进行的写作任务
    """
    data = request.json
    logger.info(f"my_docx_task_req, {data}")
    uid = int(data.get('uid'))
    logger.info(f"get_my_docx_task, uid {uid}")
    task_list = docx_meta_util.get_user_docx_task_list(uid)
    return json.dumps(task_list, ensure_ascii=False), 200


@app.route('/docx/generate/outline', methods=['POST'])
def generate_outline():
    """
    对于没有写作模板的，由系统自动生成文档目录，默认为三级
    return outline like
    # 1.一级标题
    ## 1.1 二级标题
    ### 1.1.1 三级标题
    ### 1.1.2 三级标题
    """
    logger.info(f"gen_doc_outline {request.json}")
    uid = request.json.get("uid")
    doc_type = request.json.get("doc_type")
    doc_type_chinese = my_enums.WriteDocType.get_doc_type_desc(doc_type)
    doc_title = request.json.get("doc_title")
    keywords = request.json.get("keywords")
    if not doc_type_chinese or not doc_title:
        return jsonify({"error": "未提交待写作文档的标题或文档类型，请补充"}), 400
    return Response(
        stream_with_context(gen_docx_outline_stream(doc_type_chinese, doc_title, keywords, my_cfg)),
        mimetype='text/event-stream',
        status=200,
    )

@app.route('/docx/upload', methods=['POST'])
def upload_docx_template_file():
    """
    上传Word docx写作文档模板，需要包含三级目录
    """
    logger.info(f"upload_file_req, {request}")
    if 'file' not in request.files:
        return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
    file = request.files['file']
    uid = int(request.form.get('uid'))
    if file.filename == '':
        return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

    # 生成任务ID， 使用毫秒数
    task_id = int(time.time()*1000)
    filename = f"{task_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)
    logger.info(f"upload_file_saved_as {filename}, {task_id}")
    outline = docx_util.get_outline_txt(save_path)
    logger.info(f"get_file_outline,task_id {task_id}, {outline}")
    info = {
        "task_id": task_id,
        "file_name": filename,
        "outline": outline
    }
    logger.info(f"upload_docx_template_file, {info}")
    return json.dumps(info, ensure_ascii=False), 200

@app.route("/docx/write/outline", methods=['POST'])
def write_doc_with_outline_txt():
    """
    按照提供的三级目录文本,生成docx 文档模板，这里的文档模板只有目录（默认三级），具体的段落中没有写作要求
    文档目录参数 doc_outline 传递的文本格式如下： 1.标题1 \n1.1 标题1.1 \n1.2 标题1.2
    """
    data = request.json
    logger.info(f"write_doc_with_outline_txt, data{data}")
    uid = data.get("uid")
    doc_title = data.get("doc_title")
    doc_outline = data.get("doc_outline")
    doc_type = data.get("doc_type")

    doc_type_desc = my_enums.WriteDocType.get_doc_type_desc(doc_type)
    if not doc_type_desc or not doc_title or not doc_outline:
        err_info = {"error": "缺少文档类型、标题、目录参数中的一个或多个"}
        logger.error(f"err_occurred, {err_info}")
        return json.dumps(err_info, ensure_ascii=False), 400
    task_id = int(time.time()*1000)                 # 生成任务ID， 使用毫秒数
    if data.get("vbd_id"):
        vbd_id = int(data.get("vbd_id"))
    else:
        vbd_id = None
    keywords = data.get("keywords")
    template_file_name = docx_util.gen_docx_template_with_outline_txt(task_id, UPLOAD_FOLDER, doc_title, doc_outline)
    logger.info(f"docx_template_file_generated_with_name, {template_file_name}")
    docx_meta_util.save_docx_meta_info(uid, task_id, doc_type_desc, doc_title, keywords, template_file_name)
    threading.Thread(
        target=fill_docx_with_template,
        args=(uid, doc_type_desc, doc_title, keywords, task_id, template_file_name, vbd_id, False)
    ).start()
    info = {"status": "started", "task_id": task_id}
    logger.info(f"write_doc_with_outline_txt, {info}")
    return json.dumps(info, ensure_ascii=False), 200

@app.route("/docx/write/template", methods=['POST'])
def write_doc_with_docx_template():
    """
    按照一定的 Word 文件模板, 生成文档
    在word文档模板中，有三级目录，在每个小节中，有用户提供的写作要求
    """
    data = request.json
    logger.info(f"write_doc_with_docx_template, {data}")
    task_id = int(data.get("task_id"))
    doc_type = data.get("doc_type")
    doc_type_desc = my_enums.WriteDocType.get_doc_type_desc(doc_type)
    doc_title = data.get("doc_title")

    if not doc_type_desc or not doc_title:
        err_info = {"error": "缺少参数"}
        logger.error(f"err_occurred, {err_info}")
        return json.dumps(err_info, ensure_ascii=False), 400
    template_file_name = data.get("file_name")
    uid = data.get("uid")
    keywords = data.get("keywords")
    if data.get("vbd_id"):
        vbd_id = int(data.get("vbd_id"))
    else:
        vbd_id = None
    if not task_id or not template_file_name or not uid:
        err_info = {"error": "缺少任务ID、写作模板文件名称和用户ID中的一个或多个"}
        logger.error(f"err_occurred, {err_info}")
        return jsonify(err_info), 400
    docx_meta_util.save_docx_meta_info(uid, task_id, doc_type_desc, doc_title, keywords, template_file_name)
    threading.Thread(
        target=fill_docx_with_template,
        args=(uid, doc_type_desc, doc_title, keywords, task_id, template_file_name, vbd_id, True)
    ).start()

    info = {"status": "started", "task_id": task_id}
    logger.info(f"write_doc_with_docx_template, {info}")
    return json.dumps(info, ensure_ascii=False), 200

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

@app.route('/docx/del/task/<task_id>', methods=['GET'])
def delete_file_info_by_task_id(task_id):
    """
    根据任务ID下载文件
    ：param task_id: 任务ID，其对应的文件名格式如下 f"output_{task_id}.docx"
    """
    logger.info(f"download_file_task_id, {task_id}")
    filename = f"output_{task_id}.docx"
    disk_file = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(disk_file):
        os.remove(disk_file)
    else:
        logger.warning(f"文件 {filename} 不存在， 无需删除物理文件, 只需删除数据库记录")
    docx_meta_util.delete_docx_info_by_task_id(task_id)

    return json.dumps({"msg":"删除成功", "task_id": task_id}, ensure_ascii=False), 200

@app.route('/docx/process/info', methods=['POST'])
def get_doc_process_info():
    # logger.info(f"get_doc_process_info {request}")
    task_id = request.json.get("task_id")
    uid = request.json.get("uid")
    if not task_id or not uid:
        return jsonify({"error": "缺少任务ID或用户ID"}), 400
    file_info = docx_meta_util.get_docx_info_by_task_id(task_id)
    logger.info(f"get_docx_info_by_task_id, {file_info}")
    if not file_info or len(file_info) == 0:
        return json.dumps({"error": "未找到任务ID对应的文档信息"}, ensure_ascii=False), 400
    file_info[0]['elapsed_time'] = time.time() - task_id
    # logger.info(f"get_doc_process_info, {info}")
    return json.dumps(file_info, ensure_ascii=False), 200


def clean_docx_tasks():
    while True:
        now = time.time()
        expired_uids = []  # 记录待删除的空uid
        docx_list = docx_meta_util.get_docx_file_processing_list()
        # 遍历所有用户
        for file in docx_list:
            if now - file['task_id'] > TASK_EXPIRE_TIME_MS:  # 2小时过期
                docx_meta_util.delete_docx_info_by_task_id(file['task_id'])
        time.sleep(1000)


def fill_docx_with_template(uid: int, doc_type: str, doc_title: str, keywords: str, task_id: int,
                            file_name: str, vbd_id: int, is_include_para_txt=False):
    """
    处理无模板的文档，三级目录自动生成，每个段落无写作要求
    :param uid: 用户ID
    :param doc_type: docx文档内容类型
    :param doc_title: docx文档的标题
    :param keywords: 其他的写作要求
    :param task_id: 任务ID
    :param file_name: Word template 模板文件名, 其中包含三级目录，可能含有段落写作的提示词，也可能没有
    :param vbd_id: vector db id.
    :param is_include_para_txt: 各小节（章节标题下）是否包含有描述性的文本
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {doc_title}, keywords: {keywords}, "
                f"task_id: {task_id}, file_name: {file_name}, vbd_id:{vbd_id}, is_include_para_txt = {is_include_para_txt}")

    generator = None
    try:
        docx_meta_util.update_docx_file_process_info_by_task_id(task_id, "开始解析文档结构...", 0)
        full_file_name = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(full_file_name)
        docx_meta_util.save_docx_outline_by_task_id(task_id, catalogue)
        output_file_name = f"output_{task_id}.docx"
        output_file = os.path.join(UPLOAD_FOLDER, output_file_name)
        logger.info(f"doc_output_file_name_for_task_id:{task_id} {output_file_name}")
        docx_meta_util.update_docx_file_process_info_by_task_id(task_id, "开始处理文档...")
        doc_ctx = f"我正在写一个 {doc_type} 类型的文档, 文档标题是 {doc_title}, 其他写作要求是 {keywords}"


        if vbd_id:
            default_vdb = VdbMeta.get_vdb_by_id(vbd_id)
            logger.info(f"my_default_vdb_dir_for_gen_doc: {default_vdb}")
        else:
            default_vdb = None
        if default_vdb:
            my_vdb_dir = f"{VDB_PREFIX}{uid}_{default_vdb[0]['id']}"
        else:
            my_vdb_dir = ""
        logger.info(f"my_vdb_dir_for_gen_doc: {my_vdb_dir}")

        # 使用并行化版本
        generator = DocxGenerator()
        para_comment_dict = get_para_comment_dict(full_file_name)
        if para_comment_dict:
            logger.info("使用并行化批注处理")
            generator.modify_para_with_comment_prompt_in_parallel(
                task_id, full_file_name, catalogue, doc_ctx, para_comment_dict,
                my_vdb_dir, my_cfg, output_file
            )
        elif is_include_para_txt:
            logger.info("使用并行化带提示词处理")
            generator.fill_doc_with_prompt_in_parallel(
                task_id, doc_ctx, full_file_name, catalogue, my_vdb_dir, my_cfg, output_file
            )
        else:
            logger.info("使用并行化无提示词处理")
            generator.fill_doc_without_prompt_in_parallel(
                task_id, doc_ctx, full_file_name, catalogue, my_vdb_dir, my_cfg, output_file
            )
        if generator and os.path.exists(output_file):
            try:
                logger.info(f"开始处理文档中的Mermaid图表: {output_file}")
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, "开始给文档添加图表")
                mermaid_render.mermaid_renderer.batch_process_mermaid_in_docx(output_file)
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, "文档图表添加完成")
                logger.info(f"Mermaid图表处理完成: {output_file}")
            except Exception as e:
                logger.error(f"Mermaid图表处理失败，但不影响文档主体: {str(e)}")
                # 记录错误但不中断流程
                docx_meta_util.update_docx_file_process_info_by_task_id(
                    task_id, f"文档生成完成，但图表处理遇到问题: {str(e)}"
                )
        generator.shutdown()

    except Exception as e:
        docx_meta_util.update_docx_file_process_info_by_task_id(task_id, f"任务处理失败: {str(e)}")
        logger.exception("文档生成异常", e)
    finally:
        # 确保资源被释放
        if generator:
            generator.shutdown()



if __name__ == '__main__':
    threading.Thread(target=clean_docx_tasks, daemon=True).start()
    threading.Thread(target=clean_expired_vdb_file_task, daemon=True).start()
    threading.Thread(target=process_vdb_file_task, daemon=True).start()
    port = get_console_arg1()
    app.run(host='0.0.0.0', port=port)