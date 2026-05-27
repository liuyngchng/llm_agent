#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
独立数据统计 HTTP 服务 - 基于 FastAPI
提供用户访问量、Token 使用量统计等 JSON API 接口
"""
import os
import sys
import sqlite3
import logging.config
from datetime import datetime

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from common.sys_init import init_yml_cfg
from common.cm_utils import get_console_arg1
from common.i18n import get_msg

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
my_cfg = init_yml_cfg()
STS_DB_FILE = "statistics.db"

# ---------------------------------------------------------------------------
# 数据库初始化
# ---------------------------------------------------------------------------
def init_db():
    with sqlite3.connect(STS_DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER NOT NULL UNIQUE,
                uid INTEGER NOT NULL,
                nickname TEXT NOT NULL,
                app TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0,
                input_token INTEGER NOT NULL DEFAULT 0,
                output_token INTEGER NOT NULL DEFAULT 0,
                embedding_token INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY("id" AUTOINCREMENT)
            )
        """)
        conn.commit()
        # 兼容旧表：如果旧表缺少 app 列，则自动添加
        try:
            conn.execute("ALTER TABLE statistics ADD COLUMN app TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略

init_db()

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(title="Statistics Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------
class AccessCountRequest(BaseModel):
    uid: int = Field(..., description="用户 ID")
    count: int = Field(1, description="访问次数增量")
    app: str = Field("", description="来源应用名称")


class TokenRequest(BaseModel):
    uid: int = Field(..., description="用户 ID")
    count: int = Field(..., description="Token 增量")
    app: str = Field("", description="来源应用名称")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _get_auth_api_base() -> str:
    auth_api = my_cfg.get('api', {}).get('auth_api', '')
    if not auth_api:
        raise RuntimeError("配置缺失: cfg.yml 中未设置 api.auth_api")
    return auth_api.rstrip('/')


def _get_user_name(uid: int) -> str:
    """通过 auth_service 获取用户名"""
    try:
        url = f"{_get_auth_api_base()}/auth/user/{uid}"
        logger.info(f"request_auth_api, url={url}")

        resp = requests.get(url, timeout=5, verify=False)
        if resp.status_code == 200:
            return resp.json().get('name', '')
    except Exception as e:
        logger.exception(f"get_user_name_failed, uid={uid}, err={e}")
    return ''


def _ensure_row(conn, uid: int, nickname: str, date: str, app_name: str = ""):
    """确保当天该 uid 的记录存在，返回当前记录"""
    cur = conn.execute(
        "SELECT access_count, input_token, output_token, embedding_token, app "
        "FROM statistics WHERE uid=? AND date=? AND app=?",
        (uid, date, app_name)
    )
    row = cur.fetchone()
    if row:
        return row
    conn.execute(
        "INSERT INTO statistics (uid, nickname, date, app) VALUES (?, ?, ?, ?)",
        (uid, nickname, date, app_name)
    )
    conn.commit()
    return 0, 0, 0, 0, app_name


def _add_field(uid: int, field: str, count: int, app_name: str = "") -> bool:
    """通用：给 uid 的当天记录累加某个字段"""
    if not count or not uid:
        return False
    nickname = _get_user_name(uid)
    if not nickname:
        logger.error(f"cannot_get_nickname_for_uid={uid}")
        return False
    today = datetime.today().strftime('%Y-%m-%d')
    with sqlite3.connect(STS_DB_FILE) as conn:
        try:
            _ensure_row(conn, uid, nickname, today, app_name)
            conn.execute(
                f"UPDATE statistics SET {field}={field}+? WHERE uid=? AND date=? AND app=?",
                (count, uid, today, app_name)
            )
            conn.commit()
            logger.info(f"add_{field}_success, uid={uid}, count={count}, app={app_name}")
            return True
        except Exception as e:
            conn.rollback()
            logger.exception(f"add_{field}_failed, uid={uid}, err={e}")
    return False


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@app.post("/statistics/access")
def add_access(req: AccessCountRequest):
    """记录用户访问次数"""
    success = _add_field(req.uid, "access_count", req.count, req.app)
    if not success:
        raise HTTPException(status_code=500, detail=get_msg('backend.record_access_failed'))
    return {"status": "ok"}


@app.post("/statistics/input-token")
def add_input_token(req: TokenRequest):
    """记录用户输入 Token 用量"""
    success = _add_field(req.uid, "input_token", req.count, req.app)
    if not success:
        raise HTTPException(status_code=500, detail=get_msg('backend.record_input_token_failed'))
    return {"status": "ok"}


@app.post("/statistics/output-token")
def add_output_token(req: TokenRequest):
    """记录用户输出 Token 用量"""
    success = _add_field(req.uid, "output_token", req.count, req.app)
    if not success:
        raise HTTPException(status_code=500, detail=get_msg('backend.record_output_token_failed'))
    return {"status": "ok"}


@app.post("/statistics/embedding-token")
def add_embedding_token(req: TokenRequest):
    """记录用户嵌入 Token 用量"""
    success = _add_field(req.uid, "embedding_token", req.count, req.app)
    if not success:
        raise HTTPException(status_code=500, detail=get_msg('backend.record_embedding_token_failed'))
    return {"status": "ok"}


@app.get("/statistics/list")
def get_list():
    """获取统计数据列表（最近100条）"""
    with sqlite3.connect(STS_DB_FILE) as conn:
        cur = conn.execute(
            "SELECT uid, nickname, app, date, access_count, input_token, output_token, embedding_token "
            "FROM statistics ORDER BY date DESC LIMIT 100"
        )
        rows = cur.fetchall()
    result = []
    for row in rows:
        result.append({
            "uid": row[0],
            "nickname": row[1],
            "app": row[2],
            "date": row[3],
            "access_count": row[4],
            "input_token": row[5],
            "output_token": row[6],
            "embedding_token": row[7],
        })
    return result


@app.get("/statistics/user/{uid}")
def get_by_uid(uid: int):
    """获取指定用户的统计数据"""
    with sqlite3.connect(STS_DB_FILE) as conn:
        cur = conn.execute(
            "SELECT uid, nickname, app, date, access_count, input_token, output_token "
            "FROM statistics WHERE uid=? LIMIT 1", (uid,)
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=get_msg('backend.user_stats_not_found'))
    return {
        "uid": row[0],
        "nickname": row[1],
        "app": row[2],
        "date": row[3],
        "access_count": row[4],
        "input_token": row[5],
        "output_token": row[6],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import uvicorn
    port = get_console_arg1()
    # port = 19012
    logger.info(f"statistics_service_listen_on_port {port}")
    uvicorn.run(app, host='0.0.0.0', port=port)
