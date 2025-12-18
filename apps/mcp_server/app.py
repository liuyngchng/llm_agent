#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import os
import logging.config
from mcp.server.fastmcp import FastMCP
from mcp.types import Request
from starlette.responses import JSONResponse
from apps.mcp_server.tools.read_file import get_mcp_tools

# 移除硬编码的端口，让 uvicorn 控制端口
app = FastMCP(stateless_http=True, json_response=True, host='0.0.0.0')

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


@app.custom_route("/", methods=["GET"])
async def root(request: Request):
    """根端点"""
    logger.info(f"trigger_root, {request}")
    return JSONResponse({"status": 200, "msg": "hello mcp world"})


@app.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """健康检查端点"""
    logger.info(f"trigger_health_check, {request}")
    return JSONResponse({"status": "ok"})


@app.custom_route("/tools/list", methods=["GET"])
async def get_tools(request: Request):
    """获取所有tools清单"""
    logger.info(f"trigger_get_tools, {request}")
    tool_list = await app.list_tools()
    serializable_tools = []
    for tool in tool_list:
        serializable_tools.append({
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.inputSchema,
            "outputSchema": tool.outputSchema,
            "annotations": tool.annotations,
            "meta": tool.meta
        })

    return JSONResponse({"tools": serializable_tools})


def add_your_tools():
    """从MCP服务中添加可调用的工具"""
    # 确保工具已经被注册

    mcp_tools = get_mcp_tools()

    if not mcp_tools:
        logger.warning("没有找到注册的MCP工具")
        return

    for name, tool_info in mcp_tools.items():
        app.add_tool(
            tool_info['func'],
            name=name,
            description=tool_info['description'],
            structured_output=True
        )
        logger.info(f"mcp_tools_added: {name}")


def create_starlette_app():
    """创建并配置 Starlette 应用，用于模块化导入"""
    add_your_tools()
    return app.streamable_http_app()


# 用于模块化导入的应用实例
starlette_app = create_starlette_app()

if __name__ == "__main__":
    # 直接运行时使用 HTTPS
    current_dir = os.path.dirname(__file__)
    cert_dir = os.path.join(os.path.dirname(current_dir), '../common', 'cert')
    key_file = os.path.join(cert_dir, 'srv.key')
    cert_file = os.path.join(cert_dir, 'srv.crt')

    import uvicorn

    uvicorn.run(
        starlette_app,
        host="0.0.0.0",
        port=19001,  # 直接运行时使用 19001
        ssl_keyfile=key_file,
        ssl_certfile=cert_file,
        log_level="info"
    )