#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install mcp
pip install mcp[cli]

FastMCP quickstart example.
"""
import json
import os
import logging.config
from mcp.server.fastmcp import FastMCP
from mcp.types import Request
from starlette.responses import JSONResponse

from apps.mcp.tools import db_query

app = FastMCP(port=19001, stateless_http=True, json_response=True, host='0.0.0.0')

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

@app.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """健康检查端点"""
    logger.info(f"trigger_health_check, {request}")
    return JSONResponse({"status": "ok"})

@app.custom_route("/tools", methods=["GET"])
async def get_tools(request: Request):
    """健康检查端点"""
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
    """从MCP注册表中添加工具"""
    for name, tool_info in db_query.MCP_TOOLS.items():
        app.add_tool(
            tool_info['func'],
            name=name,
            title=tool_info['title'],
            description=tool_info['description'],
            structured_output=True
        )
        logger.info(f"Added MCP tool: {name}")

def start_https_server():
    starlette_app = app.streamable_http_app()
    current_dir  = os.path.dirname(__file__)
    logger.info(f"current_dir {current_dir}")
    import uvicorn
    uvicorn.run(
        starlette_app,
        host="0.0.0.0",
        port=19001,
        ssl_keyfile="./common/cert/srv.key",
        ssl_certfile="./common/cert/srv.crt",
        log_level="info"
    )

def start_http_server():
    app.run(transport='streamable-http')  # 添加 frontend=False

if __name__ == "__main__":
    add_your_tools()
    logger.info("start mcp server (backend only)")
    start_https_server()



