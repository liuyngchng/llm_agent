#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
pip install mcp_server
pip install mcp_server[cli]

FastMCP quickstart example.
"""
import os
import logging.config
from mcp.server.fastmcp import FastMCP
from mcp.types import Request
from starlette.responses import JSONResponse


app = FastMCP(port=19001, stateless_http=True, json_response=True, host='0.0.0.0')

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


@app.tool(title="获取桌面上的文件列表", description="获取当前用户桌面上的所有文件列表")
def get_desktop_files() -> list:
    """获取桌面上的文件列表"""
    logger.info("trigger_get_desktop_files")
    return os.listdir(os.path.expanduser("~/Desktop"))

@app.tool(title="获取股票市场信息", description="获取当前市场上的股票市场信息")
def get_stock_market_info() -> dict:
    logger.info("trigger_get_stock_market_info")
    return {
        "stock_name": "Apple Inc.",
        "stock_code": "AAPL",
        "stock_price": "123.45",
        "stock_volume": "1000000",
        "stock_change": "1.23%",
    }

@app.tool(title="获取酒店清单", description="根据城市和酒店最高价格，获取符合条件的酒店信息清单")
def get_hotel_by_city_and_price(city: str, max_price: int) -> dict:
    logger.info("trigger_get_hotel_by_city_and_price")
    return {
        "hotel_name": f"Grand Hotel {city}",
        "hotel_address": f"123 Main St, Anytown, {city}",
        "hotel_price": max_price - 10,
        "hotel_rating": "5",
    }


@app.tool(title="获取航班信息", description="根据城市名称，获取当前的有效航班信息")
def get_airline_info_by_city(city: str) -> dict:
    """获取某个城市的航班信息"""
    logger.info(f"trigger_get_airline_info_by_city({city})")
    airline_info = {
        "airline_name": "Delta Airlines",
        "airline_code": "Delta",
        "airline_price": "1000",
        "airline_rating": "5",
    }
    return airline_info

@app.tool(title="获取度假城市列表", description="获取所有适合度假的城市列表")
def get_vocation_city_list() -> list:
    """获取适合度假的城市列表"""
    logger.info("trigger_get_vocation_city_list")
    city_list = [
        "北京",
        "上海",
        "广州",
        "深圳",
        "成都",
        "重庆",
        "西安",
        ]
    return city_list

@app.tool(title="获取天气信息", description="根据城市名称，获取当城市的天气信息，包括温度、风速、湿度、气压、能见度、云量、降水量、露点温度、紫外线指数、降雪深度、日出日落时间")
def get_weather_info_by_city(city: str) -> dict:
    """获取桌面上的文件列表"""
    logger.info(f"trigger_get_weather_info_by_location({city})")
    weather_info = {
        "temperature": "20℃",
        "wind direction":"south east",
        "wind speed": "3m/s",
        "humidity": "60%",
        "atmospheric pressure": "1000hPa",
        "visibility": "1000m",
        "cloudiness": "50%",
        "precipitation": "0.5mm",
        "dew point": "10℃",
        "uv index": "3",
        "snow depth": "0.5mm",
        "sunrise": "06:00",
        "sunset": "18:00",
    }
    return weather_info

@app.resource("file:///path/to/{my_file}", title="文件内容", description="根据文件路径读取文件内容")
def read_file(my_file: str) -> str:
    """
    根据文件路径读取文件内容
    uri = "file:///path/to/file.txt"
    """
    with open(my_file.replace("file://", ""), "r") as f:
        return f.read()

@app.prompt(title="度假计划提示词模板", description="根据城市名称，生成度假计划提示词模板")
def vacation_plan_prompt(city: str) -> str:
    """生成度假计划提示模板"""
    return f"请为{city}设计一个3天的度假计划，包含景点、餐饮和住宿建议"


def start_https_server():
    starlette_app = app.streamable_http_app()
    import uvicorn
    uvicorn.run(
        starlette_app,
        host="0.0.0.0",
        port=19001,
        ssl_keyfile="./cert/srv.key",
        ssl_certfile="./cert/srv.crt",
        log_level="info"
    )

def start_http_server():
    app.run(transport='streamable-http')  # 添加 frontend=False

if __name__ == "__main__":
    logger.info("start mcp_server server demo (backend only)")
    # start_https_server()
    start_http_server()



