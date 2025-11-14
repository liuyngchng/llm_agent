#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import logging.config
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import SecretStr

from common import agt_util, cfg_util
from common.docx_util import get_docx_md_txt
from common.sys_init import init_yml_cfg
from common.xlsx_util import get_xlsx_md_txt

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


UPLOAD_FOLDER = 'upload_doc'


class EvalExpertAgent:

    def __init__(self, syc_cfg:dict , prompt_padding=""):
        self.syc_cfg = syc_cfg
        self.llm_api_uri = syc_cfg['api']['llm_api_uri']
        self.llm_api_key = SecretStr(syc_cfg['api']['llm_api_key'])
        self.llm_model_name = syc_cfg['api']['llm_model_name']
        self.llm = self.get_llm()
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

    def get_llm(self):
        return agt_util.get_model(self.syc_cfg, temperature=1.3)

    def get_chain(self):
        template_name = 'eval_expert'
        template = cfg_util.get_usr_prompt_template(template_name, self.syc_cfg)
        if not template:
            raise ReferenceError(f"no_prompt_template_config_for {template_name}")
        logger.debug(f"template {template}")
        prompt = ChatPromptTemplate.from_template(template)
        model = self.get_llm()
        chain = (
            {"domain": RunnablePassthrough(), "review_criteria": RunnablePassthrough(), "project_materials": RunnablePassthrough(),"msg": RunnablePassthrough()}
            | prompt
            | model
            | StrOutputParser()
        )
        return chain

    @staticmethod
    def get_file_content_msg(categorize_files: dict[str, list[str]], content_type: str):
        msg = []
        for file_name in categorize_files.get(content_type):
            logger.info(f"processing_file: {file_name}")
            content = EvalExpertAgent.get_file_content(file_name)
            msg.append({
                'file_name': file_name,
                'content': content
            })
        return msg

    @staticmethod
    def get_file_content(file_name: str):
        """
        根据文件信息获取文件内容
        """
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"文件不存在: {abs_path}")
        # 根据文件扩展名选择处理方法
        file_ext = os.path.splitext(file_name)[1].lower()

        try:
            if file_ext in ['.docx', '.doc']:
                return get_docx_md_txt(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return get_xlsx_md_txt(file_path)
            elif file_ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
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
    categorize_files = agent.categorize_files(file_info)
    logger.info(categorize_files)

    review_criteria_msg = agent.get_file_content_msg(categorize_files, "review_criteria")
    project_materials_msg = agent.get_file_content_msg(categorize_files, "project_materials")
    logger.info(f"review_criteria_msg={review_criteria_msg}, project_materials_msg={project_materials_msg}")