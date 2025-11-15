#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import asyncio
import json
import logging.config
import os
import requests
from typing import List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.tools import BaseTool
from pydantic import SecretStr

from common import agt_util, cfg_util
from common.docx_util import get_docx_md_file_path
from common.mcp_service import async_get_available_tools
from common.sys_init import init_yml_cfg
from common.xlsx_util import get_xlsx_md_file_path

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


UPLOAD_FOLDER = 'upload_doc'


class EvalExpertAgent:

    def __init__(self, syc_cfg:dict , prompt_padding=""):
        self.syc_cfg = syc_cfg
        self.llm_api_uri = syc_cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(syc_cfg['api']['llm_api_key'])
        self.llm_model_name = syc_cfg['api']['llm_model_name']
        self.mcp_servers = syc_cfg.get('mcp', {}).get('servers', [])
        self.llm = self.get_llm()
        self.tools = []
        self.tools_description = "当前无可用工具"
        # 评审标准关键词
        self.standard_keywords = [
            '标准', '要求', '准则', '规范', '指引', '指标',
            'criteria', 'standard', 'requirement', 'guideline',
            'specification', 'rubric', 'evaluation'
        ]

        # 项目材料关键词
        self.material_keywords = [
            '方案', '报告', '材料', '文档', '计划', '提案', '申请', '设计',
            'proposal', 'report', 'material', 'document', 'submission',
            'application', 'plan', 'project'
        ]

        # 排除文件关键词（如模板、样例等）
        self.exclude_keywords = [
            '模板', '样例', '示例', 'sample', 'template', 'example'
        ]

    async def initialize_tools(self):
        """异步初始化工具"""
        try:
            # 动态获取可用工具
            available_tools = await async_get_available_tools(self.mcp_servers)
            logger.info(f"可用工具: {available_tools}")
            self.tools = self.convert_to_langchain_tools(available_tools)
            self.tools_description = self.generate_tools_description(available_tools)
            logger.info(f"工具初始化完成: {len(self.tools)} 个工具可用, tools_description: {self.tools_description}")
        except Exception as e:
            logger.error(f"工具初始化失败: {str(e)}")
            self.tools = []
            self.tools_description = "工具初始化失败，将不使用工具功能"

    @staticmethod
    def convert_to_langchain_tools(available_tools: List[Dict]) -> List[BaseTool]:
        """将MCP工具转换为LangChain工具"""
        tools = []
        try:
            from langchain.tools import Tool

            for tool_info in available_tools:
                # 修复：使用闭包正确捕获 tool_info
                def create_tool_func(tool_info=tool_info):  # 将tool_info作为默认参数固定
                    def tool_function(**kwargs):
                        try:
                            # 调用MCP服务器执行工具
                            server_addr = tool_info.get('server')
                            logger.info(f"调用工具 {tool_info['name']}, 参数: {kwargs}, 服务器: {server_addr}")

                            response = requests.post(
                                f"{server_addr}/call_tool",
                                json={
                                    "tool_name": tool_info['name'],
                                    "parameters": kwargs
                                },
                                timeout=30
                            )
                            if response.status_code == 200:
                                result = response.json().get('result', '')
                                logger.info(f"工具 {tool_info['name']} 调用成功，结果长度: {len(str(result))}")
                                return result
                            else:
                                error_msg = f"工具调用失败: {response.text}"
                                logger.error(f"工具 {tool_info['name']} 调用失败: {error_msg}")
                                return error_msg
                        except Exception as e:
                            error_msg = f"工具调用异常: {str(e)}"
                            logger.error(f"工具 {tool_info['name']} 调用异常: {error_msg}")
                            return error_msg

                    return tool_function

                # 创建工具实例
                tool_func = create_tool_func()  # 调用函数返回实际的工具函数
                tool = Tool(
                    name=tool_info['name'],
                    description=tool_info.get('description', ''),
                    func=tool_func  # 直接传递函数引用
                )
                tools.append(tool)

        except Exception as e:
            logger.error(f"转换工具失败: {str(e)}")

        return tools

    @staticmethod
    def generate_tools_description(available_tools: List[Dict]) -> str:
        """生成工具描述文本用于提示词"""
        if not available_tools:
            return "当前无可用工具"

        descriptions = []
        for tool in available_tools:
            desc = f"- **{tool['name']}**: {tool.get('description', '暂无描述')}"

            if tool.get('inputSchema'):
                input_schema = tool['inputSchema']
                # 提取并格式化参数信息
                params_desc = []
                properties = input_schema.get('properties', {})
                required_params = input_schema.get('required', [])

                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    is_required = param_name in required_params
                    required_mark = "[必需]" if is_required else "[可选]"
                    param_title = param_info.get('title', param_name)
                    params_desc.append(f"{param_name}{required_mark}({param_type}): {param_title}")

                if params_desc:
                    desc += f" 参数: {', '.join(params_desc)}"

            descriptions.append(desc)

        return "\n".join(descriptions)

    def get_llm(self):
        return agt_util.get_model(self.syc_cfg, temperature=1.3)

    def get_chain(self):
        template_name = 'eval_expert'
        template = cfg_util.get_usr_prompt_template(template_name, self.syc_cfg)
        if not template:
            raise ReferenceError(f"no_prompt_template_config_for {template_name}")
        # 动态替换工具描述
        template = template.replace("{available_tools_description}", self.tools_description)
        logger.debug(f"template {template}")
        prompt = ChatPromptTemplate.from_template(template)
        model = self.get_llm()
        # 如果有工具，使用绑定工具的模型
        if self.tools:
            model_with_tools = model.bind_tools(self.tools)
        else:
            model_with_tools = model
        chain = (
            {
                "today": RunnablePassthrough(),
                "domain": RunnablePassthrough(),
                "review_criteria": RunnablePassthrough(),
                "project_material_file": RunnablePassthrough(),
                "msg": RunnablePassthrough()
            }
            | prompt
            | model_with_tools
            | StrOutputParser()
        )
        return chain

    async def process_with_tools(self, input_data: Dict[str, Any]) -> str:
        """使用工具处理请求"""
        try:
            if not self.tools:
                await self.initialize_tools()

            # 记录工具信息
            logger.info(f"可用工具数量: {len(self.tools)}")
            for tool in self.tools:
                logger.info(f"工具: {tool.name} - {tool.description}")

            # 使用与 get_chain 相同的构建方式，但不使用 StrOutputParser
            template_name = 'eval_expert'
            template = cfg_util.get_usr_prompt_template(template_name, self.syc_cfg)
            template = template.replace("{available_tools_description}", self.tools_description)

            prompt = ChatPromptTemplate.from_template(template)
            model = self.get_llm()

            if self.tools:
                model_with_tools = model.bind_tools(self.tools)
            else:
                model_with_tools = model

            # 构建chain但不使用StrOutputParser，以保留原始响应
            chain = (
                    {
                        "today": RunnablePassthrough(),
                        "domain": RunnablePassthrough(),
                        "review_criteria": RunnablePassthrough(),
                        "project_material_file": RunnablePassthrough(),
                        "msg": RunnablePassthrough()
                    }
                    | prompt
                    | model_with_tools
            )

            # 获取原始响应
            response = chain.invoke(input_data)

            # 调试日志：记录完整响应
            logger.info(f"模型完整响应: {response}")
            logger.info(f"响应类型: {type(response)}")
            logger.info(f"响应属性: {dir(response)}")

            # 检查是否有工具调用
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"检测到工具调用: {len(response.tool_calls)} 个")
                return await self.handle_tool_calls(response.tool_calls, input_data)
            elif hasattr(response, 'additional_kwargs') and response.additional_kwargs.get('tool_calls'):
                tool_calls = response.additional_kwargs['tool_calls']
                logger.info(f"检测到工具调用(additional_kwargs): {len(tool_calls)} 个")
                return await self.handle_tool_calls(tool_calls, input_data)
            else:
                logger.info("未检测到工具调用，直接返回响应内容")
                # 返回响应内容
                return response.content if hasattr(response, 'content') else str(response)

        except Exception as e:
            logger.error(f"工具处理过程中出错: {str(e)}")
            return f"处理过程中出现错误: {str(e)}"

    async def handle_tool_calls(self, tool_calls: List, input_data: Dict[str, Any]) -> str:
        """处理工具调用"""
        try:
            logger.info(f"tool_calls:{tool_calls}, input_data:{input_data}")
            tool_results = []
            available_tool_names = [tool.name for tool in self.tools]
            logger.info(f"当前可用工具: {available_tool_names}")
            for tool_call in tool_calls:
                # 处理不同的工具调用格式
                if hasattr(tool_call, 'name'):
                    # 如果是工具调用对象
                    tool_name = tool_call.name
                    # 修复参数提取逻辑
                    if hasattr(tool_call, 'args') and tool_call.args:
                        tool_args = tool_call.args
                    elif hasattr(tool_call, 'kwargs') and tool_call.kwargs:
                        tool_args = tool_call.kwargs
                    else:
                        tool_args = {}
                else:
                    # 如果是字典格式
                    if 'name' in tool_call:
                        tool_name = tool_call['name']
                        # 提取参数
                        if 'args' in tool_call:
                            tool_args = tool_call['args']
                        elif 'kwargs' in tool_call:
                            tool_args = tool_call['kwargs']
                        else:
                            tool_args = {}
                    elif 'function' in tool_call:
                        tool_name = tool_call['function']['name']
                        try:
                            arguments = tool_call['function'].get('arguments', '{}')
                            if isinstance(arguments, str):
                                tool_args = json.loads(arguments)
                            else:
                                tool_args = arguments
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"工具参数解析失败: {e}")
                            tool_args = {}
                    else:
                        tool_name = tool_call.get('name', '')
                        tool_args = tool_call.get('arguments', {})

                # 关键修复：处理 __arg1 参数格式
                if isinstance(tool_args, dict) and '__arg1' in tool_args:
                    # 将 {'__arg1': 'file_path'} 转换为 {'file_path': 'file_path'}
                    file_path = tool_args['__arg1']
                    tool_args = {'file_path': file_path}
                    logger.info(f"转换参数格式: {tool_args}")

                logger.info(f"执行工具: {tool_name}, 参数: {tool_args}")
                tool = next((t for t in self.tools if t.name == tool_name), None)

                if tool:
                    try:
                        # 执行工具调用
                        result = tool.invoke(tool_args)
                        logger.info(f"工具 {tool_name} 调用成功，结果长度: {len(str(result))}")
                        tool_results.append({
                            'tool': tool_name,
                            'result': result
                        })
                    except Exception as e:
                        logger.error(f"工具 {tool_name} 调用失败: {str(e)}")
                        tool_results.append({
                            'tool': tool_name,
                            'result': f"工具调用失败: {str(e)}"
                        })
                else:
                    logger.warning(f"未找到工具: {tool_name}")
                    tool_results.append({
                        'tool': tool_name,
                        'result': f"工具未找到: {tool_name}"
                    })

            if tool_results:
                logger.info(f"工具调用完成，开始生成最终响应")
                return await self.finalize_with_tool_results(input_data, tool_results)
            else:
                return "未执行任何工具调用"

        except Exception as e:
            logger.error(f"处理工具调用时出错: {str(e)}")
            return f"工具调用处理失败: {str(e)}"

    async def finalize_with_tool_results(self, input_data: Dict[str, Any], tool_results: List[Dict]) -> str:
        """使用工具结果生成最终响应"""
        try:
            # 构建包含工具结果的提示词
            tool_results_str = "\n".join([
                f"工具 {result['tool']} 结果: {result['result']}"
                for result in tool_results
            ])

            final_prompt = f"""
            基于原始请求和工具调用结果，请给出最终的评审结论。

            原始请求:
            - 领域: {input_data.get('domain', '')}
            - 评审依据与标准: {input_data.get('review_criteria', '')}
            - 项目材料文件名: {input_data.get('project_material_file', '')}
            - 用户消息: {input_data.get('msg', '')}

            工具调用结果:
            {tool_results_str}

            请基于评审依据与标准给出的模板给出完整的评审报告。
            """

            model = self.get_llm()
            response = model.invoke(final_prompt)
            return response.content if hasattr(response, 'content') else str(response)

        except Exception as e:
            logger.error(f"生成最终响应时出错: {str(e)}")
            return "处理完成，但生成最终报告时出现错误。"

    @staticmethod
    def get_file_path_msg(categorize_files: dict[str, list[str]], content_type: str) -> list[dict]:
        msg = []
        for file_name in categorize_files.get(content_type):
            logger.info(f"processing_file: {file_name}")
            file_path = EvalExpertAgent.get_file_convert_md_file_path(file_name)
            msg.append({
                'file_path': file_path
            })
        return msg

    @staticmethod
    def get_file_convert_md_file_path(file_name: str) -> str:
        """
        根据文件信息获取文件转换为markdown 文件的磁盘路径
        """
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"文件不存在: {abs_path}")
        # 根据文件扩展名选择处理方法
        file_ext = os.path.splitext(file_name)[1].lower()

        try:
            if file_ext in ['.docx', '.doc']:
                return get_docx_md_file_path(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return get_xlsx_md_file_path(file_path)
            elif file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return file_path
            elif file_ext == '.pdf':
                # 如果需要处理PDF，可以在这里添加PDF处理逻辑
                return f"PDF文件内容提取功能待实现: {file_name}"
            else:
                return f"不支持的文件格式: {file_ext}"
        except Exception as e:
            logger.error(f"file_processing_error: {file_name}, {str(e)}")
            return f"文件处理失败 {file_name}: {str(e)}"

    def categorize_files(self, file_infos: list[dict[str, str]]) -> dict[str, list[str]]:
        """
        根据文件名对文件进行分类

        Args:
            file_infos: 文件信息列表 [{"file_id":"my_file_id", "file_name":"my_file_name"}]

        Returns:
            分类后的字典， {"review_criteria":["file_name1", "file_name2"], "project_materials":["file_name3", "file_name4"]}
        """
        standards = []
        materials = []
        uncategorized = []

        for file_item in file_infos:
            file_name = file_item.get('file_name', '').lower()
            # 检查是否为排除文件
            if any(keyword in file_name for keyword in self.exclude_keywords):
                logger.info(f"文件 {file_name} 被排除（模板/样例文件）")
                continue
            if any(keyword in file_name for keyword in self.standard_keywords):
                standards.append(file_item.get('file_name', ''))
                logger.info(f"文件 {file_name} 分类为: 评审标准")
            elif any(keyword in file_name for keyword in self.material_keywords):
                materials.append(file_item.get('file_name', ''))
                logger.info(f"文件 {file_name} 分类为: 项目材料")
            else:
                uncategorized.append(file_item.get('file_name', ''))
        # 记录分类结果
        logger.info(f"分类完成: 评审标准 {len(standards)} 个, "
            f"项目材料 {len(materials)} 个, 未分类 {len(uncategorized)} 个")

        return {
            'review_criteria': standards,
            'project_materials': materials,
            'uncategorized': uncategorized
        }


if __name__ == "__main__":
    my_cfg = init_yml_cfg()
    file_info = [
        {"file_id":1763088904912,"file_name":"1763086478215_评审标准.xlsx","original_name":"评审标准.xlsx"},
        {"file_id":1763088904924,"file_name":"1763088904924_天然气零售信息系统概要设计.docx","original_name":"天然气零售信息系统概要设计.docx"}
    ]
    agent = EvalExpertAgent(my_cfg)
    logger.info(file_info)
    my_categorize_files = agent.categorize_files(file_info)
    logger.info(my_categorize_files)

    review_criteria_msg = agent.get_file_path_msg(my_categorize_files, "review_criteria")
    project_materials_msg = agent.get_file_path_msg(my_categorize_files, "project_materials")
    logger.info(f"review_criteria_msg={review_criteria_msg}, project_materials_msg={project_materials_msg}")