#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
在线会议纪要整理工具
pip install flask
"""
import json
import logging.config
import os
import threading
import time

from flask import (Flask, request, jsonify, send_from_directory, abort, redirect, url_for, render_template)
from google.auth.aio.transport.aiohttp import Response

from apps.docx import docx_meta_util
from apps.docx.docx_editor import DocxEditor
from apps.docx.docx_para_util import extract_catalogue, get_outline_txt
from apps.mt_report.mt_report_util import get_doc_content, get_template_field, get_txt_abs, insert_para_to_doc
from common import my_enums, statistic_util
from common.my_enums import AppType
from common.sys_init import init_yml_cfg
from common.bp_auth import auth_bp, get_client_ip, auth_info, SESSION_TIMEOUT
from common.cm_utils import get_console_arg1

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'upload_doc'
TASK_EXPIRE_TIME_MS = 7200 * 1000  # 任务超时时间，默认2小时
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

def create_app():
    """应用工厂函数"""
    app = Flask(__name__, static_folder=None)
    app.config['JSON_AS_ASCII'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['TASK_EXPIRE_TIME_MS'] = TASK_EXPIRE_TIME_MS
    app.config['MY_CFG'] = my_cfg
    # 注册蓝图
    app.register_blueprint(auth_bp)
    # 注册路由
    register_routes(app)
    return app


def register_routes(app):
    """注册所有路由"""
    @app.route('/static/<path:file_name>')
    def get_static_file(file_name):
        static_dirs = [
            os.path.join(os.path.dirname(__file__), '../../common/static'),
            os.path.join(os.path.dirname(__file__), 'static'),
        ]

        for static_dir in static_dirs:
            if os.path.exists(os.path.join(static_dir, file_name)):
                # logger.debug(f"get_static_file, {static_dir}, {file_name}")
                return send_from_directory(static_dir, file_name)
        logger.error(f"no_file_found_error, {file_name}")
        abort(404)

    @app.route('/')
    def app_home():
        logger.info("redirect_auth_login_index")
        return redirect(url_for('auth.login_index', app_source=my_enums.AppType.MT_REPORT.name.lower()))


    @app.route('/docx/upload', methods=['POST'])
    def upload_docx_template_file():
        """
        上传 Word docx 会议纪要文档模板
        """
        logger.info(f"upload_docx_template_file, {request}")
        if 'file' not in request.files:
            return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
        file = request.files['file']
        uid = int(request.form.get('uid'))
        logger.info(f"{uid}, upload_docx_template_file")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.MT_REPORT.name.lower(),
                warning_info=warning_info

            ))
        if file.filename == '':
            return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

        # 生成任务ID， 使用毫秒数
        task_id = int(time.time() * 1000)
        filename = f"{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        logger.info(f"upload_file_saved_as {filename}, {task_id}")
        outline = get_outline_txt(save_path)
        logger.info(f"get_file_outline,task_id {task_id}, {outline}")
        info = {
            "task_id": task_id,
            "file_name": filename,
            "outline": outline
        }
        logger.info(f"upload_docx_template_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route("/mt_report/gen", methods=['POST'])
    def gen_mt_report():
        """
        按照一定的 Word 文件模板, 生成文档
        在word文档模板中，有三级目录，在每个小节中，有用户提供的写作要求
        """
        data = request.json
        uid = data.get("uid")
        logger.info(f"{uid}, gen_mt_report_dt, {data}")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return jsonify(warning_info), 400
        task_id = int(data.get("task_id"))
        doc_title = data.get("doc_title")

        if not doc_title:
            err_info = {"error": "文档标题不能为空"}
            logger.error(f"err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400
        template_file_name = data.get("file_name")
        if not task_id or not template_file_name or not uid:
            err_info = {"error": "缺少任务ID、写作模板文件名称和用户ID中的一个或多个"}
            logger.error(f"err_occurred, {err_info}")
            return jsonify(err_info), 400
        keywords = data.get("keywords")
        if not keywords:
            err_info = {"error": "会议纪要内容为空"}
            logger.error(f"err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400

        template_file_name = data.get("file_name")
        doc_type = my_enums.WriteDocType.MEETING_REPORT.value
        docx_meta_util.save_meta_info(uid, task_id, doc_type, doc_title, keywords, template_file_name)
        threading.Thread(
            target=fill_mt_report_with_txt,
            args=(uid, doc_type, doc_title, keywords, task_id, template_file_name)
        ).start()

        info = {"status": "started", "task_id": task_id}
        logger.info(f"write_doc_with_docx_template, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route('/mt_report/task', methods=['GET'])
    def docx_task_index():
        """
        获取当前在进行的写作任务，渲染页面
        """
        logger.info(f"mt_report_index, {request.args}")
        uid = request.args.get('uid')
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.MT_REPORT.name.lower(),
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
        dt_idx = "mt_report_my_task.html"
        logger.info(f"{uid}, return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, **ctx)

    @app.route('/mt_report/my/task', methods=['POST'])
    def my_docx_task():
        """
        获取用户的写作任务
        """
        data = request.json
        uid = int(data.get('uid'))
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            # logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.MT_REPORT.name.lower(),
                warning_info=warning_info

            ))
        logger.info(f"{uid}, get_my_mt_report_task, {data}")
        task_list = docx_meta_util.get_user_task_list(uid)
        return json.dumps(task_list, ensure_ascii=False), 200

    @app.route('/docx/download/<filename>', methods=['GET'])
    def download_file_by_filename(filename):
        """
        下载文件
        ：param filename: 文件名， 格式如下 f"output_{task_id}.docx"
        """

        uid = request.args["uid"]
        logger.info(f"{uid}, download_file, {filename}")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.DOCX.name.lower(),
                warning_info=warning_info

            ))
        statistic_util.add_access_count_by_uid(int(uid), 1)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        absolute_path = os.path.abspath(file_path)
        logger.info(f"文件检查 - 绝对路径: {absolute_path}")

        if not os.path.exists(absolute_path):
            logger.error(f"文件不存在: {absolute_path}")
            abort(404)

        logger.info(f"文件找到，准备发送: {absolute_path}")
        try:
            from flask import send_file
            return send_file(
                absolute_path,
                as_attachment=True,
                download_name=filename,
                mimetype=DOCX_MIME_TYPE,
            )
        except Exception as e:
            logger.error(f"文件发送失败: {str(e)}")
            abort(500)

    @app.route('/docx/download/task/<task_id>', methods=['GET'])
    def download_file_by_task_id(task_id):
        """
        根据任务ID下载文件
        ：param task_id: 任务ID，其对应的文件名格式如下 f"output_{task_id}.docx"
        """

        uid = request.args["uid"]
        logger.info(f"{uid}, download_file_task_id, {task_id}")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.DOCX.name.lower(),
                warning_info=warning_info

            ))
        statistic_util.add_access_count_by_uid(int(uid), 1)
        filename = f"output_{task_id}.docx"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        absolute_path = os.path.abspath(file_path)
        logger.info(f"文件检查 - 相对路径: {file_path}")
        logger.info(f"文件检查 - 绝对路径: {absolute_path}")
        logger.info(f"文件检查 - UPLOAD_FOLDER: {UPLOAD_FOLDER}")
        logger.info(f"文件检查 - 当前工作目录: {os.getcwd()}")
        if not os.path.exists(absolute_path):
            logger.error(f"文件不存在: {absolute_path}")
            abort(404)

        if not os.access(absolute_path, os.R_OK):
            logger.error(f"文件不可读: {absolute_path}")
            abort(403)
        logger.info(f"文件找到，准备发送: {absolute_path}")
        try:
            from flask import send_file
            logger.info(f"使用 send_file 发送: {absolute_path}")
            return send_file(
                absolute_path,
                as_attachment=True,
                download_name=filename,
                mimetype=DOCX_MIME_TYPE,
            )
        except Exception as e:
            logger.error(f"文件发送失败: {str(e)}")
            abort(500)


def fill_mt_report_with_txt(uid: int, doc_type: str, doc_title: str, keywords: str, task_id: int, file_name: str):
    """
    按照固定的模板，将会议纪要内容填充至Word文档中
    :param uid: 用户ID
    :param doc_type: docx文档内容类型
    :param doc_title: docx文档的标题
    :param keywords: 会议内容要点
    :param task_id: 任务ID
    :param file_name: Word template 模板文件名
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {doc_title}, keywords: {keywords}, "
                f"task_id: {task_id}, file_name: {file_name}")
    try:
        docx_meta_util.update_process_info_by_task_id(task_id, "开始解析模板文档结构...", 0)
        full_file_name = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(full_file_name)
        docx_meta_util.save_outline_by_task_id(task_id, catalogue)

        docx_meta_util.update_process_info_by_task_id(task_id, "开始处理文档...")
        doc_all_txt = get_doc_content(full_file_name)
        logger.info(f"doc_all_txt={doc_all_txt}")
        doc_field = get_template_field(my_cfg, doc_all_txt)
        logger.info(f"doc_field={doc_field}")
        fill_para_txt_dict = get_txt_abs(my_cfg, keywords, doc_field)
        output_file_name = f"output_{task_id}.docx"
        output_file = os.path.join(UPLOAD_FOLDER, output_file_name)
        logger.info(f"doc_output_file_name_for_task_id:{task_id} {output_file_name}")

        insert_para_to_doc(full_file_name, output_file, fill_para_txt_dict)
        docx_meta_util.update_process_info_by_task_id(task_id, "文档处理完毕", 100)
    except Exception as e:
        docx_meta_util.update_process_info_by_task_id(task_id, f"任务处理失败: {str(e)}")
        logger.exception("文档生成异常", e)

# 创建应用实例
app = create_app()

# 当直接运行脚本时，启动开发服务器
if __name__ == '__main__':
    # result = VdbMeta.get_vdb_file_processing_list()
    # logger.info(f"vdb_file_processing_list: {result}")
    # 确保后台任务在直接运行时也启动
    # start_background_tasks_once()
    port = get_console_arg1()
    app.run(host='0.0.0.0', port=port)