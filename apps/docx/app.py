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

from apps.docx.docx_cmt_util import get_comments_dict
from apps.docx.txt_gen_util import gen_docx_outline_stream
from apps.docx.docx_editor import DocxEditor
from common.docx_para_util import extract_catalogue, gen_docx_template_with_outline_txt, get_outline_txt
from common import my_enums, statistic_util,docx_meta_util
from common.my_enums import AppType
from common.sys_init import init_yml_cfg
from common.bp_auth import auth_bp, get_client_ip, auth_info, SESSION_TIMEOUT
from common.bp_vdb import vdb_bp, VDB_PREFIX, clean_expired_vdb_file_task, process_vdb_file_task
from common.cm_utils import get_console_arg1
from common.vdb_meta_util import VdbMeta

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'upload_doc'
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TASK_EXPIRE_TIME_MS = 7200 * 1000  # 任务超时时间，默认2小时
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

# 全局变量，用于存储后台任务状态
background_tasks_started = False
background_tasks_lock = threading.Lock()


def create_app():
    """应用工厂函数"""
    app = Flask(__name__, static_folder=None)
    app.config['JSON_AS_ASCII'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['TASK_EXPIRE_TIME_MS'] = TASK_EXPIRE_TIME_MS
    app.config['MY_CFG'] = my_cfg

    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(vdb_bp)

    # 注册路由
    register_routes(app)

    # 在应用启动时初始化后台任务（使用应用上下文）
    with app.app_context():
        start_background_tasks_once()

    return app


def start_background_tasks_once():
    """确保后台任务只启动一次"""
    global background_tasks_started
    with background_tasks_lock:
        if not background_tasks_started:
            logger.info("start_init_bg_task...")
            start_background_tasks()
            background_tasks_started = True


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

    @app.route('/webfonts/<path:file_name>')
    def get_webfonts_file(file_name):
        font_file_name = f"webfonts/{file_name}"
        return get_static_file(font_file_name)

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
        logger.info(f"{uid}, return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, **ctx)

    @app.route('/docx/my/task', methods=['POST'])
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
                app_source=AppType.DOCX.name.lower(),
                warning_info=warning_info

            ))
        # logger.info(f"{uid}, get_my_docx_task, {data}")
        task_list = docx_meta_util.get_user_task_list(uid)
        return json.dumps(task_list, ensure_ascii=False), 200

    @app.route('/docx/statistic/index', methods=['GET'])
    def get_statistic_report_index():
        """
        获取系统运营的页面
        """
        logger.info(f"get_statistic_report_index, {request.args}")
        uid = request.args.get('uid')
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

    @app.route('/docx/statistic/report', methods=['POST'])
    def get_statistic_report():
        """
        统计用户的系统使用数据
        """
        data = request.json
        uid = int(data.get('uid'))
        logger.info(f"{uid}, get_statistic_report, {data}")
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
        statistics_list = statistic_util.get_statistics_list()
        return json.dumps(statistics_list, ensure_ascii=False), 200

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
        uid = request.json.get("uid")
        logger.info(f"{uid}, gen_doc_outline {request.json}")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return jsonify(warning_info), 400
        doc_type = request.json.get("doc_type")
        doc_title = request.json.get("doc_title")
        keywords = request.json.get("keywords")
        if not doc_type or not doc_title:
            err_info = {"error": "未提交待写作文档的标题或文档类型，请补充"}
            logger.error(f"{uid}, gen_doc_outline_err, {err_info}")
            return jsonify(err_info), 400
        return Response(
            stream_with_context(gen_docx_outline_stream(uid, doc_type, doc_title, keywords, my_cfg)),
            mimetype='text/event-stream',
            status=200,
        )

    @app.route('/docx/upload', methods=['POST'])
    def upload_docx_template_file():
        """
        上传 Word docx 写作文档模板，需要包含三级目录
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
                app_source=AppType.DOCX.name.lower(),
                warning_info=warning_info

            ))
        if file.filename == '':
            return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

        # 生成任务ID， 使用毫秒数
        task_id = int(time.time() * 1000)
        filename = f"{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        logger.info(f"{uid}, upload_file_saved_as {filename}, {task_id}")
        outline = get_outline_txt(save_path)
        logger.info(f"{uid}, get_file_outline, task_id {task_id}, {outline}")
        info = {
            "task_id": task_id,
            "file_name": filename,
            "outline": outline
        }
        logger.info(f"{uid}, upload_docx_template_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route("/docx/write/outline", methods=['POST'])
    def write_doc_with_outline_txt():
        """
        按照提供的三级目录文本,生成 docx 文档模板，这里的文档模板只有目录（默认三级），具体的段落中没有写作要求
        文档目录参数 doc_outline 传递的文本格式如下： 1.标题1 \n1.1 标题1.1 \n1.2 标题1.2
        """
        data = request.json
        uid = data.get("uid")
        logger.info(f"{uid}, write_doc_with_outline_txt, data, {data}")
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
        doc_title = data.get("doc_title")
        doc_outline = data.get("doc_outline")
        doc_type = data.get("doc_type")
        if not doc_type or not doc_title or not doc_outline:
            err_info = {"error": "缺少文档类型、标题、目录参数中的一个或多个"}
            logger.error(f"{uid}, err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400
        task_id = int(time.time() * 1000)  # 生成任务ID， 使用毫秒数
        if data.get("vbd_id"):
            vbd_id = int(data.get("vbd_id"))
        else:
            vbd_id = None
        keywords = data.get("keywords")
        template_file_name = gen_docx_template_with_outline_txt(task_id, UPLOAD_FOLDER, doc_title,
                                                                          doc_outline)
        logger.info(f"{uid}, docx_template_file_generated_with_name, {template_file_name}")
        docx_meta_util.save_docx_file_info(
            uid, task_id, doc_type, doc_title, keywords, template_file_name, vbd_id, False
        )
        threading.Thread(
            target=process_doc,
            args=(uid, task_id, doc_type, doc_title, keywords, template_file_name, vbd_id, False)
        ).start()
        info = {"status": "started", "task_id": task_id}
        logger.info(f"{uid}, write_doc_with_outline_txt, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route("/docx/write/template", methods=['POST'])
    def write_doc_with_template():
        """
        按照一定的 Word 文件模板, 生成文档
        在word文档模板中，有三级目录，在每个小节中，有用户提供的写作要求
        """
        data = request.json
        uid = data.get("uid")
        logger.info(f"{uid}, write_doc_with_template, {data}")
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
        task_id = int(data.get("task_id"))
        doc_type = data.get("doc_type")
        doc_title = data.get("doc_title")

        if not doc_type or not doc_title:
            err_info = {"error": "文档类型或文档标题不能为空"}
            logger.error(f"{uid}, err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400
        template_file_name = data.get("file_name")

        keywords = data.get("keywords")
        if data.get("vbd_id"):
            vbd_id = int(data.get("vbd_id"))
        else:
            vbd_id = None
        if not task_id or not template_file_name or not uid:
            err_info = {"error": "缺少任务ID、写作模板文件名称和用户ID中的一个或多个"}
            logger.error(f"{uid}, err_occurred, {err_info}")
            return jsonify(err_info), 400
        docx_meta_util.save_docx_file_info(
            uid, task_id, doc_type, doc_title, keywords, template_file_name, vbd_id, True
        )
        threading.Thread(
            target=process_doc,
            args=(uid, task_id, doc_type, doc_title, keywords, template_file_name, vbd_id, True)
        ).start()

        info = {"status": "started", "task_id": task_id}
        logger.info(f"{uid}, write_doc_with_docx_template, {info}")
        return json.dumps(info, ensure_ascii=False), 200

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
        logger.info(f"{uid}, 文件检查 - 绝对路径: {absolute_path}")

        if not os.path.exists(absolute_path):
            logger.error(f"{uid}, 文件不存在: {absolute_path}")
            abort(404)

        logger.info(f"{uid}, 文件找到，准备发送: {absolute_path}")
        try:
            from flask import send_file
            return send_file(
                absolute_path,
                as_attachment=True,
                download_name=filename,
                mimetype=DOCX_MIME_TYPE,
            )
        except Exception as e:
            logger.error(f"{uid}, 文件发送失败: {str(e)}")
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
        logger.info(f"{uid}, 文件检查 - 相对路径: {file_path}")
        logger.info(f"{uid}, 文件检查 - 绝对路径: {absolute_path}")
        logger.info(f"{uid}, 文件检查 - UPLOAD_FOLDER: {UPLOAD_FOLDER}")
        logger.info(f"{uid}, 文件检查 - 当前工作目录: {os.getcwd()}")
        if not os.path.exists(absolute_path):
            logger.error(f"{uid}, 文件不存在: {absolute_path}")
            abort(404)

        if not os.access(absolute_path, os.R_OK):
            logger.error(f"{uid}, 文件不可读: {absolute_path}")
            abort(403)
        logger.info(f"{uid}, 文件找到，准备发送: {absolute_path}")
        try:
            from flask import send_file
            logger.info(f"{uid}, 使用 send_file 发送: {absolute_path}")
            return send_file(
                absolute_path,
                as_attachment=True,
                download_name=filename,
                mimetype=DOCX_MIME_TYPE,
            )
        except Exception as e:
            logger.error(f"{uid}, 文件发送失败: {str(e)}")
            abort(500)

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
        docx_meta_util.delete_task(task_id)

        return json.dumps({"msg": "删除成功", "task_id": task_id}, ensure_ascii=False), 200

    @app.route('/docx/process/info', methods=['POST'])
    def get_doc_process_info():
        # logger.info(f"get_doc_process_info {request}")
        task_id = request.json.get("task_id")
        uid = request.json.get("uid")
        if not task_id or not uid:
            return jsonify({"error": "缺少任务ID或用户ID"}), 400
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
        file_info = docx_meta_util.get_docx_file_info(task_id)
        logger.info(f"{uid}, get_docx_file_info, {file_info}")
        if not file_info or len(file_info) == 0:
            return json.dumps({"error": "未找到任务ID对应的文档信息"}, ensure_ascii=False), 400
        file_info[0]['elapsed_time'] = time.time() - task_id
        # logger.info(f"get_doc_process_info, {info}")
        return json.dumps(file_info, ensure_ascii=False), 200


def start_background_tasks():
    """启动后台任务线程"""
    if my_cfg['sys'].get('debug_mode', False):
        logger.warning("system_in_debug_mode_background_task_exit")
        return

    def _start_tasks():
        # 等待应用完全启动
        time.sleep(2)
        logger.info("Starting background tasks...")

        # 启动文档清理任务
        doc_clean_thread = threading.Thread(target=clean_docx_task, daemon=True, name="clean_docx_task")
        doc_clean_thread.start()

        # 启动VDB清理任务
        vdb_clean_thread = threading.Thread(target=clean_expired_vdb_file_task, daemon=True, name="vdb_clean_task")
        vdb_clean_thread.start()

        # 启动VDB处理任务
        vdb_process_thread = threading.Thread(target=process_vdb_file_task, daemon=True, name="vdb_process_task")
        vdb_process_thread.start()

        logger.info("all_bg_tasks_started")

    # 在新线程中启动后台任务，避免阻塞主线程
    threading.Thread(target=_start_tasks, daemon=True).start()


def clean_docx_task():
    """清理过期的文档任务"""
    while True:
        try:
            now = time.time()
            docx_list = docx_meta_util.get_processing_file_list()
            # 遍历所有任务
            for file in docx_list:
                task_id = file.get('task_id')
                if task_id is None:
                    # logger.warning(f"无效task_id：{task_id}, file: {file}")
                    continue
                if now - task_id > TASK_EXPIRE_TIME_MS:  # 2小时过期
                    logger.info(f"Cleaning expired task: {task_id}")
                    docx_meta_util.delete_task(task_id)

            time.sleep(1000)  # 每1000秒检查一次
        except Exception as e:
            logger.error(f"Error in clean_docx_tasks: {e}")
            time.sleep(60)  # 出错后等待1分钟再重试


def process_doc(uid: int, task_id: int, doc_type: str, doc_title: str, keywords: str,
    file_name: str, vbd_id: int, is_include_para_txt=False):
    """
    处理 Word 文档
    :param uid:                 用户ID
    :param task_id:             任务ID
    :param doc_type:            docx 文档内容类型
    :param doc_title:           docx 文档的标题
    :param keywords:            其他的写作要求
    :param file_name:           Word template 模板文件名, 其中包含三级目录，可能含有段落写作的提示词，也可能没有
    :param vbd_id:              vector db id.
    :param is_include_para_txt: Word 文档中各小节（章节标题下）是否包含有描述性的文本
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {doc_title}, keywords: {keywords}, "
        f"task_id: {task_id}, file_name: {file_name}, vbd_id:{vbd_id}, is_include_para_txt: {is_include_para_txt}")

    generator = None
    try:
        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始解析文档结构...", 0)
        full_file_name = os.path.join(UPLOAD_FOLDER, file_name)
        catalogue = extract_catalogue(full_file_name)
        docx_meta_util.save_outline_by_task_id(task_id, catalogue)
        output_file_name = f"output_{task_id}.docx"
        output_file = os.path.join(UPLOAD_FOLDER, output_file_name)
        logger.info(f"{uid},{task_id}, doc_output_file_name, {output_file_name}")
        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始处理文档...")
        doc_ctx = f"我正在写一个 {doc_type} 类型的文档, 文档标题是 {doc_title}"
        if keywords:
            doc_ctx = doc_ctx + f", 其他写作要求是 {keywords}"
        if vbd_id:
            vdb_info = VdbMeta.get_vdb_by_id(vbd_id)
            logger.info(f"{uid}, {task_id}, vdb_info: {vdb_info}")
        else:
            vdb_info = None
        if vdb_info:
            my_vdb_dir = f"{VDB_PREFIX}{uid}_{vdb_info[0]['id']}"
        else:
            my_vdb_dir = ""
        logger.info(f"{uid}, {task_id}, my_vdb_dir_for_gen_doc, {my_vdb_dir}")
        generator = DocxEditor()
        para_comment_dict = get_comments_dict(full_file_name)
        if para_comment_dict:
            logger.info(f"{uid}, {task_id}, fill_doc_with_comment, {full_file_name}")
            logger.debug(f"{uid}, {task_id}, fill_doc_with_comment, {full_file_name}， comment_dict, {para_comment_dict}")
            generator.modify_doc_with_comment(
                uid, task_id, doc_ctx, full_file_name, catalogue, my_vdb_dir, my_cfg, output_file, para_comment_dict
            )
        elif is_include_para_txt:
            logger.info(f"{uid}, {task_id}, fill_doc_with_para_content, {full_file_name}")
            generator.fill_doc_with_prompt(
                uid, task_id, doc_ctx, full_file_name, catalogue, my_vdb_dir, my_cfg, output_file
            )
        else:
            logger.info(f"{uid}, {task_id}, fill_doc_without_para_content, {full_file_name}")
            generator.fill_doc_without_prompt(
                uid, task_id, doc_ctx, full_file_name, catalogue, my_vdb_dir, my_cfg, output_file
            )
        generator.shutdown()
    except Exception as e:
        docx_meta_util.update_process_info_by_task_id(uid, task_id, f"任务处理失败: {str(e)}")
        logger.exception(f"{uid}, {task_id}, fill_doc_err", e)
    finally:
        # 确保资源被释放
        if generator:
            generator.shutdown()


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