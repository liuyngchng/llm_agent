#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
独立用户认证 HTTP 服务 - 基于 FastAPI
提供登录、注册、权限校验等 JSON API 接口
"""
import hashlib
import json
import os
import random
import re
import string
import sys
import time
import logging.config

import svgwrite
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from apps.auth_service import auth_util
from common import cm_utils
from common.cm_utils import get_console_arg1, decode_token, create_token

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from common.sys_init import init_yml_cfg
from common.const import SESSION_TIMEOUT

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

# 初始化数据库
auth_util.init_db()

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(
    title="用户认证服务",
    description="提供用户登录、注册、权限校验等 API",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 图形验证码存储
captcha_codes: dict = {}

# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    usr: str = Field(..., description="用户名")
    t: str = Field(..., description="加密后的密码")
    captcha_code: str = Field("", description="验证码")
    captcha_token: str = Field("", description="验证码 token")


class RegisterRequest(BaseModel):
    usr: str = Field(..., min_length=1, description="用户名")
    t: str = Field(..., min_length=1, description="加密后的密码")
    captcha_code: str = Field("", description="验证码")
    captcha_token: str = Field("", description="验证码 token")

class SessionToken(BaseModel):
    t: str = Field(..., min_length=1, description="会话token")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    x_forwarded_for = request.headers.get("X-Forwarded-For", "")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "127.0.0.1"

    ipv4 = r"^(\d{1,3}\.){3}\d{1,3}$"
    ipv6 = r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$"

    if ip in ("127.0.0.1", "localhost", "::1"):
        return ip
    if re.match(ipv4, ip) and all(0 <= int(p) <= 255 for p in ip.split(".")):
        return ip
    if re.match(ipv6, ip):
        return ip
    return "INVALID_IP"



def verify_captcha(code: str, token: str) -> bool:
    """验证图形验证码"""
    if not token or token not in captcha_codes:
        return False
    info = captcha_codes.get(token)
    if time.time() > info["expires_at"]:
        del captcha_codes[token]
        return False
    if info["text"] != code:
        info["attempts"] += 1
        if info["attempts"] >= 3:
            del captcha_codes[token]
        return False
    return True


def _cleanup_expired_captchas():
    now = time.time()
    expired = [t for t, v in captcha_codes.items() if now > v["expires_at"]]
    for t in expired:
        del captcha_codes[t]


def _generate_captcha_svg(text: str) -> str:
    """生成 SVG 验证码图片"""
    width, height = 100, 44
    dwg = svgwrite.Drawing(size=(width, height))
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height),
                      fill="#f8f9fa", stroke="#dee2e6", stroke_width=1))
    # 干扰线
    for _ in range(3):
        dwg.add(dwg.line(
            start=(random.randint(0, width), random.randint(0, height)),
            end=(random.randint(0, width), random.randint(0, height)),
            stroke=random.choice(["#adb5bd", "#6c757d", "#495057"]),
            stroke_width=random.uniform(0.5, 1)))
    # 干扰点
    for _ in range(15):
        dwg.add(dwg.circle(
            center=(random.randint(0, width), random.randint(0, height)),
            r=random.uniform(0.3, 1),
            fill=random.choice(["#adb5bd", "#6c757d", "#495057"])))
    # 文字
    font_size = 20
    text_x = 5
    for ch in text:
        rot = random.uniform(-8, 8)
        y_off = random.uniform(-2, 2)
        dwg.add(dwg.text(ch, insert=(text_x, 28 + y_off),
                         font_size=font_size, font_family="Arial, sans-serif",
                         fill="#212529", font_weight="bold",
                         transform=f"rotate({rot},{text_x},{28 + y_off})"))
        text_x += 18
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height),
                      fill="none", stroke="#ced4da", stroke_width=1))
    return dwg.tostring()


# ---------------------------------------------------------------------------
# 依赖注入 — token 鉴权
# ---------------------------------------------------------------------------

async def require_user(authorization: str = Header("")) -> dict:
    """
    从 Authorization header 解析当前用户，失败则 401
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证 token")
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    payload = decode_token(token, my_cfg['sys']['cypher_key'])
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return payload


async def optional_user(authorization: str = Header("")) -> dict | None:
    """与 require_user 类似但不会拒绝请求（token 解析失败返回 None）"""
    if not authorization:
        return None
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    return decode_token(token, my_cfg['sys']['cypher_key'])


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "healthy", "service": "auth_service"}


# ---- 验证码 ----

@app.get("/auth/captcha/generate")
def generate_captcha():
    """生成验证码 token"""
    _cleanup_expired_captchas()
    text = "".join(random.choices(string.digits, k=4))
    token = hashlib.md5(f"{text}{time.time()}".encode()).hexdigest()[:16]
    captcha_codes[token] = {"text": text, "expires_at": time.time() + 300, "attempts": 0}
    return {"success": True, "captcha_token": token}


@app.get("/auth/captcha/image/{captcha_token}")
def generate_captcha_image(captcha_token: str):
    """获取验证码 SVG 图片"""
    info = captcha_codes.get(captcha_token)
    if not info:
        raise HTTPException(status_code=404, detail="验证码不存在或已过期")
    logger.debug(f"{captcha_token} info: {json.dumps(info)}")
    svg = _generate_captcha_svg(info["text"])
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "no-cache"})


# ---- 登录 ----

@app.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    """用户登录，返回 token"""
    ip = get_client_ip(request)
    logger.info(f"用户登录: {body.usr}, IP={ip}")

    if not verify_captcha(body.captcha_code, body.captcha_token):
        logger.warning(f"验证码错误 - 用户: {body.usr}")
        raise HTTPException(status_code=400, detail="验证码错误")

    result = auth_util.auth_user(body.usr, body.t, my_cfg)
    if not result["pass"]:
        logger.error(f"认证失败 - 用户: {body.usr}, 原因: {result.get('msg')}")
        raise HTTPException(status_code=401, detail=result.get("msg", "登录失败"))

    # 清理验证码
    if body.captcha_token in captcha_codes:
        del captcha_codes[body.captcha_token]
    token = create_token(result["uid"], result["role"], SESSION_TIMEOUT, my_cfg['sys']['cypher_key'])
    logger.info(f"登录成功 - 用户: {body.usr}, uid: {result['uid']}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "uid": result["uid"],
        "role": result["role"],
        "expires_in": SESSION_TIMEOUT,
    }


# ---- 注册 ----

@app.post("/auth/register")
async def register(body: RegisterRequest):
    """用户注册"""
    logger.info(f"用户注册: {body.usr}")

    if not verify_captcha(body.captcha_code, body.captcha_token):
        logger.warning(f"注册验证码错误 - 用户: {body.usr}")
        raise HTTPException(status_code=400, detail="验证码错误")

    if auth_util.get_uid_by_user(body.usr) is not None:
        logger.error(f"注册失败 - 用户已存在: {body.usr}")
        raise HTTPException(status_code=409, detail=f"用户 {body.usr} 已存在")

    if not auth_util.save_usr(body.usr, body.t):
        raise HTTPException(status_code=500, detail="用户创建失败")

    uid = auth_util.get_uid_by_user(body.usr)
    if uid is None:
        raise HTTPException(status_code=500, detail="用户创建后查询失败")

    if body.captcha_token in captcha_codes:
        del captcha_codes[body.captcha_token]

    token = create_token(uid, 0, SESSION_TIMEOUT, my_cfg['sys']['cypher_key'])        # 注册用户默认角色为 0
    logger.info(f"user_registry_success: {body.usr}, uid: {uid}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "uid": uid,
        "message": f"用户 {body.usr} 注册成功",
    }


# ---- token 验证 ----

@app.post("/auth/token")
def verify_token(token: SessionToken) -> dict | None:
    if not token or not token.t:
        logger.info(f"token is null, {token}")
        return None
    logger.debug(f"decode_token {token.t}")
    session_info = decode_token(token.t)
    logger.debug(f"decode_token {token.t}, {session_info}, now, {time.time()}")
    return session_info





@app.post("/auth/verify")
def verify(user: dict = Depends(require_user)):
    """验证 token 有效，返回用户身份"""
    return {"valid": True, "uid": user["uid"], "role": user["role"]}


@app.get("/auth/me")
def me(user: dict = Depends(require_user)):
    """获取当前登录用户的信息"""
    info = auth_util.get_user_info_by_uid(user["uid"])
    if not info:
        raise HTTPException(status_code=404, detail="用户不存在")
    return info


@app.get("/auth/user/{uid}")
def get_user_info(uid: int):
    """根据 uid 查询用户信息（内部调用，无需认证）"""
    info = auth_util.get_user_info_by_uid(uid)
    if not info:
        raise HTTPException(status_code=404, detail="用户不存在")
    return info


@app.get("/auth/user/query/{username}")
def search_user(username: str, user: dict = Depends(require_user)):
    """根据用户名查询用户"""
    uid = auth_util.get_uid_by_user(username)
    if not uid:
        raise HTTPException(status_code=404, detail="用户不存在")
    info = auth_util.get_user_info_by_uid(uid)
    return info


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logger.info(f"my_cfg {my_cfg.get('db')},\n{my_cfg.get('api')}")
    port = get_console_arg1()
    # port = 19011      # 生产环境服务端口
    logger.info(f"auth_service_listen_on_port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
