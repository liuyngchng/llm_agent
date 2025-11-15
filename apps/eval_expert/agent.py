#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import asyncio
import json
import logging.config
import os
import requests
from typing import List, Dict, Any

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

    def __init__(self, syc_cfg: dict, prompt_padding=""):
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
            self.tools = self.convert_to_basic_tools(available_tools)
            self.tools_description = self.generate_tools_description(available_tools)
            logger.info(f"工具初始化完成: {len(self.tools)} 个工具可用, tools_description: {self.tools_description}")
        except Exception as e:
            logger.error(f"工具初始化失败: {str(e)}")
            self.tools = []
            self.tools_description = "工具初始化失败，将不使用工具功能"

    @staticmethod
    def convert_to_basic_tools(available_tools: List[Dict]) -> List[Dict]:
        """将MCP工具转换为基本工具字典"""
        tools = []
        try:
            for tool_info in available_tools:
                tool_dict = {
                    'name': tool_info['name'],
                    'description': tool_info.get('description', ''),
                    'server': tool_info.get('server'),
                    'inputSchema': tool_info.get('inputSchema', {})
                }
                tools.append(tool_dict)

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
        """获取LLM配置"""
        return agt_util.get_model(self.syc_cfg, temperature=1.3)

    def call_llm_api(self, prompt: str) -> str:
        """直接调用LLM API"""
        try:
            llm_config = self.get_llm()

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {llm_config["api_key"].get_secret_value()}'
            }

            payload = {
                'model': llm_config['model_name'],
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 1.3
            }

            response = requests.post(
                llm_config['api_uri'],
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                # 根据不同的API响应格式提取内容
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                elif 'content' in result:
                    return result['content']
                else:
                    return str(result)
            else:
                error_msg = f"LLM API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return error_msg

        except Exception as e:
            error_msg = f"LLM API调用异常: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建提示词"""
        template_name = 'eval_expert'
        template = cfg_util.get_usr_prompt_template(template_name, self.syc_cfg)
        if not template:
            raise ReferenceError(f"no_prompt_template_config_for {template_name}")

        # 动态替换工具描述
        template = template.replace("{available_tools_description}", self.tools_description)

        # 替换其他变量
        prompt = template.replace("{today}", input_data.get("today", ""))
        prompt = prompt.replace("{domain}", input_data.get("domain", ""))
        prompt = prompt.replace("{review_criteria}", input_data.get("review_criteria", ""))
        prompt = prompt.replace("{project_material_file}", input_data.get("project_material_file", ""))
        prompt = prompt.replace("{msg}", input_data.get("msg", ""))

        logger.debug(f"构建的提示词: {prompt}")
        return prompt

    async def process_with_tools(self, input_data: Dict[str, Any]) -> str:
        """使用工具处理请求"""
        try:
            if not self.tools:
                await self.initialize_tools()

            # 记录工具信息
            logger.info(f"可用工具数量: {len(self.tools)}")
            for tool in self.tools:
                logger.info(f"工具: {tool['name']} - {tool['description']}")

            # 构建提示词
            prompt = self.build_prompt(input_data)

            # 调用LLM API
            response = self.call_llm_api(prompt)

            # 检查响应中是否包含工具调用
            tool_calls = self.extract_tool_calls_from_response(response)

            if tool_calls:
                logger.info(f"检测到工具调用: {len(tool_calls)} 个")
                return await self.handle_tool_calls(tool_calls, input_data)
            else:
                logger.info("未检测到工具调用，直接返回响应内容")
                return response

        except Exception as e:
            logger.error(f"工具处理过程中出错: {str(e)}")
            return f"处理过程中出现错误: {str(e)}"

    def extract_tool_calls_from_response(self, response: str) -> List[Dict]:
        """从LLM响应中提取工具调用信息"""
        tool_calls = []

        try:
            # 简单的工具调用检测逻辑
            # 这里可以根据实际响应格式进行调整
            if "tool_call" in response.lower() or "function" in response.lower():
                # 尝试解析JSON格式的工具调用
                lines = response.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            data = json.loads(line)
                            if 'tool_name' in data or 'function' in data:
                                tool_calls.append(data)
                        except json.JSONDecodeError:
                            continue

            # 如果没有检测到结构化工具调用，但响应中提到了可用工具名称
            if not tool_calls and self.tools:
                for tool in self.tools:
                    if tool['name'].lower() in response.lower():
                        # 创建一个基本的工具调用
                        tool_call = {
                            'name': tool['name'],
                            'args': self.extract_tool_arguments(response, tool['name'])
                        }
                        tool_calls.append(tool_call)

        except Exception as e:
            logger.error(f"提取工具调用失败: {str(e)}")

        return tool_calls

    def extract_tool_arguments(self, response: str, tool_name: str) -> Dict:
        """从响应中提取工具参数"""
        # 简单的参数提取逻辑，可以根据实际需求增强
        args = {}

        # 查找文件路径参数
        if 'file_path' in response.lower() or '文件' in response:
            # 尝试提取文件路径
            import re
            file_patterns = [
                r'file_path[\"\' ]*:[\"\' ]*([^\"\',}\s]+)',
                r'文件[\"\' ]*:[\"\' ]*([^\"\',}\s]+)',
                r'path[\"\' ]*:[\"\' ]*([^\"\',}\s]+)'
            ]

            for pattern in file_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE)
                if matches:
                    args['file_path'] = matches[0]
                    break

        return args

    async def handle_tool_calls(self, tool_calls: List, input_data: Dict[str, Any]) -> str:
        """处理工具调用"""
        try:
            logger.info(f"tool_calls:{tool_calls}, input_data:{input_data}")
            tool_results = []
            available_tool_names = [tool['name'] for tool in self.tools]
            logger.info(f"当前可用工具: {available_tool_names}")

            for tool_call in tool_calls:
                # 处理不同的工具调用格式
                if isinstance(tool_call, dict):
                    if 'name' in tool_call:
                        tool_name = tool_call['name']
                        tool_args = tool_call.get('args', {})
                    elif 'tool_name' in tool_call:
                        tool_name = tool_call['tool_name']
                        tool_args = tool_call.get('parameters', {})
                    else:
                        tool_name = tool_call.get('function', {}).get('name', '')
                        tool_args = tool_call.get('function', {}).get('arguments', {})
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except json.JSONDecodeError:
                                tool_args = {}
                else:
                    continue

                # 关键修复：处理 __arg1 参数格式
                if isinstance(tool_args, dict) and '__arg1' in tool_args:
                    # 将 {'__arg1': 'file_path'} 转换为 {'file_path': 'file_path'}
                    file_path = tool_args['__arg1']
                    tool_args = {'file_path': file_path}
                    logger.info(f"转换参数格式: {tool_args}")

                logger.info(f"执行工具: {tool_name}, 参数: {tool_args}")
                tool = next((t for t in self.tools if t['name'] == tool_name), None)

                if tool:
                    try:
                        # 执行工具调用
                        result = self.execute_tool(tool, tool_args)
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

    def execute_tool(self, tool: Dict, tool_args: Dict) -> str:
        """执行工具调用"""
        try:
            server_addr = tool.get('server')
            if not server_addr:
                return f"工具 {tool['name']} 未配置服务器地址"

            logger.info(f"调用工具 {tool['name']}, 参数: {tool_args}, 服务器: {server_addr}")

            response = requests.post(
                f"{server_addr}/call_tool",
                json={
                    "tool_name": tool['name'],
                    "parameters": tool_args
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json().get('result', '')
                logger.info(f"工具 {tool['name']} 调用成功，结果长度: {len(str(result))}")
                return result
            else:
                error_msg = f"工具调用失败: {response.text}"
                logger.error(f"工具 {tool['name']} 调用失败: {error_msg}")
                return error_msg

        except Exception as e:
            error_msg = f"工具调用异常: {str(e)}"
            logger.error(f"工具 {tool['name']} 调用异常: {error_msg}")
            return error_msg

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

            return self.call_llm_api(final_prompt)

        except Exception as e:
            logger.error(f"生成最终响应时出错: {str(e)}")
            return "处理完成，但生成最终报告时出现错误。"

    @staticmethod
    def get_file_path_msg(categorize_files: dict[str, list[str]], content_type: str) -> list[dict]:
        msg = []
        for file_name in categorize_files.get(content_type, []):
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
        {"file_id": 1763088904912, "file_name": "1763086478215_评审标准.xlsx", "original_name": "评审标准.xlsx"},
        {"file_id": 1763088904924, "file_name": "1763088904924_天然气零售信息系统概要设计.docx",
         "original_name": "天然气零售信息系统概要设计.docx"}
    ]
    agent = EvalExpertAgent(my_cfg)
    logger.info(file_info)
    my_categorize_files = agent.categorize_files(file_info)
    logger.info(my_categorize_files)

    review_criteria_msg = agent.get_file_path_msg(my_categorize_files, "review_criteria")
    project_materials_msg = agent.get_file_path_msg(my_categorize_files, "project_materials")
    logger.info(f"review_criteria_msg={review_criteria_msg}, project_materials_msg={project_materials_msg}")