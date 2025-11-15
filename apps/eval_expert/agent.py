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
from common.mcp_util import async_get_available_tools
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
        self.tools = []
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
            logger.info(f"工具初始化完成: {len(self.tools)} 个工具可用")
        except Exception as e:
            logger.error(f"工具初始化失败: {str(e)}")
            self.tools = []

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

    def call_llm_api(self, prompt: str) -> str:
        """直接调用LLM API"""
        key = self.llm_api_key.get_secret_value()
        model = self.llm_model_name
        uri = f"{self.llm_api_uri}/chat/completions"
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {key}'
            }

            # 构建消息
            messages = [
                {"role": "user", "content": prompt}
            ]

            # 构建请求体
            payload = {
                'model': model,
                'messages': messages,
                'temperature': 1.3
            }

            # 如果有可用工具，添加到请求中
            if self.tools:
                payload['tools'] = self.convert_tools_to_openai_format()
                # 可选：设置工具调用策略
                payload['tool_choice'] = 'auto'

            logger.info(f"start_request, {uri}, {model}, 工具数量: {len(self.tools)}, 提示词: {prompt[:400]}")
            response = requests.post(
                url=uri,
                headers=headers,
                json=payload,
                timeout=60,
                verify=False,
            )
            logger.info(f"response_status: {response.status_code}, data: {json.dumps(response.json(), ensure_ascii=False)}")
            if response.status_code == 200:
                result = response.json()
                logger.info(f"LLM 响应解析成功")
                return self.parse_llm_response(result)
            else:
                error_msg = f"LLM API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return error_msg
        except Exception as e:
            error_msg = f"LLM API调用异常: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def convert_tools_to_openai_format(self) -> List[Dict]:
        """将工具转换为OpenAI格式"""
        openai_tools = []
        for tool in self.tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool['name'],
                    "description": tool.get('description', ''),
                    "parameters": tool.get('inputSchema', {})
                }
            }
            openai_tools.append(openai_tool)
        return openai_tools

    def parse_llm_response(self, result: Dict) -> str:
        """解析LLM响应"""
        if 'choices' in result and len(result['choices']) > 0:
            choice = result['choices'][0]
            message = choice.get('message', {})

            # 检查是否有工具调用
            if 'tool_calls' in message and message['tool_calls']:
                # 返回工具调用信息，让上层处理
                return json.dumps({
                    'tool_calls': message['tool_calls'],
                    'content': message.get('content', '')
                })
            else:
                # 直接返回文本内容
                return message.get('content', '')
        else:
            return str(result)

    def build_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建提示词"""
        template_name = 'eval_expert'
        template = cfg_util.get_usr_prompt_template(template_name, self.syc_cfg)
        if not template:
            raise ReferenceError(f"no_prompt_template_config_for {template_name}")
        # 替换其他变量
        prompt = template.replace("{today}", str(input_data.get("today", "")))
        prompt = prompt.replace("{domain}", str(input_data.get("domain", "")))
        prompt = prompt.replace("{review_criteria}", str(input_data.get("review_criteria", "")))
        project_material_file = input_data.get("project_material_file", [])
        if isinstance(project_material_file, list):
            project_files_str = ", ".join([
                str(item.get('file_path', '')) if isinstance(item, dict) else str(item)
                for item in project_material_file
            ])
        else:
            project_files_str = str(project_material_file)
        prompt = prompt.replace("{project_material_file}", project_files_str)
        prompt = prompt.replace("{msg}", str(input_data.get("msg", "")))

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
            # 检查是否是结构化的工具调用响应
            if response.startswith('{') and response.endswith('}'):
                try:
                    data = json.loads(response)
                    if 'tool_calls' in data and data['tool_calls']:
                        return data['tool_calls']
                except json.JSONDecodeError:
                    pass

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

    @staticmethod
    def extract_tool_arguments(response: str, tool_name: str) -> Dict:
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
            logger.info(f"tool_calls:{tool_calls}")
            tool_results = []
            available_tool_names = [tool['name'] for tool in self.tools]
            logger.info(f"当前可用工具: {available_tool_names}")

            for tool_call in tool_calls:
                # 处理不同的工具调用格式
                if isinstance(tool_call, dict):
                    # 处理 OpenAI 格式的工具调用
                    if 'function' in tool_call:
                        tool_name = tool_call['function']['name']
                        try:
                            if isinstance(tool_call['function']['arguments'], str):
                                tool_args = json.loads(tool_call['function']['arguments'])
                            else:
                                tool_args = tool_call['function']['arguments']
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"工具参数解析失败: {e}")
                            tool_args = {}
                    elif 'name' in tool_call:
                        tool_name = tool_call['name']
                        tool_args = tool_call.get('args', {})
                    elif 'tool_name' in tool_call:
                        tool_name = tool_call['tool_name']
                        tool_args = tool_call.get('parameters', {})
                    else:
                        continue
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

    @staticmethod
    def execute_tool(tool: Dict, tool_args: Dict) -> str:
        """执行工具调用"""
        try:
            server_addr = tool.get('server')
            if not server_addr:
                return f"工具 {tool['name']} 未配置服务器地址"

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            }

            # 构建符合 JSON-RPC 2.0 标准的请求体
            import uuid
            json_rpc_request = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": tool['name'],
                    "arguments": tool_args
                }
            }

            logger.info(f"调用工具 {server_addr}, {tool['name']}, 参数: {tool_args}")
            response = requests.post(
                f"{server_addr}",
                headers=headers,
                json=json_rpc_request,  # 使用标准的 JSON-RPC 2.0 格式
                timeout=30,
                verify=False
            )

            if response.status_code == 200:
                result_data = response.json()
                # 检查 JSON-RPC 响应格式
                if 'result' in result_data:
                    result = result_data['result']
                    logger.info(f"工具 {tool['name']} 调用成功，结果长度: {len(str(result))}")
                    return result
                elif 'error' in result_data:
                    error_msg = f"工具调用返回错误: {result_data['error']}"
                    logger.error(f"工具 {tool['name']} 调用错误: {error_msg}")
                    return error_msg
                else:
                    error_msg = f"无效的 JSON-RPC 响应格式: {result_data}"
                    logger.error(f"工具 {tool['name']} 响应格式错误: {error_msg}")
                    return error_msg
            else:
                error_msg = f"工具调用失败: {response.status_code} - {response.text}"
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

            请严格按照评审依据与标准模板：
            {input_data.get('review_criteria', '')}
            
            填写模板中的相应内容，给出最终的报告。
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