#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
AI 数字评委
pip install flask
"""
import hashlib
import json
import logging.config
import os
import threading
import time

from flask import (Flask, request, jsonify, send_from_directory,
                   abort, redirect, url_for, render_template, Response)

from apps.paper_review.paper_reviewer import generate_review_report
from common import docx_meta_util
from common.cfg_util import save_file_info, get_file_info
from common.docx_md_util import convert_docx_to_md, get_md_file_content
from common import my_enums, statistic_util
from common.docx_meta_util import get_doc_info
from common.html_util import convert_md_to_html_with_css, get_html_ctx_from_md, convert_markdown_to_html
from common.my_enums import AppType, FileType
from common.sys_init import init_yml_cfg
from common.bp_auth import auth_bp, get_client_ip, auth_info
from common.cm_utils import get_console_arg1
from common.xlsx_md_util import convert_xlsx_to_md
from common.const import SESSION_TIMEOUT, UPLOAD_FOLDER, OUTPUT_DIR, TASK_EXPIRE_TIME_MS, DOCX_MIME_TYPE, XLSX_MIME_TYPE

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)


def create_app():
    """应用工厂函数"""
    app = Flask(__name__, static_folder=None)
    app.config['JSON_AS_ASCII'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['TASK_EXPIRE_TIME_MS'] = TASK_EXPIRE_TIME_MS
    app.config['CFG'] = my_cfg
    app.config['APP_SOURCE'] = my_enums.AppType.PAPER_REVIEW.name.lower()
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

    @app.route('/webfonts/<path:file_name>')
    def get_webfonts_file(file_name):
        font_file_name = f"webfonts/{file_name}"
        return get_static_file(font_file_name)

    @app.route('/')
    def app_home():
        logger.info("redirect_auth_login_index")
        return redirect(url_for('auth.login_index', app_source=my_enums.AppType.PAPER_REVIEW.name.lower()))

    @app.route('/xlsx/upload', methods=['POST'])
    def upload_xlsx():
        """
        上传 Excel xlsx 评审标准文件
        """
        logger.info(f"upload_xlsx_file, {request}")
        if 'file' not in request.files:
            return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
        file = request.files['file']
        uid = int(request.form.get('uid'))
        logger.info(f"{uid}, upload_xlsx_criteria_file")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.PAPER_REVIEW.name.lower(),
                warning_info=warning_info
            ))
        if file.filename == '':
            return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

        # 生成任务ID，使用毫秒数
        task_id = int(time.time() * 1000)
        filename = f"{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        md_file = convert_xlsx_to_md(save_path, True, True)
        file_md5 = hashlib.md5(md_file.encode('utf-8')).hexdigest()
        save_file_info(uid, file_md5, md_file, FileType.XLSX.value)
        logger.info(f"xlsx_file {file.filename} saved_as {file_md5}, {task_id}")

        info = {
            "task_id": task_id,
            "file_name": file_md5,
            "message": "xlsx 文件上传成功"
        }
        logger.info(f"upload_xlsx_criteria_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route('/docx/upload', methods=['POST'])
    def upload_docx():
        """
        上传 Word docx 评审材料文档
        """
        logger.info(f"upload_docx, {request}")
        if 'file' not in request.files:
            return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
        file = request.files['file']
        uid = int(request.form.get('uid'))
        logger.info(f"{uid}, upload_docx")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.PAPER_REVIEW.name.lower(),
                warning_info=warning_info
            ))
        if file.filename == '':
            return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

        # 生成任务ID，使用毫秒数
        task_id = int(time.time() * 1000)
        filename = f"{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        md_file = convert_docx_to_md(save_path, True)
        file_md5 = hashlib.md5(md_file.encode('utf-8')).hexdigest()
        save_file_info(uid, file_md5, md_file, FileType.DOCX.value)
        logger.info(f"docx_file {file.filename} saved_as {file_md5}, {task_id}")

        info = {
            "task_id": task_id,
            "file_name": file_md5,
            "message": "docx 文件上传成功"
        }
        logger.info(f"upload_docx_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route('/md/upload', methods=['POST'])
    def upload_markdown():
        """
        上传 Word docx 评审材料文档
        """
        logger.info(f"upload_markdown, {request}")
        if 'file' not in request.files:
            return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
        file = request.files['file']
        uid = int(request.form.get('uid'))
        logger.info(f"{uid}, upload_docx")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.PAPER_REVIEW.name.lower(),
                warning_info=warning_info
            ))
        if file.filename == '':
            return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

        # 生成任务ID，使用毫秒数
        task_id = int(time.time() * 1000)
        filename = f"{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        md_file = os.path.abspath(save_path)
        file_md5 = hashlib.md5(md_file.encode('utf-8')).hexdigest()
        save_file_info(uid, file_md5, md_file, FileType.MARKDOWN.value)
        logger.info(f"md_file {file.filename} saved_as {file_md5}, {task_id}")

        info = {
            "task_id": task_id,
            "file_name": file_md5,
            "message": "markdown 文件上传成功"
        }
        logger.info(f"upload_md_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route("/review_report/gen", methods=['POST'])
    def gen_review_report():
        """
        生成评审报告
        """
        data = request.json
        uid = int(data.get("uid"))
        logger.info(f"{uid}, gen_review_report_dt, {data}")
        statistic_util.add_access_count_by_uid(int(uid), 1)
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return jsonify(warning_info), 400

        task_id = int(data.get("task_id"))
        review_topic = data.get("review_topic")
        review_type = data.get("review_type")
        review_criteria_file_id = data.get("review_criteria_file_name")
        review_paper_file_id = data.get("review_paper_file_name")

        # 验证输入
        if not review_topic:
            err_info = {"error": "评审主题不能为空"}
            logger.error(f"err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400
        if not review_type:
            err_info = {"error": "评审类别不能为空"}
            logger.error(f"err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400

        if not task_id or not review_criteria_file_id or not review_paper_file_id or not uid:
            err_info = {"error": "缺少任务ID、评审标准文件、评审材料文件或用户ID"}
            logger.error(f"err_occurred, {err_info}")
            return jsonify(err_info), 400
        review_paper_file_info = get_file_info(uid, review_paper_file_id)
        if not review_paper_file_info:
            err_info = {"error": f"未找到相应的评审文件信息 {review_paper_file_id}"}
            logger.error(f"err_occurred, {err_info}")
            return jsonify(err_info), 400

        review_criteria_file_info = get_file_info(uid, review_criteria_file_id)
        if not review_criteria_file_info:
            err_info = {"error": f"未找到相应的评审文件信息 {review_criteria_file_info}"}
            logger.error(f"err_occurred, {err_info}")
            return jsonify(err_info), 400

        docx_ctx = f"我正在做一个 {review_type} 的评审，评审主题是 {review_topic}"
        output_file_name = f"{OUTPUT_DIR}/output_{task_id}.md"
        output_file_path = os.path.abspath(output_file_name)
        criteria_file = review_criteria_file_info[0]['full_path']
        criteria_file_type = review_criteria_file_info[0]['file_suffix']
        paper_file = review_paper_file_info[0]['full_path']
        docx_meta_util.save_doc_info(
            uid, task_id, review_type, review_topic, criteria_file, "",paper_file ,
            0, False, docx_ctx, output_file_path, "",
            output_file_type=criteria_file_type
        )

        # 启动后台任务
        threading.Thread(
            target=generate_review_report,
            args=(uid, task_id, review_type, review_topic,  criteria_file, paper_file, criteria_file_type, my_cfg)
        ).start()

        info = {"status": "started", "task_id": task_id}
        logger.info(f"generate_propose, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route('/paper_review/task', methods=['GET'])
    def docx_task_index():
        """
        获取当前在进行的写作任务，渲染页面
        """
        logger.info(f"paper_review_index, {request.args}")
        uid = request.args.get('uid')
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.PAPER_REVIEW.name.lower(),
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
        dt_idx = "paper_review_my_task.html"
        logger.info(f"{uid}, return_page_with_no_auth {dt_idx}")
        return render_template(dt_idx, **ctx)

    @app.route('/paper_review/my/task', methods=['POST'])
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
            return redirect(url_for(
                'auth.login_index',
                app_source=AppType.PAPER_REVIEW.name.lower(),
                warning_info=warning_info
            ))
        # logger.info(f"{uid}, get_my_paper_review_task, {data}")
        task_list = docx_meta_util.get_user_task_list(uid)
        return json.dumps(task_list, ensure_ascii=False), 200

    @app.route('/paper_review/download/task/<task_id>', methods=['GET'])
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
                app_source=AppType.PAPER_REVIEW.name.lower(),
                warning_info=warning_info
            ))
        statistic_util.add_access_count_by_uid(int(uid), 1)
        file_path_info = get_doc_info(task_id)
        logger.debug(f"{task_id}, {file_path_info}")
        absolute_path = file_path_info[0]['output_file_path']
        output_file_type = file_path_info[0]['output_file_type']
        output_file_suffix = ".docx"
        mimetype = DOCX_MIME_TYPE
        if FileType.XLSX.value == output_file_type:
            output_file_suffix = ".xlsx"
            mimetype = XLSX_MIME_TYPE
        # 分离目录和文件名
        dir_path, filename = os.path.split(absolute_path)
        # 分离文件名和扩展名
        name, _ = os.path.splitext(filename)
        # 构建新的文件路径
        output_file_path = str(os.path.join(dir_path, name + output_file_suffix))

        print(output_file_path)
        logger.info(f"文件检查 - 绝对路径: {output_file_path}")
        if not os.path.exists(output_file_path):
            logger.error(f"文件不存在: {output_file_path}")
            abort(404)
        logger.info(f"文件找到，准备发送: {output_file_path}")
        download_name=f"{task_id}_output_paper_review_report{output_file_suffix}"
        try:
            from flask import send_file
            logger.info(f"使用 send_file 发送: {output_file_path}")
            return send_file(output_file_path, as_attachment=True, download_name=download_name,mimetype=mimetype)
        except Exception as e:
            logger.error(f"文件发送失败: {str(e)}")
            abort(500)

    @app.route('/paper_review/preview/task/<task_id>', methods=['GET'])
    def preview_file_by_task_id(task_id):
        """
        根据任务ID下载文件
        ：param task_id: 任务ID，其对应的文件名格式如下 f"output_{task_id}.docx"
        """
        uid = request.args["uid"]
        logger.info(f"{uid}, preview_file_task_id, {task_id}")
        session_key = f"{uid}_{get_client_ip()}"
        app_source = AppType.PAPER_REVIEW.name.lower()
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
        file_path_info = get_doc_info(task_id)
        logger.debug(f"{task_id}, {file_path_info}")
        absolute_path = file_path_info[0]['output_file_path']
        logger.debug(f"absolute_path, {absolute_path}")
        from pathlib import Path
        md_absolute_path = str(Path(absolute_path).with_suffix('.md'))
        html_absolute_path = str(Path(absolute_path).with_suffix('.html'))
        logger.info(f"文件检查 - 绝对路径: {md_absolute_path}")
        if not os.path.exists(md_absolute_path):
            logger.error(f"文件不存在: {md_absolute_path}")
            abort(404)
        logger.info(f"文件找到，准备发送: {md_absolute_path}")
        # html_content, toc_content = get_html_ctx_from_md(md_absolute_path)
        # ctx = {
        #     "sys_name": AppType.PAPER_REVIEW.value,
        #     "warning_info": "",
        #     "app_source": app_source,
        #     "html_content": html_content,
        #     "toc_content": toc_content,
        # }
        # dt_idx = "md.html"
        # logger.debug(f"return_page {dt_idx}")
        # return render_template(dt_idx, **ctx)
        # html_content = convert_markdown_to_html(int(uid), task_id, get_md_file_content(md_absolute_path), my_cfg)
        html_content = convert_md_to_html_with_css(md_absolute_path, "评审意见")
        logger.debug(f"return page\n{html_content}")
        return Response(html_content, mimetype='text/html')

    @app.route('/paper_review/preview/file/<file_id>', methods=['GET'])
    def preview_file_by_file_id(file_id):
        """
        根据任务ID下载文件
        ：param task_id: 任务ID，其对应的文件名格式如下 f"output_{task_id}.docx"
        """
        uid = request.args["uid"]
        logger.info(f"{uid}, preview_file_by_file_id, {file_id}")
        session_key = f"{uid}_{get_client_ip()}"
        app_source = AppType.PAPER_REVIEW.name.lower()
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
        file_path_info = get_file_info(int(uid), file_id)
        logger.debug(f"{uid}, {file_id}, {file_path_info}")
        absolute_path = file_path_info[0]['full_path']
        logger.debug(f"absolute_path, {absolute_path}")
        from pathlib import Path
        md_absolute_path = str(Path(absolute_path).with_suffix('.md'))
        logger.info(f"文件检查 - 绝对路径: {md_absolute_path}")
        if not os.path.exists(md_absolute_path):
            logger.error(f"文件不存在: {md_absolute_path}")
            abort(404)
        logger.info(f"文件找到，准备发送: {md_absolute_path}")
        html_content, toc_content = get_html_ctx_from_md(md_absolute_path)
        ctx = {
            "sys_name": AppType.PAPER_REVIEW.value,
            "warning_info": "",
            "app_source": app_source,
            "html_content": html_content,
            "toc_content": toc_content,
        }
        dt_idx = "md.html"
        logger.debug(f"return_page {dt_idx}")
        return render_template(dt_idx, **ctx)


    @app.route('/paper_review/del/task/<task_id>', methods=['GET'])
    def delete_file_info_by_task_id(task_id):
        """
        根据任务ID删除任务
        ：param task_id: 任务ID
        """
        logger.info(f"delete_file_task_id, {task_id}")
        filename = f"output_{task_id}.docx"
        disk_file = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(disk_file):
            os.remove(disk_file)
        else:
            logger.warning(f"文件 {filename} 不存在， 无需删除物理文件, 只需删除数据库记录")
        docx_meta_util.delete_task(task_id)

        return json.dumps({"msg": "删除成功", "task_id": task_id}, ensure_ascii=False), 200



# 创建应用实例
app = create_app()

# 当直接运行脚本时，启动开发服务器
if __name__ == '__main__':
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)