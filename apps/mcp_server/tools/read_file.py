#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
from common.docx_md_util import get_md_file_catalog, get_md_para_by_heading, get_md_file_content
from typing import Dict, Any, Optional

logging.config.fileConfig("logging.conf", encoding="utf-8")
logger = logging.getLogger(__name__)

# 在模块级别定义 MCP_TOOLS
MCP_TOOLS = {}

def mcp_tool(name: str, title:str, description: str, require_approval: bool = False):
    """装饰器标记函数为MCP工具"""
    def decorator(func):
        MCP_TOOLS[name] = {
            'func': func,
            'name': name,
            'title': title,
            'description': description,
            'require_approval': require_approval,
            'schema': _generate_input_schema(func)
        }
        logger.info(f"Registered MCP tool: {name}")
        return func
    return decorator

def _generate_input_schema(func):
    """根据函数签名生成输入schema"""
    import inspect
    from typing import get_type_hints

    schema = {
        "type": "object",
        "properties": {},
        "required": []
    }

    # 获取函数签名和类型提示
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    for param_name, param in sig.parameters.items():
        if param_name == 'self':  # 跳过self参数
            continue

        param_type = type_hints.get(param_name, str)
        param_default = param.default

        # 类型映射
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array"
        }

        param_info = {
            "type": type_mapping.get(param_type, "string")
        }

        # 添加描述（从docstring中提取）
        if func.__doc__:
            param_info["description"] = f"参数 {param_name}"

        # 处理可选参数
        if param_default == inspect.Parameter.empty:
            schema["required"].append(param_name)
        else:
            param_info["default"] = param_default

        schema["properties"][param_name] = param_info

    return schema


@mcp_tool(
    name="get_markdown_catalog",
    title="获取Markdown文件的目录",
    description="获取Markdown文件的目录结构，返回JSON格式的层级目录",
    require_approval=False
)
def get_markdown_catalog(file_path: str) -> Dict[str, Any]:
    """
    获取Markdown文件的目录结构

    Args:
        file_path: Markdown文件的完整路径

    Returns:
        包含目录结构的字典，包含标题、层级和子章节信息
    """
    logger.info(f"triggered_call, {file_path}")
    try:
        catalog = get_md_file_catalog(file_path)
        logger.info(f"获取目录结构: {file_path}")
        result = {
            "status": "success",
            "data": catalog,
            "file_path": file_path
        }
    except Exception as e:
        logger.error(f"获取目录失败: {file_path}, 错误: {str(e)}")
        result = {
            "status": "error",
            "message": f"获取目录失败: {str(e)}",
            "data": "",
            "file_path": file_path
        }
    logger.info(f"返回结果: {result}")
    return result

@mcp_tool(
    name="get_markdown_content",
    title="获取Markdown文件的内容",
    description="获取Markdown文件的全文文本，如果内容长度大于320KB，则只返回前320KB的内容",
    require_approval=False
)
def get_markdown_content(file_path: str) -> Dict[str, Any]:
    """
    获取Markdown文件的目录结构

    Args:
        file_path: Markdown文件的完整路径

    Returns:
        文件的全文信息
    """
    logger.info(f"triggered_call, {file_path}")
    try:
        content = get_md_file_content(file_path)
        logger.info(f"获取内容: {file_path}")
        result = {
            "status": "success",
            "data": content,
            "file_path": file_path
        }
    except Exception as e:
        logger.error(f"获取内容失败: {file_path}, 错误: {str(e)}")
        result = {
            "status": "error",
            "message": f"获取内容失败: {str(e)}",
            "data": "",
            "file_path": file_path
        }
    logger.info(f"返回结果: {result}")
    return result

@mcp_tool(
    name="get_markdown_section",
    title="获取Markdown文件的特定章节内容",
    description="根据一级标题和可选的二级标题获取Markdown文件特定章节的内容",
    require_approval=False
)
def get_markdown_section(md_file_path: str, heading1: str, heading2: Optional[str] = None) -> Dict[str, Any]:
    """
    获取Markdown文件特定章节的内容

    Args:
        md_file_path: Markdown文件的完整路径
        heading1: 一级标题名称
        heading2: 二级标题名称（可选）

    Returns:
        包含章节内容的字典
    """
    logger.info(f"call_get_markdown_section, {md_file_path}, {heading1}, {heading2}")
    try:
        content = get_md_para_by_heading(md_file_path, heading1, heading2)
        if content:
            logger.info(f"成功获取章节内容: {heading1}" + (f" -> {heading2}" if heading2 else ""))
            result = {
                "status": "success",
                "data": {
                    "heading1": heading1,
                    "heading2": heading2,
                    "content": content
                },
                "file_path": md_file_path
            }
        else:
            logger.warning(f"未找到指定章节: {heading1}" + (f" -> {heading2}" if heading2 else ""))
            result = {
                "status": "not_found",
                "message": "未找到指定章节内容",
                "data": {
                    "heading1": heading1,
                    "heading2": heading2,
                    "content": ""
                },
                "file_path": md_file_path
            }

    except Exception as e:
        logger.error(f"获取章节内容失败: {md_file_path}, 错误: {str(e)}")
        return {
            "status": "error",
            "message": f"获取章节内容失败: {str(e)}",
            "data": {
                "heading1": heading1,
                "heading2": heading2,
                "content": ""
            },
            "file_path": md_file_path
        }
    logger.info(f"返回结果: {result}")
    return result

# 其他辅助函数...
def get_mcp_tools_config() -> Dict[str, Any]:
    """获取MCP工具的完整配置"""
    tools_config = {}

    for tool_name, tool_info in MCP_TOOLS.items():
        tools_config[tool_name] = {
            "description": tool_info["description"],
            "inputSchema": tool_info["schema"],
            "requireApproval": tool_info["require_approval"]
        }
    return tools_config

def execute_mcp_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """执行MCP工具"""
    if tool_name not in MCP_TOOLS:
        return {
            "status": "error",
            "message": f"工具不存在: {tool_name}"
        }

    try:
        tool_func = MCP_TOOLS[tool_name]["func"]
        result = tool_func(**kwargs)
        return result
    except Exception as e:
        logger.error(f"执行工具失败 {tool_name}: {str(e)}")
        return {
            "status": "error",
            "message": f"执行失败: {str(e)}"
        }

# 添加这个函数来确保工具被正确注册
def get_mcp_tools():
    """返回注册的MCP工具"""
    return MCP_TOOLS

if __name__ == "__main__":
    # 测试代码
    tools_config = get_mcp_tools_config()
    logger.info("可用的MCP工具:")
    for name, config in tools_config.items():
        print(f"- {name}: {config['description']}")

    # 测试获取目录
    my_result = get_markdown_catalog("common/output_doc/1.md")
    print(f"目录获取结果: {my_result}")