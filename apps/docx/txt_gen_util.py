#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
文本生成工具类
"""
import logging.config
import os
import time


from langchain_core.prompts import ChatPromptTemplate

from common import cfg_util, agt_util, cm_utils, statistic_util
from common.cm_utils import rmv_think_block, estimate_tokens

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

def gen_docx_outline_stream(uid:int, doc_type: str, doc_title: str, keywords: str, cfg: dict):
    """
    流式生成docx文档目录
    :doc_type: docx 文档的内容类型，详见:class:`my_enums`WriteDocType
    :doc_title: 文档标题
    :keywords: 文档写作的其他要求关键词
    :cfg: 系统配置
    :is_remote: 是否调用远端LLM
    """
    logger.info(f"doc_type[{doc_type}] , doc_title[{doc_title}], cfg['api']=[{cfg.get('api', None)}]")
    template = cfg_util.get_usr_prompt_template('gen_docx_outline_msg', cfg)
    prompt = ChatPromptTemplate.from_template(cm_utils.replace_spaces(template))
    logger.info(f"prompt {prompt}")
    model = agt_util.get_model(cfg, temperature=0.7)
    # 计算输入 token 数量
    input_text = prompt.format(doc_type=doc_type, doc_title=doc_title, keywords=keywords)
    # logger.info(f"{uid}, start_calc_txt_token, {input_text}")
    input_tokens = estimate_tokens(input_text)
    logger.info(f"{uid}, input_tokens, {input_tokens}")
    statistic_util.add_input_token_by_uid(uid, input_tokens)
    logger.info(f"submit_to_llm, {cfg['api']['llm_api_uri'],}, {cfg['api']['llm_model_name']}, prompt {prompt}")
    try:
        # 流式调用模型
        output_txt = ''
        for chunk in model.stream(input_text):
            if hasattr(chunk, 'content'):
                output_text = cm_utils.rmv_think_block(chunk.content)
                output_txt += chunk.content
                yield output_text
            elif hasattr(chunk, 'text'):
                output_text = cm_utils.rmv_think_block(chunk.text())
                output_txt += chunk.text()
                yield output_text
        output_tokens = estimate_tokens(output_txt[:-1])
        # logger.info(f"{uid}, output_tokens, {output_tokens}")
        logger.info(f"{uid}, gen_doc_outline, {output_txt}")
        statistic_util.add_output_token_by_uid(uid, output_tokens)
    finally:
        # 清理资源
        logger.info("gen_outline_finish, dispose resources")
        dispose(model)

def gen_txt(uid: int, write_context: str, references: str, para_text: str, user_comment: str, catalogue: str,
            current_sub_title: str, cfg: dict, max_retries=6) -> str | None:
    """
    根据提供的三级目录、参考资料，以及每个章节的具体文本写作要求，输出文本
    :param uid:                 用户请求ID
    :param write_context:       整体的写作背景
    :param references:          可供参考的样例子文本
    :param para_text:           局部章节文本的写作要求
    :param user_comment:        用户添加的批注文本
    :param catalogue:           整个文档的三级目录
    :param current_sub_title:   当前写作章节的目录标题
    :param cfg:                 系统配置
    :param max_retries:         最大尝试次数， 需处于集合 [1, 7]
    """
    # logger.info(
    #     f"catalogue[{catalogue}], "
    #     f"user_instruction[{paragraph_prompt}], "
    #     f"demo_txt[{demo_txt}], "
    #     f"current_sub_title[{current_sub_title}]"
    # )
    template = cfg_util.get_usr_prompt_template('gen_txt_msg', cfg)
    prompt = ChatPromptTemplate.from_template(template)
    # logger.debug(f"prompt {prompt}")
    backoff_times = [5, 10, 20, 40, 80, 160]
    if max_retries < 1:
        max_retries = 1
    if max_retries > len(backoff_times):
        max_retries = len(backoff_times)
    last_exception = None
    model = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                time.sleep(backoff_times[attempt - 1])
                logger.info(f"retry #{attempt} times after wait {backoff_times[attempt - 1]}s")
            model = agt_util.get_model(cfg, temperature=1.3)
            chain = prompt | model
            arg_dict = {
                "write_context": write_context,
                "catalogue": catalogue,
                "current_sub_title": current_sub_title,
                "references": references,
                "paragraph_prompt": para_text,
                "user_comment": user_comment,
            }
            # 计算输入 token 数量
            input_text = prompt.format(
                write_context=write_context,
                catalogue=catalogue,
                current_sub_title=current_sub_title,
                references=references,
                paragraph_prompt=para_text,
                user_comment=user_comment,
            )
            # logger.info(f"{uid}, start_calc_txt_token, {input_text}")
            input_tokens = estimate_tokens(input_text)
            logger.info(f"{uid}, input_tokens, {input_tokens}")
            statistic_util.add_input_token_by_uid(uid, input_tokens)
            logger.info(f"gen_txt_arg, {arg_dict}, {cfg['api']['llm_api_uri']}, {cfg['api']['llm_model_name']}")
            response = chain.invoke(arg_dict)
            output_txt = rmv_think_block(response.content)
            output_tokens = estimate_tokens(response.content)
            logger.info(f"{uid}, output_tokens, {output_tokens}")
            statistic_util.add_output_token_by_uid(uid, output_tokens)
            dispose(model)
            output_txt = output_txt.replace(current_sub_title, "").strip()
            return output_txt
        except Exception as ex:
            last_exception = ex
            logger.exception(f"retry_failed_in_gen_txt, retry_time={attempt}, {str(ex)}, {cfg['api']['llm_api_uri']}")
            if attempt < max_retries:
                continue
            dispose(model)
            logger.exception(f"all_retries_exhausted_task_gen_txt_failed, {para_text}")
            raise last_exception
    return None

def dispose(model):
    if 'model' in locals():
        del model
        import torch
        torch.cuda.empty_cache()