#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
通过文本转换为SQL语句，提供数据库数据查询服务，通过 stream 模式提供数据
pip install gunicorn flask concurrent-log-handler langchain_openai langchain_ollama \
 langchain_core langchain_community pandas tabulate pymysql cx_Oracle pycryptodome
"""
import json
import logging.config
import re
import time
import cfg_util as cfg_utl

from flask import Flask, render_template, Response, request, jsonify, redirect, url_for

import utils
from bp_auth import auth_bp, auth_info, get_client_ip
from my_enums import DataType, DBType, AppType
from sql_yield import SqlYield
from sys_init import init_yml_cfg
from utils import get_console_arg1

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.config['JSON_AS_ASCII'] = False
my_cfg = init_yml_cfg()

# user's last sql, {"my_uid": {"sql":"my_sql", "curr_page":1, "total_page":1}}
# last search sql, current page and total page for the SQL
usr_page_dt = {}

SESSION_TIMEOUT = 72000     # session timeout second , default 2 hours

@app.route('/')
def app_home():
    logger.info("redirect_auth_login_index")
    return redirect(url_for('auth.login_index', app_source=AppType.TXT2SQL.name.lower()))

@app.route('/stream', methods=['POST', 'GET'])
def stream():
    logger.info(f"request.args {request.args}")
    t = int(request.args.get('t', 0))
    q = request.args.get('q', '')
    uid = int(request.args.get('uid', ''))
    page = request.args.get('page')
    session_key = f"{uid}_{get_client_ip()}"
    if not auth_info.get(session_key, None) or time.time() - auth_info.get(session_key) > SESSION_TIMEOUT:
        return Response(
            illegal_access(uid),
            mimetype='text/event-stream; charset=utf-8'
        )
    logger.info(f"rcv_stream_req, t={t}, q={q}")
    sql_yield = SqlYield(uid, my_cfg)
    if not q and usr_page_dt.get(uid, None) and page and page != '':
        usr_page_dt[uid]["cur_page"] += 1
        logger.info(f"usr_page_dt_for_{uid}: {json.dumps(usr_page_dt[uid], ensure_ascii=False)}")
        answer = sql_yield.get_pg_dt(uid, usr_page_dt[uid])
    else:
        answer = sql_yield.yield_dt_with_nl(uid, q, DataType.HTML.value, usr_page_dt)
    return Response(answer,mimetype='text/event-stream; charset=utf-8')

@app.route('/cfg/idx', methods=['GET'])
def config_index():
    """
     A index for static
    curl -s --noproxy '*' http://127.0.0.1:19000 | jq
    :return:
    """
    logger.info(f"request_args_in_config_index {request.args}")
    app_source = request.args.get('app_source', '')
    try:
        uid = request.args.get('uid').strip()
        if not uid:
            return "user is null in config, please submit your username in config request"
    except Exception as e:
        logger.error(f"err_in_config_index, {e}, url: {request.url}", exc_info=True)
        raise jsonify("err_in_config_index")
    ctx = cfg_utl.get_ds_cfg_by_uid(uid, my_cfg)
    ctx["uid"] = uid
    ctx["app_source"] = app_source
    ctx['sys_name'] = my_cfg['sys']['name']
    ctx["waring_info"] = ""
    dt_idx = "config_index.html"
    logger.info(f"return_page {dt_idx}, ctx {ctx}")
    return render_template(dt_idx, **ctx)

@app.route('/cfg/dt', methods=['POST'])
def save_config():
    logger.info(f"save_config_info {request.form}")
    dt_idx = "config_index.html"
    uid = request.form.get('uid').strip()
    db_type = request.form.get('db_type').strip()
    db_host = request.form.get('db_host').strip()
    db_port = request.form.get('db_port').strip()
    db_name = request.form.get('db_name').strip()
    db_usr  = request.form.get('db_usr').strip()
    db_psw  = request.form.get('db_psw').strip()
    tables = request.form.get('tables').strip()
    add_chart = request.form.get('add_chart').strip()
    is_strict = request.form.get('is_strict').strip()
    llm_ctx = request.form.get('llm_ctx').strip()
    data_source_cfg = {
        "sys_name":     my_cfg['sys']['name'],
        "waring_info":  "",
        "uid":          uid,
        "db_type":      db_type,
        "db_name":      db_name,
        "db_host":      db_host,
        "db_port":      db_port,
        "db_usr":       db_usr,
        "db_psw":       db_psw,
        "tables":       tables,
        "add_chart":    add_chart,
        "is_strict":    is_strict,
        "llm_ctx":      llm_ctx
    }
    if uid:
        uid_num = int(uid)
        usr = cfg_utl.get_user_name_by_uid(uid_num)
    else:
        usr = None
    if not usr:
        data_source_cfg['waring_info'] = '非法访问，请您先登录系统'
        return render_template(dt_idx, **data_source_cfg)
    if data_source_cfg["db_type"] == DBType.SQLITE.value:
        data_source_cfg['waring_info'] = '数据库类型有误'
        return render_template(dt_idx, **data_source_cfg)
    save_cfg_result = cfg_utl.save_ds_cfg(data_source_cfg, my_cfg)
    if save_cfg_result:
        data_source_cfg['waring_info'] = '保存成功'
    else:
        data_source_cfg['waring_info'] = '保存失败'
    # sql_agent = SqlAgent(cfg_utl.build_data_source_cfg_with_uid(uid, my_cfg))
    # data_source_cfg["schema"] = f"表清单: {sql_agent.get_all_tables()}\n {sql_agent.get_schema_info()}"
    return render_template(dt_idx, **data_source_cfg)


@app.route('/cfg/delete', methods=['POST'])
def delete_config():
    logger.info(f"del_cfg_info {request.data}")
    uid = json.loads(request.data).get('uid').strip()
    logger.info(f"del_cfg_info_for_uid_{uid}")
    usr = cfg_utl.get_user_name_by_uid(uid)
    waring_info = {"success": False, "msg": ""}
    if not usr:
        waring_info['msg'] = '非法访问，请先登录系统'
        return waring_info
    delete_cfg_result = cfg_utl.delete_data_source_config(uid, my_cfg)
    if delete_cfg_result:
        waring_info['msg'] = '删除成功'
        waring_info['success'] = True
    else:
        waring_info['msg'] = '删除失败'
    logger.info(f"del_cfg_info_for_uid_{uid}, return {waring_info}")
    return waring_info


@app.route('/user/hack/info', methods=['GET', 'POST'])
def user_hack_info():
    dt_idx = 'hack_info_index.html'
    ctx = {
        "sys_name": my_cfg['sys']['name'],
        "app_source": AppType.TXT2SQL.name.lower(),
        "warning_info": "",
    }
    if request.method == 'GET':
        uid = request.args.get("uid").strip()
        user_list = cfg_utl.get_user_list()
        hack_user_config = cfg_utl.get_user_hack_info(uid, my_cfg)
        ctx['uid'] = uid
        ctx['user_list'] = user_list
        ctx['hack_user_config'] = hack_user_config
        return render_template(dt_idx,  **ctx)
    else:
        uid = request.form.get("user_list").strip()
        hack_info = request.form.get("hack_user_config").strip()
        user_list = cfg_utl.get_user_list()
        ctx['uid'] = uid
        ctx['hack_user_config'] = hack_info
        ctx['user_list'] = user_list
        is_ok = utils.check_contain_spaces_in_every_line(hack_info)
        if not is_ok:
            ctx['waring_info'] = '保存失败，数据格式有误，每行需含有至少一个空格或制表符[TAB]'
            return render_template(dt_idx, **ctx)
        hack_info = utils.replace_spaces(hack_info)
        logger.info(f"user_hack_info_for_uid_{uid}, hack_info: {hack_info}")
        save_cfg_result = cfg_utl.save_user_hack_info(uid, hack_info, my_cfg)

        hack_user_config = cfg_utl.get_user_hack_info(uid, my_cfg)
        ctx['hack_user_config'] = hack_user_config
        if save_cfg_result:
            ctx['waring_info'] = '保存成功'
        else:
            ctx['waring_info'] = '保存失败'
            # sql_agent = SqlAgent(cfg_utl.build_data_source_cfg_with_uid(uid, my_cfg))
            # data_source_cfg["schema"] = f"表清单: {sql_agent.get_all_tables()}\n {sql_agent.get_schema_info()}"
        return render_template(dt_idx, **ctx)

@app.route('/user/prompt', methods=['GET'])
def user_prompt_idx():
    dt_idx = 'prompt_index.html'
    ctx = {
        "sys_name": my_cfg['sys']['name'],
        "app_source": AppType.TXT2SQL.name.lower(),
        "warning_info": "",
    }
    uid = request.args.get("uid").strip()
    user_list = cfg_utl.get_user_list()
    ctx['uid'] = uid
    ctx['user_list'] = user_list
    ctx['refine_q_msg'] = cfg_utl.get_usr_prompt_template('refine_q_msg', my_cfg, uid)
    ctx['sql_gen_msg'] = cfg_utl.get_usr_prompt_template('sql_gen_msg', my_cfg, uid)
    return render_template(dt_idx,  **ctx)


@app.route('/user/prompt', methods=['POST'])
def set_user_prompt():
    dt_idx = 'prompt_index.html'
    ctx = {
        "sys_name": my_cfg['sys']['name'],
        "app_source": AppType.TXT2SQL.name.lower(),
        "warning_info": "",
    }

    uid = int(request.form.get("uid").strip())
    refine_q_msg = request.form.get("refine_q_msg").strip()
    refine_q_msg = re.sub(r' +', ' ', refine_q_msg)
    sql_gen_msg = request.form.get("sql_gen_msg").strip()
    sql_gen_msg = re.sub(r' +', ' ', sql_gen_msg)
    ctx['uid'] = uid
    check_result = utils.validate_user_prompt(refine_q_msg, sql_gen_msg)
    if not check_result['is_valid']:
        warn_info = "保存失败，数据格式有误, "
        if check_result['refine_q_msg_err']:
            warn_info += f"问题优化提示词缺少必要变量: {check_result['refine_q_msg_err']} "
        if check_result['sql_gen_msg_err']:
            warn_info += f"SQL生成提示词缺少必要变量: {check_result['sql_gen_msg_err']}"
        ctx['warning_info'] = warn_info
        ctx['refine_q_msg'] = refine_q_msg
        ctx['sql_gen_msg'] = sql_gen_msg
        logger.info(f"{uid}, validate_user_prompt_result, {check_result}")
        return render_template(dt_idx, **ctx)

    logger.info(f"{uid}_user_customized_prompt, refine_q_msg:{refine_q_msg}, sql_gen_msg:{sql_gen_msg}")
    refine_q_msg_v = refine_q_msg.replace("'", "''")
    sql_gen_msg_v = sql_gen_msg.replace("'", "''")
    save_cfg_result1 = cfg_utl.save_usr_prompt_template(uid, 'refine_q_msg', refine_q_msg_v)
    save_cfg_result2 = cfg_utl.save_usr_prompt_template(uid, 'sql_gen_msg', sql_gen_msg_v)

    if save_cfg_result1 and save_cfg_result2:
        ctx['warning_info'] = '保存成功'
    else:
        ctx['warning_info'] = '保存失败'

    refine_q_msg = cfg_utl.get_usr_prompt_template('refine_q_msg', my_cfg, uid)
    sql_gen_msg = cfg_utl.get_usr_prompt_template('sql_gen_msg', my_cfg, uid)
    ctx['refine_q_msg'] = refine_q_msg
    ctx['sql_gen_msg'] = sql_gen_msg
    return render_template(dt_idx, **ctx)

@app.route('/prompt/reset', methods=['POST'])
def reset_user_prompt():
    dt_idx = 'prompt_index.html'
    ctx = {
        "sys_name": my_cfg['sys']['name'],
        "app_source": AppType.TXT2SQL.name.lower(),
        "warning_info": "",
    }

    uid = int(request.form.get("uid").strip())
    ctx['uid'] = uid
    if not uid or uid == 0:
        warn_info = "用户信息有误, 系统出现异常"
        ctx['warning_info'] = warn_info
        logger.info(f"{uid}, validate_user_info_fail_err, {uid}")
        return render_template(dt_idx, **ctx)

    logger.info(f"{uid}_reset_user_prompt")
    del_prompt_result = cfg_utl.del_usr_prompt_template(uid)

    if del_prompt_result:
        ctx['warning_info'] = '重置成功'
    else:
        ctx['warning_info'] = '重置失败'

    refine_q_msg = cfg_utl.get_usr_prompt_template('refine_q_msg', my_cfg, uid)
    sql_gen_msg = cfg_utl.get_usr_prompt_template('sql_gen_msg', my_cfg, uid)
    ctx['refine_q_msg'] = refine_q_msg
    ctx['sql_gen_msg'] = sql_gen_msg
    return render_template(dt_idx, **ctx)

@app.route('/<uid>/my/hack/info', methods=['GET'])
def get_my_hack_info(uid: str):
    """
    获取某个用户的 hack info
    """
    hack_user_config = cfg_utl.get_user_hack_info(uid, my_cfg)
    logger.info(f"get_user_hack_info {uid}, {hack_user_config}")
    response = {
        "status": 200,
        "data":hack_user_config,
        "msg": "成功获取用户配置信息"
    }
    return json.dumps(response, ensure_ascii=False)


def illegal_access(uid):
    waring_info = "登录信息已失效，请重新登录后再使用本系统"
    logger.error(f"{waring_info}, {uid}")
    yield SqlYield.build_yield_dt(waring_info)

def generate_data():
    messages = ["大模型思考中...", "用户问题优化中...","优化后的问题是：***",
                "用户问题转换为SQL中...","SQL语句为：***","数据查询中...",
                "查询到的数据:****","正在绘图...","绘图结果为：\ndata_chart", "本次查询已完成"]
    for msg in messages:
        time.sleep(1)  # 模拟处理延迟
        yield f"data: {msg}\n\n"


if __name__ == '__main__':
    """
    just for test, not for a production environment.
    """
    port = get_console_arg1()
    logger.info(f"listening_port {port}")
    app.run(host='0.0.0.0', port=port)