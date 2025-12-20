#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
for test purpose only
pip install mcp_server
pip install mcp_server[cli]

FastMCP quickstart example.
"""

import os
import logging.config
from mcp.server.fastmcp import FastMCP
from mcp.types import Request
from starlette.responses import JSONResponse

app = FastMCP(port=19002, stateless_http=True, json_response=True)  # 初始化 MCP 服务实例
log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


@app.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """健康检查端点"""
    logger.info(f"trigger_health_check, {request}")
    return JSONResponse({"status": "ok"})

@app.tool()
def get_user_info(user_id: str) -> dict:
    """获取用户信息"""
    logger.info("trigger_get_desktop_files")
    return {
        "user_id": user_id,
        "user_name": "<NAME>",
        "user_email": "<EMAIL>",
        "user_phone": "1234567890",
        "user_address": "123 Main St, Anytown, USA",
    }

@app.tool()
def update_user_info(user_id: str, updates: dict):
    """更新用户信息"""
    logger.info(f"trigger_update_user_info, {updates}")
    return {
        "status": "ok",
        "user_info": {
            "user_phone": "1234567890",
        }
    }

@app.tool()
def query_balance(user_id: str) -> dict:
    """查询余额"""
    logger.info(f"trigger_query_balance, {user_id}")
    return {
        "user_id": user_id,
        "balance": 10000,
    }

@app.tool()
def pay_bill(user_id: str, amount: float) -> dict:
    """支付账单"""
    logger.info(f"trigger_pay_bill, {user_id}, {amount}")
    return {
        "status": "ok",
        "balance": 10000 - amount,
    }

@app.tool()
def purchase_gas(user_id: str, volume: float) -> dict:
    """购买燃气"""
    logger.info(f"trigger_purchase_gas, {user_id}, {volume}")
    return {
        "status": "ok",
        "balance": 10000 - volume,
    }

@app.tool()
def get_gas_consumption(user_id: str, start_date: str, end_date: str) -> dict:
    """查询某段时间的燃气消费信息明细"""
    logger.info(f"trigger_get_gas_consumption, {user_id}, {start_date}, {end_date}")
    return {
        "user_id": user_id,
        "gas_consumption": 10000,
    }

@app.tool()
def analyze_consumption_pattern(user_id: str) -> dict:
    """分析燃气消费模式"""
    logger.info(f"trigger_analyze_consumption_pattern, {user_id}")
    return {
        "user_id": user_id,
        "consumption_pattern": "1234567890",
    }

@app.tool()
def report_malfunction(user_id: str, description: str, address: str) -> dict:
    """上报表具故障、管道泄漏、无气等问题"""
    logger.info(f"trigger_report_malfunction, {user_id}, {description}, {address}")
    return {
        "status": "ok",
        "user_id": user_id,
    }

@app.tool()
def query_repair_status(ticket_id: str) -> dict:
    """查询维修工单状态"""
    logger.info(f"trigger_query_repair_status, {ticket_id}")
    return {
        "ticket_id": ticket_id,
        "status": "repairing",
    }

@app.tool()
def get_gas_price(city: str) -> dict:
    """查询燃气价格"""
    logger.info(f"trigger_get_gas_price, {city}")
    return {
        "city": city,
        "price": 2.36,
        "unit":"元/立方米"
    }

@app.tool()
def find_service_centers(user_location: str, service_type: str) -> dict:
    """查询附近的服务中心"""
    logger.info(f"trigger_find_service_centers, {user_location}, {service_type}")
    return {
        "user_location": user_location,
        "service_type": service_type,
        "service_centers": ["1234567890"],
    }

@app.tool()
def get_queue_status(center_id: str) -> dict:
    """查询服务中心排队情况"""
    logger.info(f"trigger_get_queue_status, {center_id}")
    return {
        "center_id": center_id,
        "queue_status": "1234567890",
    }

@app.tool()
def get_safety_tips() -> dict:
    """推送安全用气知识"""
    logger.info(f"trigger_get_safety_tips")
    return {
        "safety_tips": "1234567890",
    }

@app.tool()
def get_emergency_guidance(issue_type: str) -> dict:
    """推送紧急情况下的应急处置步骤指导"""
    logger.info(f"trigger_get_emergency_guidance, {issue_type}")
    return {
        "issue_type": issue_type,
        "emergency_guidance": "1234567890",
    }

@app.tool()
def get_rate_info() -> dict:
    """查询燃气费率信息"""
    logger.info(f"trigger_get_rate_info")
    return {
        "rate_info": "1234567890",
    }

@app.tool()
def get_policy_documents(doc_type: str) -> dict:
    """查询优惠政策文档"""
    logger.info(f"trigger_get_policy_documents, {doc_type}")
    return {
        "doc_type": doc_type,
        "policy_documents": "1234567890",
    }

@app.tool()
def get_setup_instructions(user_id: str) -> dict:
    """查询报装流程"""
    logger.info(f"trigger_get_setup_instructions, {user_id}")
    return {
        "user_id": user_id,
        "setup_instructions": "1234567890",
    }



if __name__ == "__main__":
    logger.info("start mcp_server server (backend only)")
    # 通信协议：transport = 'stdio', 表示使用标准输入输出，也可替换为 HTTP 或 WebSocket
    app.run(transport='streamable-http')  # 添加 frontend=False
