#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
项目评审数字专家
pip install gunicorn flask concurrent-log-handler langchain_openai \
 langchain_core langchain_community tabulate pycryptodome
"""
import json
import logging.config
import os
import time
import threading

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, redirect, abort, url_for, send_from_directory, render_template
from apps.eval_expert.eval_expert_agent import EvalExpertAgent
from common.my_enums import AppType
from common.sys_init import init_yml_cfg
from common.bp_auth import auth_bp, auth_info, get_client_ip, SESSION_TIMEOUT
from common.bp_vdb import vdb_bp, clean_expired_vdb_file_task, process_vdb_file_task
from common.cm_utils import get_console_arg1
from common import statistic_util, my_enums

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

my_cfg = init_yml_cfg()
os.system(
    "unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy"
)

# 全局变量，用于存储后台任务状态
background_tasks_started = False
background_tasks_lock = threading.Lock()

UPLOAD_FOLDER = 'upload_doc'

def create_app():
    """应用工厂函数"""
    app = Flask(__name__, static_folder=None)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config['JSON_AS_ASCII'] = False
    app.config['MY_CFG'] = my_cfg

    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(vdb_bp)

    # 注册路由
    register_routes(app)

    # 在应用启动时初始化后台任务（使用应用上下文）
    # with app.app_context():
    #     start_background_tasks_once()

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
        return redirect(url_for('auth.login_index', app_source=AppType.EVAL_EXPERT.name.lower()))


    @app.route('/chat/statistic/index', methods=['GET'])
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
                app_source=AppType.EVAL_EXPERT.name.lower(),
                warning_info=warning_info
            ))
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
        logger.info(f"{uid}, return_statistics_page {dt_idx}")
        return render_template(dt_idx, **ctx)

    @app.route('/chat/statistic/report', methods=['POST'])
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
                app_source=AppType.EVAL_EXPERT.name.lower(),
                warning_info=warning_info
            ))
        statistics_list = statistic_util.get_statistics_list()
        return json.dumps(statistics_list, ensure_ascii=False), 200

    @app.route('/chat', methods=['POST'])
    def chat(catch=None):
        """
        curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/chat' \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -d '{"msg":"who are you?"}'
        :return a string
        """
        logger.info(f"chat_request {request.form}")
        msg = request.form.get('msg', "").strip()
        uid = request.form.get('uid')
        file_infos = request.form.get('file_infos')
        if not file_infos:
            warning_info = f"缺少评审文件信息，请上传后再试"
            logger.error(f"{warning_info}, {msg}, {uid}")
            return warning_info

        if not uid:
            warning_info = f"缺少用户身份信息，请您检查后再试"
            logger.error(f"{warning_info}, {msg}, {uid}")
            return warning_info

        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户登录信息已失效，请重新登录后再使用本系统"
            logger.error(f"{warning_info}, {uid}")
            return warning_info

        logger.info(f"rcv_msg, {msg}, uid {uid}")
        auth_info[session_key] = time.time()
        logger.info(f"request_file_infos, {file_infos}")
        file_infos = json.loads(file_infos)
        eval_expert = EvalExpertAgent(my_cfg)
        categorize_files = eval_expert.categorize_files(file_infos)
        logger.info(f"categorize_files, {categorize_files}")
        # 处理文件内容
        review_criteria_msg = eval_expert.get_file_path_msg(categorize_files, "review_criteria")
        project_materials_msg = eval_expert.get_file_path_msg(categorize_files, "project_materials")
        def generate_stream():
            full_response = ""
            stream_input = {
                "domain": "燃气行业",
                "review_criteria_file": review_criteria_msg,
                "project_material_file": project_materials_msg,
                "msg": msg
            }
            logger.info(f"stream_input {stream_input}")
            for chunk in eval_expert.get_chain().stream(stream_input):
                full_response += chunk
                yield chunk
            logger.info(f"full_response: {full_response}")

        return app.response_class(generate_stream(), mimetype='text/event-stream')




    @app.route('/upload', methods=['POST'])
    def upload_file():
        """
        单个文件上传
        """
        logger.info(f"upload_file, {request}")
        if 'file' not in request.files:
            return json.dumps({"error": "未找到上传的文件信息"}, ensure_ascii=False), 400
        file = request.files['file']
        uid = int(request.form.get('uid'))
        logger.info(f"{uid}, upload_file")
        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None)
                or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            warning_info = "用户会话信息已失效，请重新登录"
            logger.warning(f"{uid}, {warning_info}")
            return json.dumps({"error": f"{warning_info}"}, ensure_ascii=False), 400
        if file.filename == '':
            return json.dumps({"error": "上传文件的文件名为空"}, ensure_ascii=False), 400

        # 生成任务ID， 使用毫秒数
        file_id = int(time.time() * 1000)
        file_name = f"{file_id}_{file.filename}"
        save_path = os.path.join(UPLOAD_FOLDER, file_name)
        file.save(save_path)
        logger.info(f"{uid}, upload_file_saved_as {file_name}, {file_id}")
        info = {
            "file_id": file_id,
            "file_name": file_name,
        }
        logger.info(f"{uid}, file_uploaded, {info}")
        return json.dumps(info, ensure_ascii=False), 200

def start_background_tasks():
    """启动后台任务线程"""
    if my_cfg['sys'].get('debug_mode', False):
        logger.warning("system_in_debug_mode_background_task_exit")
        return

    def _start_tasks():
        # 等待应用完全启动
        time.sleep(2)
        logger.info("Starting background tasks...")

        # 启动VDB清理任务
        vdb_clean_thread = threading.Thread(target=clean_expired_vdb_file_task, daemon=True, name="vdb_clean_task")
        vdb_clean_thread.start()

        # 启动VDB处理任务
        vdb_process_thread = threading.Thread(target=process_vdb_file_task, daemon=True, name="vdb_process_task")
        vdb_process_thread.start()

        logger.info("all_bg_tasks_started")

    # 在新线程中启动后台任务，避免阻塞主线程
    threading.Thread(target=_start_tasks, daemon=True).start()


# 创建应用实例
app = create_app()

# 当直接运行脚本时，启动开发服务器
if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    logger.info(f"my_cfg {my_cfg.get('db')},\n{my_cfg.get('api')}")
    app.config['ENV'] = 'dev'
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)