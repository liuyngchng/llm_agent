#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSM 知识库问答系统 — 主入口
对标 Go 版本 go_to_chat/main.go
独立运行，不依赖外部认证/统计服务。
"""
import io
import json
import logging.config
import os
import signal
import sys
import threading
import time

from flask import Flask, request, jsonify, redirect

# 配置必须在导入其他模块前加载
from apps.csm.cfg import load_config, apply_db_config
from apps.csm.store import SQLiteStore
from apps.csm.session import SessionManager
from apps.csm.kb_manager import KBManager
from apps.csm.embedding_client import EmbeddingClient
from apps.csm.handler import Handler
from apps.csm.handler.auth import AuthHandler, extract_token, parse_token

# ============================================================
# 日志初始化
# ============================================================
log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", force=True)
logger = logging.getLogger(__name__)

# ============================================================
# 全局变量
# ============================================================
my_cfg = None
meta_store = None
session_mgr = None
kb_manager = None
handler = None
background_tasks_started = False
background_tasks_lock = threading.Lock()


def create_app():
    """应用工厂函数"""
    global my_cfg, meta_store, session_mgr, kb_manager, handler

    app = Flask(__name__, static_folder=None, template_folder='templates')
    app.config['JSON_AS_ASCII'] = False

    # 添加 common/templates 到 Jinja2 搜索路径（login.html 等公共模板）
    from jinja2 import FileSystemLoader, ChoiceLoader
    common_templates = os.path.join(os.path.dirname(__file__), '../../common/templates')
    if os.path.isdir(common_templates):
        original_loader = app.jinja_loader
        app.jinja_loader = ChoiceLoader([
            original_loader if original_loader else FileSystemLoader(app.template_folder),
            FileSystemLoader(common_templates),
        ])

    # ============================================================
    # 1. 加载配置
    # ============================================================
    logger.info("加载配置文件...")
    my_cfg = load_config("cfg.yml")

    # ============================================================
    # 2. 初始化数据库
    # ============================================================
    logger.info("初始化数据库...")
    db_path = "cfg.db"
    if not os.path.exists(db_path):
        template = "cfg.db.template"
        if os.path.exists(template):
            import shutil
            shutil.copy(template, db_path)
            logger.info("从模板复制数据库: %s -> %s", template, db_path)
        else:
            logger.error("数据库文件 %s 不存在，且无模板文件 %s", db_path, template)
            sys.exit(1)

    meta_store = SQLiteStore(db_path)

    # 从数据库加载运行时配置
    db_configs = meta_store.get_all_configs()
    sys_auth = "true" if my_cfg["sys"].get("auth", True) else "false"
    meta_store.seed_default_configs(my_cfg["sys"]["name"], sys_auth)
    # 重新读取（seed 后可能已有新配置）
    db_configs = meta_store.get_all_configs()
    apply_db_config(my_cfg, db_configs)

    logger.info("系统配置: name=%s, auth=%s, api_auth=%s",
                my_cfg["sys"]["name"], my_cfg["sys"]["auth"], my_cfg["sys"].get("api_auth", True))

    # ============================================================
    # 3. 初始化会话管理器
    # ============================================================
    session_mgr = SessionManager()

    # ============================================================
    # 4. 初始化知识库管理器
    # ============================================================
    kb_manager = KBManager(my_cfg, meta_store)

    # ============================================================
    # 5. 初始化 Embedding 客户端
    # ============================================================
    emb_client = None
    if my_cfg["api"].get("embedding_api_uri") and my_cfg["api"].get("embedding_api_key"):
        try:
            emb_client = EmbeddingClient(
                my_cfg["api"]["embedding_api_uri"],
                my_cfg["api"]["embedding_api_key"],
                my_cfg["api"]["embedding_model_name"],
            )
        except Exception as e:
            logger.warning("Embedding 客户端初始化失败: %s", e)

    # ============================================================
    # 6. 初始化处理器
    # ============================================================
    handler = Handler(my_cfg, kb_manager, session_mgr, meta_store, emb_client)

    # ============================================================
    # 7. 注册路由
    # ============================================================
    register_routes(app)

    # ============================================================
    # 8. 启动后台任务
    # ============================================================
    with app.app_context():
        start_background_tasks_once()

    # ============================================================
    # 9. 优雅退出
    # ============================================================
    def graceful_shutdown(signum, frame):
        logger.info("正在关闭服务...")
        kb_manager.stop_file_worker()
        meta_store.close()
        os._exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    return app


def register_routes(app):
    """注册所有路由"""

    # ============================================================
    # 静态文件
    # ============================================================
    @app.route('/static/<path:file_name>')
    def get_static_file(file_name):
        from flask import send_from_directory
        static_dirs = [
            os.path.join(os.path.dirname(__file__), 'static'),
        ]
        # 也尝试 common/static
        common_static = os.path.join(os.path.dirname(__file__), '../../common/static')
        if os.path.exists(common_static):
            static_dirs.append(common_static)

        for static_dir in static_dirs:
            file_path = os.path.join(static_dir, file_name)
            if os.path.exists(file_path):
                return send_from_directory(static_dir, file_name)
        return "File not found", 404

    # ============================================================
    # 免认证页面路由
    # ============================================================
    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok"})

    @app.route('/login')
    def login_page():
        return handler.Auth.login_page()

    # ============================================================
    # 认证 API
    # ============================================================
    @app.route('/api/login', methods=['POST'])
    def api_login():
        return handler.Auth.login()

    @app.route('/api/logout', methods=['POST'])
    def api_logout():
        return handler.Auth.logout()

    # ============================================================
    # 需要认证的页面路由
    # ============================================================
    @app.route('/')
    @handler.Auth.require_auth
    def page_index():
        return handler.Page.index()

    @app.route('/vdb/idx')
    @handler.Auth.require_auth
    def page_vdb_index():
        return handler.Page.vdb_index()

    @app.route('/user/api')
    @handler.Auth.require_auth
    def page_user_api():
        return handler.Page.user_api_index()

    # ============================================================
    # 需要认证的 API 路由（受 api_auth 开关控制）
    # ============================================================

    @app.route('/api/chat', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_chat():
        return handler.Chat.chat()

    @app.route('/api/chat/sync', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_chat_sync():
        return handler.Chat.chat_sync()

    @app.route('/api/chat/history', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_chat_history():
        return handler.Chat.history()

    @app.route('/api/chat/clear', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_chat_clear():
        return handler.Chat.clear()

    @app.route('/api/agents', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_agents():
        return handler.Auth.get_online_agents()

    @app.route('/api/faq', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_faq_list():
        return handler.Faq.list()

    @app.route('/api/faq/match', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_faq_match():
        return handler.Faq.match()

    @app.route('/api/faq/template', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_faq_template():
        return handler.Faq.template()

    @app.route('/api/me', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_me():
        return handler.Auth.me()

    @app.route('/api/ai-agents/public', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_agents_public():
        return handler.Agent.list_public()

    @app.route('/api/ai-agents', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_agents_list():
        return handler.Agent.list()

    @app.route('/api/ai-agents', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_agents_create():
        return handler.Agent.create()

    @app.route('/api/ai-agents/<int:agent_id>', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_agents_get(agent_id):
        return handler.Agent.get(agent_id)

    @app.route('/api/ai-agents/<int:agent_id>', methods=['PUT'])
    @handler.Auth.require_api_auth
    def api_agents_update(agent_id):
        return handler.Agent.update(agent_id)

    @app.route('/api/ai-agents/<int:agent_id>', methods=['DELETE'])
    @handler.Auth.require_api_auth
    def api_agents_delete(agent_id):
        return handler.Agent.delete(agent_id)

    @app.route('/api/system-vars', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_system_vars():
        return handler.Agent.list_system_vars()

    @app.route('/api/workflows', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_workflows_public():
        return handler.Workflow.list_public()

    @app.route('/api/workflows/<int:workflow_id>', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_workflows_get(workflow_id):
        return handler.Workflow.get(workflow_id)

    @app.route('/api/classifier/test', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_classifier_test():
        return handler.Chat.test_classifier()

    @app.route('/api/config', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_config_get():
        return handler.Config.get_config()

    @app.route('/api/info', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_info():
        return handler.Config.info()

    @app.route('/api/vdb', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_vdb_list():
        return handler.Vdb.my_list()

    @app.route('/api/vdb/pub', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_vdb_pub():
        return handler.Vdb.pub_list()

    @app.route('/api/vdb', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_vdb_create():
        return handler.Vdb.create()

    @app.route('/api/vdb/<int:vdb_id>', methods=['DELETE'])
    @handler.Auth.require_api_auth
    def api_vdb_delete(vdb_id):
        return handler.Vdb.delete(vdb_id)

    @app.route('/api/vdb/<int:vdb_id>/default', methods=['PUT'])
    @handler.Auth.require_api_auth
    def api_vdb_set_default(vdb_id):
        return handler.Vdb.set_default(vdb_id)

    @app.route('/api/vdb/<int:vdb_id>/files', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_vdb_files(vdb_id):
        return handler.Vdb.file_list(vdb_id)

    @app.route('/api/vdb/<int:vdb_id>/upload', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_vdb_upload(vdb_id):
        return handler.Vdb.upload(vdb_id)

    @app.route('/api/vdb/search', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_vdb_search():
        return handler.Vdb.search()

    @app.route('/api/vdb/file/<int:file_id>/progress', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_vdb_file_progress(file_id):
        return handler.Vdb.process_info(file_id)

    @app.route('/api/vdb/file/<int:file_id>/chunks', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_vdb_file_chunks(file_id):
        return handler.Vdb.chunks(file_id)

    @app.route('/api/vdb/file/<int:file_id>/download', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_vdb_file_download(file_id):
        return handler.Vdb.download(file_id)

    @app.route('/api/vdb/file/<int:file_id>', methods=['DELETE'])
    @handler.Auth.require_api_auth
    def api_vdb_file_delete(file_id):
        return handler.Vdb.file_delete(file_id)

    # ============================================================
    # 管理员页面路由
    # ============================================================
    @app.route('/admin/config')
    @handler.Auth.require_auth
    @handler.Auth.require_admin
    def admin_config():
        return handler.Page.config_index()

    # ============================================================
    # 管理员 API 路由
    # ============================================================
    @app.route('/api/config', methods=['PUT'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_config_update():
        return handler.Config.update_config()

    @app.route('/api/config/test-models', methods=['POST'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_config_test_models():
        return handler.Config.test_models()

    @app.route('/api/faq', methods=['POST'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_faq_create():
        return handler.Faq.create()

    @app.route('/api/faq/upload', methods=['POST'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_faq_upload():
        return handler.Faq.upload()

    @app.route('/api/faq/<int:faq_id>', methods=['PUT'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_faq_update(faq_id):
        return handler.Faq.update(faq_id)

    @app.route('/api/faq/<int:faq_id>', methods=['DELETE'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_faq_delete(faq_id):
        return handler.Faq.delete(faq_id)

    @app.route('/api/faq', methods=['DELETE'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_faq_clear():
        return handler.Faq.clear_all()

    @app.route('/api/users', methods=['GET'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_users_list():
        return handler.User.list_users()

    @app.route('/api/users', methods=['POST'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_users_create():
        return handler.User.create_user()

    @app.route('/api/users/<user_name>', methods=['DELETE'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_users_delete(user_name):
        return handler.User.delete_user(user_name)

    @app.route('/api/users/<user_name>/reset-pwd', methods=['PUT'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_users_reset_pwd(user_name):
        return handler.User.reset_user_pwd(user_name)

    @app.route('/api/workflows', methods=['POST'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_workflows_create():
        return handler.Workflow.create()

    @app.route('/api/workflows/<int:workflow_id>', methods=['PUT'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_workflows_update(workflow_id):
        return handler.Workflow.update(workflow_id)

    @app.route('/api/workflows/<int:workflow_id>', methods=['DELETE'])
    @handler.Auth.require_api_auth
    @handler.Auth.require_admin
    def api_workflows_delete(workflow_id):
        return handler.Workflow.delete(workflow_id)

    # ============================================================
    # 用户自助 API
    # ============================================================
    @app.route('/api/user/password', methods=['PUT'])
    @handler.Auth.require_api_auth
    def api_user_change_pwd():
        return handler.User.change_password()

    @app.route('/api/user/tokens', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_user_tokens():
        return handler.User.list_my_tokens()

    @app.route('/api/user/token', methods=['POST'])
    @handler.Auth.require_api_auth
    def api_user_gen_token():
        return handler.User.generate_token()

    @app.route('/api/user/call-logs', methods=['GET'])
    @handler.Auth.require_api_auth
    def api_user_call_logs():
        return handler.User.my_call_logs()

    # ============================================================
    # API 调用日志中间件
    # ============================================================
    @app.before_request
    def api_call_log_middleware():
        """记录 API 调用的中间件"""
        # 只记录 /api/ 路径
        if not request.path.startswith('/api/'):
            return

        # 仅记录携带 API token 的请求
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return

        # 解析 token
        token_str = auth[7:]
        user = parse_token(token_str)
        if not user:
            return

        # 保存请求信息到 request 中，供 after_request 使用
        request._api_log_user = user["user_name"]
        request._api_log_body = request.get_data(as_text=True)[:1000]

    @app.after_request
    def api_call_log_after(response):
        """记录 API 调用日志"""
        user_name = getattr(request, "_api_log_user", None)
        if not user_name:
            return response

        # 构造日志
        req_body = getattr(request, "_api_log_body", "")
        resp_body = response.get_data(as_text=True)
        if len(resp_body) > 1000:
            resp_body = resp_body[:1000] + "..."

        status_code = response.status_code
        err_msg = ""
        if status_code >= 400:
            err_msg = resp_body

        # 异步保存日志 — 先捕获请求上下文的变量，避免线程中访问 request 报错
        path = request.path
        method = request.method

        def _save_log():
            try:
                meta_store.save_api_call_log(
                    user_name, path, method,
                    req_body, resp_body, status_code, err_msg,
                )
            except Exception as e:
                logger.error("保存 API 调用日志失败: %s", e)

        threading.Thread(target=_save_log, daemon=True).start()

        return response


def start_background_tasks_once():
    """确保后台任务只启动一次"""
    global background_tasks_started
    with background_tasks_lock:
        if not background_tasks_started:
            logger.info("启动后台任务...")
            start_background_tasks()
            background_tasks_started = True


def start_background_tasks():
    """启动后台任务线程（对标 Go：go kbManager.StartFileWorker()）"""
    def _start():
        kb_manager.start_file_worker()

    threading.Thread(target=_start, daemon=True).start()


# ============================================================
# 创建应用实例
# ============================================================
app = create_app()

# ============================================================
# 主入口
# ============================================================
if __name__ == '__main__':
    port = 19007
    logger.info("CSM 服务启动: http://localhost:%d", port)
    app.run(host='0.0.0.0', port=port, debug=my_cfg.get("server", {}).get("debug", False))