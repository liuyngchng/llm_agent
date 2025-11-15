#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
项目评审数字专家
pip install gunicorn flask concurrent-log-handler requests \
 pycryptodome
"""
import asyncio
import json
import logging.config
import os
import time
import threading
from datetime import datetime

from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, request, redirect, abort, url_for, send_from_directory, render_template, Response
from apps.eval_expert.agent import EvalExpertAgent
from common.docx_util import get_md_file_content
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

    @app.route('/chat/stream', methods=['POST'])
    def chat_stream():
        """新的流式聊天接口"""
        logger.info(f"chat_stream_request {request.form}")
        msg = request.form.get('msg', "").strip()
        uid = request.form.get('uid')
        file_infos = request.form.get('file_infos')

        # 验证逻辑
        if not file_infos:
            return json.dumps({"error": "缺少评审文件信息"}, ensure_ascii=False), 400

        if not uid:
            return json.dumps({"error": "缺少用户身份信息"}, ensure_ascii=False), 400

        session_key = f"{uid}_{get_client_ip()}"
        if (not auth_info.get(session_key, None) or
                time.time() - auth_info.get(session_key) > SESSION_TIMEOUT):
            return json.dumps({"error": "用户登录信息已失效"}, ensure_ascii=False), 401

        logger.info(f"rcv_msg, {msg}, uid {uid}")
        auth_info[session_key] = time.time()

        def generate():
            try:
                # 初始化agent
                eval_expert = EvalExpertAgent(my_cfg)

                # 在生成器内部运行异步代码
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # 处理文件分类
                file_info_list = json.loads(file_infos)
                categorize_files = eval_expert.categorize_files(file_info_list)
                logger.info(f"categorize_files, {categorize_files}")

                # 处理文件内容
                review_criteria_file = eval_expert.get_file_path_msg(categorize_files, "review_criteria")
                review_criteria = ''
                for file in review_criteria_file:
                    review_criteria += get_md_file_content(file['file_path'])
                project_material_file = eval_expert.get_file_path_msg(categorize_files, "project_materials")

                stream_input = {
                    "today": datetime.now().strftime("%Y年%m月%d日"),
                    "domain": "燃气行业",
                    "review_criteria": review_criteria,
                    "project_material_file": project_material_file,
                    "msg": msg
                }

                # 使用真正的流式处理
                collected_chunks = []

                def stream_callback(chunk):
                    # 立即发送到客户端
                    data = json.dumps({'content': chunk}, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    collected_chunks.append(chunk)
                    return ""  # 确保返回字符串

                # 执行真正的流式处理 - 同步方式调用异步函数
                full_response = loop.run_until_complete(
                    real_process_with_streaming(eval_expert, stream_input, stream_callback)
                )
                loop.close()

                # 发送结束标记
                yield "data: [DONE]\n\n"

                logger.info(f"流式处理完成，总响应长度: {len(full_response)}")

            except Exception as e:
                logger.error(f"流式处理错误: {str(e)}")
                error_msg = json.dumps({'content': f"❌ 处理过程中出现错误: {str(e)}"}, ensure_ascii=False)
                yield f"data: {error_msg}\n\n"
                yield "data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')

    async def real_process_with_streaming(eval_expert, stream_input, stream_callback):
        """真正的流式处理实现"""
        try:
            if not eval_expert.tools:
                await eval_expert.initialize_tools()

            # 构建提示词
            prompt = eval_expert.build_prompt(stream_input)

            # 发送开始处理消息
            stream_callback("🚀 开始处理您的请求...\n\n")

            # 调用LLM API（真正的流式）
            response = await eval_expert.real_call_llm_api_stream(prompt, stream_callback)

            # 检查响应中是否包含工具调用
            tool_calls = eval_expert.extract_tool_calls_from_response(response)

            if tool_calls:
                stream_callback(f"\n🔧 检测到 {len(tool_calls)} 个工具调用，开始执行...\n\n")
                logger.info(f"检测到工具调用: {len(tool_calls)} 个")
                final_response = await eval_expert.real_handle_tool_calls_stream(tool_calls, stream_input,
                                                                                 stream_callback)
                return final_response
            else:
                logger.info("未检测到工具调用，直接返回响应内容")
                return response

        except Exception as e:
            error_msg = f"❌ 处理过程中出现错误: {str(e)}"
            logger.error(f"工具处理过程中出错: {str(e)}")
            stream_callback(error_msg)
            return error_msg



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