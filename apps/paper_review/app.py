#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
AI 数字评委
pip install flask
"""
import json
import logging.config
import os
import threading
import time

from flask import (Flask, request, jsonify, send_from_directory,
                   abort, redirect, url_for, render_template)

from common import docx_meta_util
from common.docx_para_util import extract_catalogue, get_outline_txt
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
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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

    @app.route('/webfonts/<path:file_name>')
    def get_webfonts_file(file_name):
        font_file_name = f"webfonts/{file_name}"
        return get_static_file(font_file_name)

    @app.route('/')
    def app_home():
        logger.info("redirect_auth_login_index")
        return redirect(url_for('auth.login_index', app_source=my_enums.AppType.PAPER_REVIEW.name.lower()))

    @app.route('/xlsx/upload', methods=['POST'])
    def upload_xlsx_criteria_file():
        """
        上传 Excel xlsx 评审标准文件
        """
        logger.info(f"upload_xlsx_criteria_file, {request}")
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
        filename = f"criteria_{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        logger.info(f"criteria_file_saved_as {filename}, {task_id}")

        info = {
            "task_id": task_id,
            "file_name": filename,
            "message": "评审标准文件上传成功"
        }
        logger.info(f"upload_xlsx_criteria_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route('/docx/upload', methods=['POST'])
    def upload_docx_review_file():
        """
        上传 Word docx 评审材料文档
        """
        logger.info(f"upload_docx_review_file, {request}")
        if 'file' not in request.files:
            return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
        file = request.files['file']
        uid = int(request.form.get('uid'))
        logger.info(f"{uid}, upload_docx_review_file")
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
        filename = f"review_{task_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        logger.info(f"review_file_saved_as {filename}, {task_id}")

        # 提取文档大纲
        outline = get_outline_txt(save_path)
        logger.info(f"get_file_outline,task_id {task_id}, {outline}")

        info = {
            "task_id": task_id,
            "file_name": filename,
            "outline": outline,
            "message": "评审材料文件上传成功"
        }
        logger.info(f"upload_docx_review_file, {info}")
        return json.dumps(info, ensure_ascii=False), 200

    @app.route("/review_report/gen", methods=['POST'])
    def gen_review_report():
        """
        生成评审报告
        """
        data = request.json
        uid = data.get("uid")
        logger.info(f"{uid}, gen_review_report_dt, {data}")
        statistic_util.add_access_count_by_uid(int(uid), 1)
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return jsonify(warning_info), 400

        task_id = int(data.get("task_id"))
        doc_title = data.get("doc_title")
        review_criteria_file_name = data.get("review_criteria_file_name")
        review_paper_file_name = data.get("review_paper_file_name")

        # 验证输入
        if not doc_title:
            err_info = {"error": "评审主题不能为空"}
            logger.error(f"err_occurred, {err_info}")
            return json.dumps(err_info, ensure_ascii=False), 400

        if not task_id or not review_criteria_file_name or not review_paper_file_name or not uid:
            err_info = {"error": "缺少任务ID、评审标准文件、评审材料文件或用户ID"}
            logger.error(f"err_occurred, {err_info}")
            return jsonify(err_info), 400

        # 保存任务信息到数据库
        doc_type = my_enums.WriteDocType.REVIEW_REPORT.value
        docx_meta_util.save_docx_file_info(uid, task_id, doc_type, doc_title,
                                           "", review_paper_file_name, 0, False)

        # 启动后台任务
        threading.Thread(
            target=generate_review_report,
            args=(uid, doc_type, doc_title, task_id, review_criteria_file_name, review_paper_file_name)
        ).start()

        info = {"status": "started", "task_id": task_id}
        logger.info(f"generate_review_report, {info}")
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
                app_source=AppType.paper_review.name.lower(),
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
                app_source=AppType.paper_review.name.lower(),
                warning_info=warning_info
            ))
        logger.info(f"{uid}, get_my_paper_review_task, {data}")
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
                app_source=AppType.DOCX.name.lower(),
                warning_info=warning_info
            ))
        statistic_util.add_access_count_by_uid(int(uid), 1)
        filename = f"output_{task_id}.docx"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        absolute_path = os.path.abspath(file_path)
        logger.info(f"文件检查 - 绝对路径: {absolute_path}")

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


def generate_review_report(uid: int, doc_type: str, doc_title: str, task_id: int,
                           review_criteria_file_name: str, review_paper_file_name: str):
    """
    生成评审报告
    :param uid: 用户ID
    :param doc_type: 文档类型
    :param doc_title: 文档标题
    :param task_id: 任务ID
    :param review_criteria_file_name: 评审标准文件名
    :param review_paper_file_name: 评审材料文件名
    """
    logger.info(f"uid: {uid}, doc_type: {doc_type}, doc_title: {doc_title}, "
                f"task_id: {task_id}, criteria_file: {review_criteria_file_name}, "
                f"review_file: {review_paper_file_name}")
    try:
        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始解析评审标准...", 0)

        # 解析评审标准Excel文件
        criteria_file_path = os.path.join(UPLOAD_FOLDER, review_criteria_file_name)
        # TODO: 添加解析Excel评审标准的代码
        # criteria_data = parse_criteria_excel(criteria_file_path)

        docx_meta_util.update_process_info_by_task_id(uid, task_id, "开始分析评审材料...", 30)

        # 解析评审材料Word文档
        review_file_path = os.path.join(UPLOAD_FOLDER, review_paper_file_name)
        catalogue = extract_catalogue(review_file_path)
        docx_meta_util.save_outline_by_task_id(task_id, catalogue)

        docx_meta_util.update_process_info_by_task_id(uid, task_id, "生成评审报告...", 60)

        # TODO: 根据评审标准和评审材料生成评审报告
        # 这里调用你的AI评审逻辑
        # review_result = generate_ai_review(criteria_data, review_file_path)

        # 生成输出文件
        output_file_name = f"output_{task_id}.docx"
        output_file = os.path.join(UPLOAD_FOLDER, output_file_name)

        # TODO: 将评审结果写入Word文档
        # write_review_to_doc(review_result, output_file)

        # 暂时复制原文件作为示例
        import shutil
        shutil.copy2(review_file_path, output_file)

        docx_meta_util.update_process_info_by_task_id(uid, task_id, "评审报告生成完毕", 100)

    except Exception as e:
        docx_meta_util.update_process_info_by_task_id(uid, task_id, f"任务处理失败: {str(e)}")
        logger.exception("评审报告生成异常", e)


# 创建应用实例
app = create_app()

# 当直接运行脚本时，启动开发服务器
if __name__ == '__main__':
    port = get_console_arg1()
    app.run(host='0.0.0.0', port=port)