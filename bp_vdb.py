#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install flask
矢量知识库构建
"""
import logging.config
import os
import shutil
import threading
import time

from flask import (request, jsonify, Blueprint, render_template)
from werkzeug.utils import secure_filename


from db_util import DbUtl
from sys_init import init_yml_cfg
from vdb_util import vector_file, search_txt, update_doc

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

vdb_bp = Blueprint('vdb', __name__)


VDB_PREFIX = "./vdb/vdb_idx_"

UPLOAD_FOLDER = "upload_doc"
# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

my_cfg = init_yml_cfg()

task_progress = {}  # 存储文本进度信息
thread_lock = threading.Lock()

# 定义允许的文件类型及其魔数签名
ALLOWED_TYPES = {
    '.pdf': [b'%PDF'],          # PDF签名
    '.docx': [b'PK\x03\x04'],   # ZIP格式签名(DOCX本质是ZIP)
    '.txt': []                  # 文本文件无固定签名
}

@vdb_bp.route('/vdb/idx', methods=['GET'])
def vdb_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000/vdb/idx | jq
    :return:
    """
    logger.info(f"request_args_in_vdb_index {request.args}")
    try:
        uid = request.args.get('uid').strip()
        t = request.args.get('t').strip()
        if not uid:
            return "user is null in config, please submit your username in config request"
    except Exception as e:
        logger.error(f"err_in_vdb_index, {e}, url: {request.url}", exc_info=True)
        raise jsonify("err_in_vdb_index")
    vdb_status = ""
    vdb_dir = f"{VDB_PREFIX}{uid}"
    if os.path.exists(vdb_dir):
        total_kb = get_dir_file_size_in_kb(vdb_dir)
        vdb_status = f"当前知识库大小: {total_kb}"
    ctx = {
        "uid": uid,
        "t": t,
        "vdb_status": vdb_status,
        "sys_name": my_cfg['sys']['name'],
        "waring_info": ""
    }
    dt_idx = "vdb_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@vdb_bp.route('/vdb/list', methods=['POST'])
def get_vdb_list():
    """
    获取知识库列表
    """
    data = request.get_json()
    logger.info(f"get_vdb_list {data}")
    uid = data.get("uid")
    t = data.get("t")
    dt = DbUtl.get_vdb_info_by_uid(uid)
    return jsonify({"kb_list": dt})

@vdb_bp.route('/vdb/file/list', methods=['POST'])
def get_vdb_file_list():
    """
    获取知识库内的文件列表
    """
    data = request.get_json()
    logger.info(f"get_vdb_file_list {data}")
    uid = data.get("uid")
    t = data.get("t")
    vdb_id = data.get("vdb_id")
    dt = DbUtl.get_vdb_file_list(uid, vdb_id)
    return jsonify({"files": dt, "success": True})

@vdb_bp.route('/vdb/file/delete', methods=['POST'])
def delete_file_from_vdb():
    """
    删除知识库内的文件
    """
    data = request.get_json()
    logger.info(f"delete_file_from_vdb {data}")
    uid = data.get("uid")
    t = data.get("t")
    vdb_id = data.get("vdb_id")
    file_id = data.get("file_id")

    vdb_dir = f"{VDB_PREFIX}{uid}_{vdb_id}"
    if not os.path.exists(vdb_dir):
        info = {"success": False, "message": "知识库不存在，删除失败"}
        logger.info(info)
        return jsonify(info), 200
    dt = DbUtl.get_vdb_file_list(uid, vdb_id)
    if not dt or len(dt) == 0:
        info = {"success": False, "message": "知识库中的文件不存在，删除失败"}
        logger.info(info)
        return jsonify(info), 200
    disk_file_name = dt[0].get("file_path", None)
    if not disk_file_name:
        info = {"success": False, "message": "文件路径信息缺失，删除失败"}
        logger.info(info)
        return jsonify(info), 200
    DbUtl.delete_file_by_uid_vbd_id_file_id(file_id, uid, vdb_id)
    save_path = os.path.join(UPLOAD_FOLDER, disk_file_name)
    result = vdb_util.del_doc(save_path, vdb_dir)
    logger.info(f"delete_file_from_vdb, {result}, file_save_path {save_path}")
    info = {"success": True, "message": "文件已成功从知识库中删除"}
    logger.info(info)
    return jsonify(info), 200

@vdb_bp.route('/vdb/create', methods=['POST'])
def create_vdb():
    """
    创建知识库
    """
    data = request.get_json()
    logger.info(f"create_vdb {data}")
    uid = data.get("uid")
    kb_name = data.get("kb_name")
    is_public = data.get("is_public")
    t = data.get("t")
    db_check = DbUtl.get_vdb_info_by_uid(uid, kb_name)
    if db_check:
        info = {"success": False, "message": f"知识库 {kb_name} 已存在"}
        logger.error(info)
        return jsonify(info), 200
    if is_public:
        is_public = 1
    else:
        is_public = 0
    dt = DbUtl.create_vdb_info(kb_name, uid, is_public)
    return jsonify({"success": True, "kb": dt})

@vdb_bp.route('/vdb/delete', methods=['POST'])
def delete_vdb_dir():
    data = request.json
    logger.info(f"vdb_delete, {data}")
    uid = data.get("uid")
    t = data.get("t")
    kb_id = data.get("kb_id")
    del_result = False
    try:
        if not uid or not t:
            msg = "未提供合法的用户信息"
            logger.error(msg)
            return jsonify({"success": del_result,"message": msg}), 200
        DbUtl.delete_file_by_uid_vbd_id(uid, kb_id)
        DbUtl.delete_vdb_by_uid_and_kb_id(uid, kb_id)

        vdb_dir = f"{VDB_PREFIX}{uid}_{kb_id}"
        if os.path.exists(vdb_dir):
            shutil.rmtree(vdb_dir)
            msg = "成功删除知识库"
            del_result = True
        else:
            del_result = True
            msg = "知识库已删除"
        logger.info(f"{msg}, {vdb_dir}")
        return jsonify({"success": del_result, "message": msg}), 200
    except Exception as e:
        msg = f"删除知识库出现异常 {str(e)}"
        logger.error(f"err_msg, {msg}", exc_info=True)
        return jsonify({"success": del_result, "message": msg}), 200

@vdb_bp.route('/vdb/upload', methods=['POST'])
def upload_file():
    logger.info(f"start_upload_file, {request}")
    if 'file' not in request.files:
        info = {"success": False, "message": "未找到文件"}
        logger.error(info)
        return jsonify(info), 400
    file = request.files['file']
    upload_file_name = file.filename
    kb_id = request.form.get('kb_id')
    uid = request.form.get('uid')
    if not kb_id or not uid or not upload_file_name:
        info = {"success": False, "message": f"缺少参数,文件名、知识库ID或用户ID为空, {upload_file_name}, {kb_id}, {uid}"}
        logger.error(info)
        return jsonify(info), 400
    logger.info(f"vdb_upload_file, {upload_file_name}, {kb_id}, {uid}")

    try:
        # 安全检查和处理文件名
        safe_filename = secure_filename(upload_file_name)
        if not safe_filename:  # 安全检查后文件名仍为空
            info = {"success": False, "message": f"无效文件名, {upload_file_name}"}
            logger.error(info)
            return jsonify(info), 400
        # 检查文件类型
        logger.info(f"safe_filename: {safe_filename}")
        allowed_extensions = {'.docx', '.pdf', '.txt'}
        original_filename = upload_file_name
        file_ext = os.path.splitext(original_filename)[1].lower()  # 提取扩展名并转为小写
        if file_ext not in allowed_extensions:
            info = {"success": False, "message": f"不支持的文件类型 {file_ext}，仅允许 docx/pdf/txt"}
            logger.error(info)
            return jsonify(info), 400
        # 读取文件头进行魔数验证
        file.seek(0)
        header = file.read(4)  # 读取前4字节
        # 特殊处理DOCX(PK\x03\x04)和PDF(%PDF)
        if file_ext in ['.docx', '.pdf']:
            valid_signatures = ALLOWED_TYPES[file_ext]
            if not any(header.startswith(sig) for sig in valid_signatures):
                info = {"success": False, "message": "文件内容与类型不符"}
                logger.error(info)
                return jsonify(info), 400
        file.seek(0)  # 重置文件指针
        # 生成唯一任务ID和文件名
        task_id = str(int(time.time() * 1000))  # 使用毫秒提高唯一性
        disk_file_name = f"{task_id}_{original_filename}"
        save_path = os.path.join(UPLOAD_FOLDER, disk_file_name)
        # 保存文件
        file.save(save_path)
        file_info = DbUtl.get_file_info(upload_file_name, uid, kb_id)
        if file_info:
            logger.info(f"duplicate_upload_file, {upload_file_name}, {disk_file_name}, "
                    f"{uid}, {kb_id}, previous_file {file_info[0].get('file_path')}")
        else:
            logger.info(f"save_new_file_info_for_vdb, {upload_file_name}, {disk_file_name}, {uid}, {kb_id}")
            DbUtl.save_file_info(upload_file_name, disk_file_name, uid, kb_id)
        # 初始化任务进度
        with thread_lock:
            task_progress[task_id] = {
                'progress': 0,
                'filename': disk_file_name,
                'timestamp': time.time()
            }
        info = {"success": True,"task_id": task_id,"file_name": disk_file_name,"message": "文件上传成功"}
        logger.info(f"文件上传成功: {disk_file_name}, 大小: {os.path.getsize(save_path)}字节, return {info}")
        return jsonify(info), 200

    except Exception as e:
        logger.error(f"文件上传处理失败: {str(e)}", exc_info=True)
        info = {"success": False, "message": f"文件上传处理失败: {str(e)}"}
        logger.error(info)
        return jsonify(info), 500

@vdb_bp.route("/vdb/index/doc", methods=['POST'])
def index_doc():
    data = request.json
    logger.info(f"vdb_index_doc, {data}")
    task_id = data.get("task_id")
    file_name = data.get("file_name")
    uid = data.get("uid")
    kb_id = data.get("kb_id")

    if not task_id or not file_name or not kb_id:
        return jsonify({"error": "缺少参数"}), 400
    threading.Thread(
        target=process_doc,
        args=(task_id, file_name, uid, kb_id)
    ).start()
    return jsonify({"status": "started", "task_id": task_id}), 200

@vdb_bp.route('/vdb/process/info', methods=['POST'])
def get_doc_process_info():
    task_id = request.json.get("task_id")
    if not task_id:
        return jsonify({"error": "缺少任务ID"}), 400
    with thread_lock:
        progress_info = task_progress.get(task_id, {"text": "未知状态"})
    return jsonify({
        "task_id": task_id,
        "progress": progress_info["text"]
    }), 200


@vdb_bp.route('/vdb/search', methods=['POST'])
def search_vdb():

    data = request.json
    logger.info(f"vdb_search, {data}")
    search_input = data.get("search_input")
    uid = data.get("uid")
    kb_id = data.get("kb_id")
    t = data.get("t")
    if not search_input or not uid or not t:
        return jsonify({"error": "缺少参数"}), 400
    my_vector_db_dir = f"{VDB_PREFIX}{uid}_{kb_id}"

    search_result = search_txt(search_input, my_vector_db_dir, 0.1, my_cfg['api'], 3)
    logger.info(f"search_result_for_[{search_input}], {search_result}")
    if search_result:
        search_result = search_result.replace("\n", "<br>")
        return jsonify({"search_output": search_result}), 200
    else:
        return jsonify({"search_output": "未检索到有效内容"}), 200

def clean_tasks():
    while True:
        with thread_lock:
            now = time.time()
            expired = [k for k, v in task_progress.items()
                      if now - v['timestamp'] > 3600]  # 1小时过期
            for k in expired:
                del task_progress[k]
        time.sleep(300)


def process_doc(task_id: str, file_name: str, uid: str, kb_id: str):
    try:
        upload_file_name =get_upload_file_name(file_name)
        file_info = DbUtl.get_file_info(upload_file_name, uid, kb_id)
        if not file_info:
            raise Exception(f"no_upload_file_info_err, {upload_file_name}, {file_name}, {uid}, {kb_id}")
        record_file_name = file_info[0]['file_path']
        file_id = file_info[0]['id']
        cur_file_path = os.path.join(UPLOAD_FOLDER, file_name)
        prev_file_path = os.path.join(UPLOAD_FOLDER, record_file_name)
        output_vdb_dir = f"{VDB_PREFIX}{uid}_{kb_id}"
        if upload_file_name != record_file_name:

            logger.info(f"duplicate_file_in_vdb_to_be_update, prev={record_file_name}, cur={file_name}, vdb_id {kb_id}")
            with thread_lock:
                task_progress[task_id] = {"text": "更新已有文档...", "timestamp": time.time()}
            update_doc(task_id, thread_lock, task_progress, prev_file_path, cur_file_path, output_vdb_dir, my_cfg['api'])
            DbUtl.update_file_info(file_id, file_name)
        else:
            logger.info(f"new_file_in_vdb_to_be_add, {file_name}, vdb_id {kb_id}")
            with thread_lock:
                task_progress[task_id] = {"text": "开始解析文档结构...", "timestamp": time.time()}
            vector_file(task_id, thread_lock, task_progress, cur_file_path,
                output_vdb_dir, my_cfg['api'],300, 80)
    except Exception as e:
        with thread_lock:
            task_progress[task_id] = {
                "text": f"任务处理失败: {str(e)}",
                "timestamp": time.time()
            }
        logger.exception(f"process_doc_err, {file_name}", e)

def get_upload_file_name(disk_file_name):
    parts = disk_file_name.split("_", 1)
    return parts[1] if len(parts) > 1 else disk_file_name

def get_dir_file_size_in_kb(file_dir: str):
    total_size = 0
    for dirpath, _, filenames in os.walk(file_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    total_kb = f"{total_size / 1024:.2f} KB"
    return total_kb

if __name__ == '__main__':
    logger.info("just for test")