#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
Word 文档文本生成器
"""
import json
import logging.config
import multiprocessing
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Any

import psutil
from xml.etree import ElementTree as ET

from docx import Document
from docx.shared import RGBColor, Cm

from common.docx_cmt_util import refresh_current_heading_xml
from common import cfg_util,docx_meta_util
from apps.docx.txt_gen_util import gen_txt
from common.docx_meta_util import get_doc_info, save_gen_para_txt, get_para_list_with_status, \
    count_mermaid_para, set_doc_info_para_task_created_flag, save_para_task, count_para_task
from common.docx_para_util import get_elapsed_time, get_reference_from_vdb, \
    is_3rd_heading, is_txt_para, refresh_current_heading
from apps.docx.mermaid_render import MermaidRenderer

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


class DocxWriter:
    """
    DOCX文档生成器，使用多线程并行生成文本内容
    1. 任务一共分为3种：
        (1) 只含有目录的 docx 文件；
        (2) 含有目录和段落写作要求文本的 docx 文件;
        (3) 含有word 批注内容的 docx 文件；
    2. 处理文档分为3个步骤：
        (1) 生成并行任务清单；
        (2) 执行并行任务，输出生成的文本集合[{para_idx:para_content}]；
        (3)将文本集合插入到目标Word文档；
    3. 文档处理方法：
        （1）含有批注的文档，需要通过 zipfile 工具解压原始 docx 文件，然后处理xml 来修改 word文档；
        （2）不含批注的文档，则使用 python-docx 处理，按照段落 index，插入相应的段落内容；
    """

    def __init__(self, max_workers=None, timeout=300, consider_memory=True):
        """
        进行类的初始化
        :param max_workers: 固定工作线程数，None则自动计算
        :param timeout: 任务超时时间
        :param consider_memory: 是否考虑内存使用情况
        """
        self.consider_memory = consider_memory

        if max_workers is None:
            max_workers = self._calc_worker()

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.timeout = timeout
        self.lock = threading.Lock()
        self.start_time = None

        logger.info(f"初始化文档生成器 - 工作线程: {self.max_workers}, "
                    f"CPU核心: {multiprocessing.cpu_count()}, "
                    f"内存: {self._get_mem_info()}")

    def _calc_worker(self) -> int:
        """
        基于系统资源动态计算工作线程数
        考虑CPU核心数、内存使用情况等
        """
        try:
            cpu_count = multiprocessing.cpu_count()
            memory_info = DocxWriter._get_mem_usage()
            base_workers = cpu_count
            if self.consider_memory and memory_info['available_percent'] < 20:
                memory_factor = 0.5
                logger.warning(f"系统内存紧张({memory_info['available_percent']:.1f}%)，减少工作线程数")
            elif self.consider_memory and memory_info['available_percent'] < 40:
                memory_factor = 0.8
            else:
                memory_factor = 1.0
            optimal_workers = int(base_workers * memory_factor)
            optimal_workers = max(2, min(optimal_workers, 16))
            logger.info(f"动态计算工作线程 - CPU: {cpu_count}, "
                        f"内存可用: {memory_info['available_percent']:.1f}%, "
                        f"最终线程数: {optimal_workers}")
            return optimal_workers
        except Exception as e:
            logger.warning(f"动态计算工作线程失败，使用默认值: {e}")
            return 4

    @staticmethod
    def _get_mem_usage() -> dict:
        """
        获取系统内存使用情况
        """
        try:
            memory = psutil.virtual_memory()
            return {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'available_percent': (memory.available / memory.total) * 100
            }
        except Exception as e:
            logger.warning(f"获取内存信息失败: {e}")
            return {'available_percent': 100}  # 默认认为内存充足

    @staticmethod
    def _get_mem_info() -> str:
        """获取内存信息字符串"""
        try:
            memory = DocxWriter._get_mem_usage()
            return f"{memory['available_percent']:.1f}%可用"
        except:
            return "未知"

    def fill_doc_with_prompt(self, uid:int, task_id: int, sys_cfg: dict, doc_info: dict) -> str:
        """
        处理有目录并且有段落写作要求的 Word 文档
        :param uid:             user id
        :param task_id:         任务Id
        :param sys_cfg:         系统配置参数
        :param doc_info:       doc_file_info 字典
        """
        input_file_path = doc_info['input_file_path']
        output_file_path = doc_info['output_file_path']
        try:
            logger.info(f"{uid}, {task_id}, 开始处理文档 {input_file_path}")
            if doc_info['is_para_task_created']:
                task_count = count_para_task(task_id)[0]['count(1)']
                logger.info(f"{uid}, {task_id}, para_task_created_ignore_collect_task")
            else:
                task_count = DocxWriter._collect_doc_with_prompt_task(uid, task_id, input_file_path)
            if task_count == 0:
                final_info = f"未检测到需要生成的文本段落"
                docx_meta_util.update_process_info(uid, task_id, final_info, 100)
                import shutil
                shutil.copy2(input_file_path, output_file_path)
                logger.info(f"{uid}, {task_id}, {final_info}, {input_file_path}, 输出文件 {output_file_path}")
                return final_info

            initial_info = f"需处理 {task_count} 个段落，计划启动 {self.executor._max_workers} 个任务"
            logger.info(f"{uid}, {task_id}, {initial_info}")
            docx_meta_util.update_process_info(uid, task_id, initial_info)

            doc_gen_results = self._submit_tasks(uid, task_id, doc_info, sys_cfg, include_mermaid=True)
            success = DocxWriter._insert_para_to_doc(uid, task_id)
            if not success:
                error_info = "文档更新失败"
                logger.error(f"{uid}, {task_id}, {error_info}")
                docx_meta_util.update_process_info(uid, task_id, error_info, 100)
                return error_info
            logger.info(f"{uid}, {task_id}, 保存文档完成，{output_file_path}, 耗时 {get_elapsed_time(doc_info['start_time'])}")
            # 计算详细统计信息
            success_count = len([r for r in doc_gen_results.values() if r.get('success')])
            failed_count = task_count - success_count
            # 处理Mermaid图表
            img_count = 0
            try:
                logger.info(f"{uid}, {task_id}, 开始处理文档中的Mermaid图表")
                current_info = docx_meta_util.get_doc_info(task_id)
                process_info = f"{current_info[0]['process_info']}, 开始处理文档配图"
                docx_meta_util.update_process_info(uid, task_id, process_info, 95)
                mermaid_process_info = DocxWriter._submit_mermaid_task(
                    uid, task_id,
                    output_file_path,
                    sys_cfg['api']['mermaid_api_uri']
                )
                img_count = mermaid_process_info.get('img_count', 0)
                docx_meta_util.update_img_count_by_task_id(task_id, img_count)
                if not mermaid_process_info['success']:
                    failed_count += 1
                logger.info(f"{uid}, {task_id}, Mermaid图表处理完成, {json.dumps(mermaid_process_info, ensure_ascii=False)}")
            except Exception as e:
                failed_count += 1
                logger.error(f"{uid}, {task_id}, Mermaid图表处理失败: {str(e)}")
            total_time = get_elapsed_time(doc_info['start_time'])
            final_info = (f"文档处理完成，共执行 {task_count} 个文本生成任务，"
                          f"成功生成 {success_count} 段文本和 {img_count} 张配图，失败任务 {failed_count} 个，{total_time}")
            if failed_count > 0:
                final_info += f"，失败任务的原因可在日志中查看具体的失败原因"
            docx_meta_util.update_process_info(uid, task_id, final_info, 100)
            logger.info(f"{uid}, {task_id}, {final_info}，输出文件: {output_file_path}")
            return final_info
        except Exception as e:
            error_info = f"文档生成过程出现异常: {str(e)}"
            logger.error(f"{uid}, {task_id}, {error_info}")
            docx_meta_util.update_process_info(uid, task_id, error_info, 100)
            return error_info

    @staticmethod
    def _collect_doc_with_prompt_task(uid: int, task_id: int, input_file_path: str) -> int:
        """
        生成含有目录和段落写作指导的 docx 文档的各个段落文本生成任务，返回总任务数
        :param uid: user id
        :param task_id: doc task id
        :param input_file_path: 输入文件的磁盘绝对路径
        return 生成的任务数量
        """
        logger.info(f"{uid}, {task_id}, start_gen_doc_task")
        tasks = []
        current_heading = []
        doc = Document(input_file_path)
        para_count = len(doc.paragraphs)
        for index, para in enumerate(doc.paragraphs):
            refresh_current_heading(para, current_heading)
            check_if_txt_para = is_txt_para(para, current_heading)
            if not check_if_txt_para:
                logger.info(f"{task_id}, 跳过非描述性的文本段落 {para.text}")
                continue
            task_key =  f"para_{index}"
            task = {
                'unique_key': task_key,
                'para_text': para.text,
                'user_comment': "",
                'current_sub_title': current_heading[0] if current_heading else "",
                'current_heading': current_heading.copy(),
                'para_id': index,
            }
            tasks.append(task)
        process_info = f"扫描了 {para_count} 段文本， 已创建 {len(tasks)} 个批处理任务"
        docx_meta_util.update_process_info(uid, task_id, process_info)
        logger.info(f"{uid}, {task_id}, start_save_doc_task")
        docx_meta_util.save_para_task(uid, task_id, tasks)
        set_doc_info_para_task_created_flag(uid, task_id)
        logger.info(f"{uid}, {task_id}, gen_doc_task_count, {len(tasks)}")
        return len(tasks)

    def _submit_tasks(self, uid: int, task_id: int, doc_info: dict, sys_cfg: dict,
            include_mermaid: bool = False) -> dict[str, dict]:
        """
        提交文本生成任务，开始并行处
        :param uid: user id
        :param task_id: 任务ID
        :param doc_info: docx_file_info 字典
        :param sys_cfg: 系统配置信息
        :param include_mermaid: 是否包含Mermaid处理任务
        :return 执行完任务的结果
        """
        start_time = doc_info['start_time']
        results = {}
        completed = 0
        future_to_key = {}
        last_update_time = time.time()
        para_info_list = get_para_list_with_status(task_id, 0, False)
        if not para_info_list:
            logger.warning(f"{uid}, {task_id}, 未找到文档的段落任务信息")
            return {}
        total_tasks = len(para_info_list)
        logger.debug(f"{uid}, para_tasks_count, {total_tasks}")
        actual_total_tasks = total_tasks + 1 if include_mermaid else total_tasks
        # 提交所有任务到线程池
        for para_info in para_info_list:
            future = self.executor.submit(DocxWriter._gen_doc_para, doc_info, para_info, sys_cfg)
            future_to_key[future] = para_info['unique_key']
        # 监控任务进度并收集结果
        try:
            for future in as_completed(future_to_key, timeout=self.timeout):
                key = future_to_key[future]
                try:
                    result = future.result()
                    results[key] = result
                except Exception as e:
                    logger.error(f"{uid}, {task_id}, 段落生成失败 {key}: {str(e)}")
                    results[key] = {
                        'success': False,
                        'error': str(e),
                    }

                completed += 1
                update_interval = 2
                current_time = time.time()
                if current_time - last_update_time >= update_interval or completed == total_tasks:
                    percent = int(completed / actual_total_tasks * 100)
                    elapsed_time = get_elapsed_time(start_time)
                    if completed > 0:
                        elapsed_seconds = (time.time() * 1000 - start_time) / 1000
                        avg_time_per_task = elapsed_seconds / completed
                        remaining_tasks = actual_total_tasks - completed
                        estimated_remaining = avg_time_per_task * remaining_tasks
                        if estimated_remaining < 60:
                            remaining_str = f"约 {int(estimated_remaining)} 秒"
                        else:
                            remaining_str = f"约 {int(estimated_remaining / 60)} 分 {int(estimated_remaining % 60)} 秒"
                        progress_info = f"正在处理第 {completed}/{actual_total_tasks} 个任务，{elapsed_time}，剩余{remaining_str}"
                    else:
                        progress_info = f"正在处理第 {completed}/{actual_total_tasks} 个任务，{elapsed_time}"
                    docx_meta_util.update_process_info(uid, task_id, progress_info, percent)
                    last_update_time = current_time

        except TimeoutError:
            logger.warning(f"{uid}, {task_id}, 总体任务执行超时，取消未完成的任务")
            # 在 as_completed 外部取消未完成的任务
            cancelled_count = 0
            completed_before_timeout = completed
            for future, key in future_to_key.items():
                if not future.done():
                    future.cancel()
                    cancelled_count += 1
                    results[key] = {
                        'success': False,
                        'error': '任务执行超时被取消',
                    }
            logger.info(
                f"{uid}, {task_id}, 超时前已完成 {completed_before_timeout} 个任务，已取消 {cancelled_count} 个超时任务")

            # 更新最终进度信息
            timeout_info = f"任务执行超时，已完成 {completed_before_timeout}/{total_tasks} 个任务，{cancelled_count} 个任务因超时取消"
            docx_meta_util.update_process_info(uid, task_id, timeout_info)
        return results

    @staticmethod
    def _gen_doc_para(doc_info:dict[str, Any], para_info: dict[str, Any], sys_cfg: dict) -> dict:
        """
        按照指定的要求生成单个段落的文本和图表（支持Mermaid图表）
        """
        task_id = para_info['task_id']
        if not task_id:
            logger.error(f"task_id_null_exception, {para_info}")
            raise RuntimeError('task_id_null_exception')
        para_id = para_info['para_id']
        uid = para_info['uid']
        current_sub_title = para_info['current_sub_title']

        vdb_dir = doc_info['vdb_dir']
        doc_ctx = doc_info['doc_ctx']
        doc_outline = doc_info['doc_outline']
        try:
            # 获取参考文本
            references = get_reference_from_vdb(
                para_info['para_text'],
                vdb_dir,
                sys_cfg['api']
            )
            logger.debug(f"gen_txt_user_comment, {para_info['user_comment']}")
            llm_txt = gen_txt(
                uid=uid,
                write_context=doc_ctx,
                references=references,
                para_text=para_info['para_text'],
                catalogue=doc_outline,
                current_sub_title=current_sub_title,
                user_comment=para_info['user_comment'],
                cfg=sys_cfg
            )
            logger.info(f"{uid}, {task_id}, {para_id}, gen_txt, {llm_txt}")
            word_count = len(llm_txt)
            if '<mermaid>' in llm_txt:
                contains_mermaid = 1
            else:
                contains_mermaid = 0
            save_gen_para_txt(task_id, para_id, llm_txt, word_count, contains_mermaid)
            logger.info(f"{uid}, {task_id}, {para_id}, save_para_info_after_gen_doc_para, {llm_txt}")
            return {
                "success": True
            }
        except Exception as e:
            logger.exception(f"{uid}, {task_id}, {para_id},生成段落文本失败: {str(e)}, current_sub_title, {current_sub_title}")
            raise

    @staticmethod
    def _submit_mermaid_task(uid: int, task_id: int, output_file_path: str, mermaid_api_uri: str,) -> dict[str, Any]:
        """
        提交处理文档中的Mermaid script 脚本的任务
        :return: 处理结果信息
        """
        doc_para_mermaid_count = count_mermaid_para(task_id)
        mermaid_count = doc_para_mermaid_count[0][0]
        logger.debug(f"mermaid_count = {mermaid_count}")
        try:
            if mermaid_count > 0:
                logger.info(f"{uid}, {task_id}, 检测到文档包含Mermaid图表 {mermaid_count}，开始处理: {output_file_path}")
                mermaid_instance = MermaidRenderer(kroki_url=mermaid_api_uri)
                img_count = mermaid_instance.batch_process_mermaid_in_docx(task_id, output_file_path)
                logger.info(f"{uid}, {task_id}, 文档包含Mermaid图表处理完成: {output_file_path}")
                return {
                    'success': True,
                    'mermaid_count': mermaid_count,
                    'has_mermaid': True,
                    'img_count': img_count,
                }
            else:
                logger.info(f"{uid}, {task_id}, 文档未包含Mermaid图表，跳过处理: {output_file_path}")
                return {
                    'success': True,
                    'mermaid_count': 0,
                    'has_mermaid': False,
                    'img_count': 0,
                }
        except Exception as e:
            logger.error(f"{uid}, {task_id}, 处理Mermaid图表时发生异常: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'img_count': 0,
            }

    @staticmethod
    def _insert_para_to_doc(uid: int, task_id: int) -> bool:
        """
        将生成的文本结果集合，按照段落索引插入到文档的指定位置
        :param uid: user id
        :param task_id: 生成文本的任务ID
        """
        doc_file_info = get_doc_info(task_id)
        input_file_path = doc_file_info[0]['input_file_path']
        output_file_path = doc_file_info[0]['output_file_path']
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"{uid}, {task_id}, 创建输出目录: {output_dir}")
        # 已经是按照 para_id 倒序排列的 list了， 可以直接遍历
        doc_para_info_list = get_para_list_with_status(task_id, 1)
        try:
            doc = Document(input_file_path)
            paragraphs = doc.paragraphs
            if not doc_para_info_list or not doc_para_info_list[0]:
                logger.warning(f"{uid}, {task_id}, 没有有效的生成结果需要插入, 保存原始文档:{input_file_path}  至 {output_file_path}")
                doc.save(output_file_path)
                return True
            # 从后往前插入，避免索引变化
            for item in doc_para_info_list:
                para_id = item['para_id']
                para_gen_txt = item['gen_txt']
                if para_id >= len(paragraphs):  # 添加边界检查
                    logger.warning(f"{uid}, {task_id}, 段落索引 {para_id} 超出范围（总段落数：{len(paragraphs)}），跳过, input_file={input_file_path}")
                    continue
                original_para = paragraphs[para_id]

                # 创建新段落并插入
                new_para = doc.add_paragraph()
                new_para.paragraph_format.first_line_indent = Cm(1)
                red_run = new_para.add_run(para_gen_txt)
                red_run.font.color.rgb = RGBColor(0, 0, 0)

                # 插入到原始段落后面
                original_para._p.addnext(new_para._p)
                logger.debug(f"{uid}, {task_id}, 已在段落 {para_id} 后插入生成内容")
            doc.save(output_file_path)
            logger.info(f"{uid}, {task_id}, 使用段落索引更新文档成功: {output_file_path}")
            return True
        except Exception as e:
            logger.exception(f"{uid}, {task_id}, 使用段落索引更新文档失败: input_file={input_file_path}, output_doc={output_file_path}")
            return False

    def modify_doc_with_comment(self, uid: int, task_id: int, sys_cfg: dict, doc_info: dict, comments_dict: dict) -> str:
        """
        处理添加了Word批注的文档,采用直接修改xml的方式修改 word文档，保证与提取批注的方式一致
        :param uid:             用户 ID
        :param task_id:         执行任务的ID
        :param sys_cfg:             系统配置，用于使用大模型的能力
        :param doc_info:       docx_file_info 字典
        :param comments_dict:   段落ID和段落批注的对应关系字典
        """
        input_file_path = doc_info['input_file_path']
        output_file_path = doc_info['output_file_path']
        if not os.path.exists(input_file_path):
            error_info = f"输入文件不存在, file_not_exists, {input_file_path}"
            logger.error(f"{uid}, {task_id}, {error_info}")
            docx_meta_util.update_process_info(uid, task_id, error_info, 100)
            return error_info
        if not comments_dict:
            warning_info = "文件里未找到批注信息, no_comment_found"
            logger.warning(f"{uid}, {task_id}, {warning_info}, {input_file_path}")
            docx_meta_util.update_process_info(uid, task_id, warning_info, 100)
            return warning_info
        logger.debug(f"{uid}, {task_id}, comments_dict: {comments_dict}")
        try:
            info = f"处理带批注的文档 {input_file_path}，共找到 {len(comments_dict)} 个批注"
            logger.info(f"{uid}, {task_id}, {info}")
            docx_meta_util.update_process_info(uid, task_id, info)
            if doc_info['is_para_task_created']:
                task_count = count_para_task(task_id)[0]['count(1)']
                logger.info(f"{uid}, {task_id}, para_task_created_ignore_collect_task")
            else:
                task_count = DocxWriter._collect_doc_with_comment_task(uid, task_id, comments_dict, input_file_path)
            if task_count == 0:
                final_info = "未找到有效的批注处理任务"
                logger.info(f"{uid}, {task_id}, {final_info}")
                docx_meta_util.update_process_info(uid, task_id, final_info, 100)
                import shutil
                shutil.copy2(input_file_path, output_file_path)
                return final_info
            initial_info = f"需处理 {task_count} 个批注段落，启动 {self.executor._max_workers} 个任务"
            logger.info(f"{uid}, {task_id}, {initial_info}")
            docx_meta_util.update_process_info(uid, task_id, initial_info)
            doc_gen_results = self._submit_tasks(uid, task_id, doc_info, sys_cfg, include_mermaid=True)
            success = DocxWriter._update_doc_with_comments(uid, task_id, doc_info)
            if not success:
                error_info = "XML方式更新文档失败"
                logger.error(f"{uid}, {task_id}, {error_info}")
                docx_meta_util.update_process_info(uid, task_id, error_info, 100)
                return error_info
            logger.info(f"{uid}, {task_id}, 保存批注处理文档完成: {output_file_path}")
            # 统计结果
            success_count = len([r for r in doc_gen_results.values() if r.get('success')])
            failed_count = task_count - success_count
            # 处理Mermaid图表
            img_count = 0
            try:
                logger.info(f"{uid}, {task_id}, 开始处理文档中的Mermaid图表")
                current_info = docx_meta_util.get_doc_info(task_id)
                process_info = f"{current_info[0]['process_info']}, 开始处理文档配图"
                docx_meta_util.update_process_info(uid, task_id, process_info, 95)
                mermaid_process_info = DocxWriter._submit_mermaid_task(
                    uid, task_id, output_file_path, sys_cfg['api']['mermaid_api_uri']
                )
                img_count = mermaid_process_info.get('img_count', 0)
                docx_meta_util.update_img_count_by_task_id(task_id, img_count)
                if not mermaid_process_info['success']:
                    failed_count += 1
                logger.info(f"{uid}, {task_id}, Mermaid图表处理完成")
            except Exception as e:
                failed_count += 1
                logger.error(f"{uid}, {task_id}, Mermaid图表处理失败: {str(e)}")
            total_time = get_elapsed_time(doc_info['start_time'])
            final_info = (f"批注文档处理完成，共处理 {task_count} 个批注段落，"
                f"成功生成 {success_count} 段文本和 {img_count} 张配图，失败 {failed_count} 段，{total_time}")
            if failed_count > 0:
                final_info += "，失败段落可在日志中查看详情"
            docx_meta_util.update_process_info(uid, task_id, final_info, 100)
            logger.info(f"{uid}, {task_id}, {final_info}，输出文件: {output_file_path}")
            return final_info
        except Exception as e:
            error_info = f"批注文档处理过程出现异常: {str(e)}"
            logger.error(f"{uid}, {task_id}, {error_info}")
            docx_meta_util.update_process_info(uid, task_id, error_info, 100)
            return error_info

    @staticmethod
    def _update_doc_with_comments(uid: int, task_id: int, file_info: dict) -> bool:
        """
        使用 XML 方式更新文档中的批注段落的内容
        :param uid: user id
        :param task_id: 任务ID
        :param file_info: docx_file_info 字典
        """
        import shutil
        import tempfile
        temp_dir = None
        input_file_path = file_info['input_file_path']
        output_file_path = file_info['output_file_path']
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"{uid}, {task_id}, 创建输出目录: {output_dir}")
        docx_para_list = get_para_list_with_status(task_id,0)
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            # 解压 docx 文件
            with zipfile.ZipFile(input_file_path, 'r') as z:
                z.extractall(temp_dir)
            # 读取并修改 document.xml
            document_xml_path = os.path.join(temp_dir, 'word/document.xml')
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            # 注册命名空间
            for prefix, uri in namespaces.items():
                ET.register_namespace(prefix, uri)
            # 解析文档
            tree = ET.parse(document_xml_path)
            root = tree.getroot()
            # 查找所有段落
            paragraphs = root.findall('.//w:p', namespaces)
            modified_count = 0

            for item in docx_para_list:
                para_id = item['para_id']
                para_gen_txt = item['gen_txt']
                if para_id is None or para_id >= len(paragraphs):
                    logger.warning(f"{uid}, {task_id}, 段落索引 {para_id} 超出范围，跳过")
                    continue
                paragraph = paragraphs[para_id]
                logger.debug(
                    f"{uid}, {task_id}, 处理段落 {para_id}: 原始文本长度={len(paragraph.findall('.//w:t', namespaces))},"
                    f" 新文本长度={len(para_gen_txt)}"
                )
                # 更新段落文本
                if DocxWriter._update_para_txt_xml(uid, task_id, paragraph, para_gen_txt, namespaces):
                    modified_count += 1
                    logger.debug(f"{uid}, {task_id}, 已更新段落 {para_id}")

            # 保存修改后的 XML
            tree.write(document_xml_path, encoding='UTF-8', xml_declaration=True)

            # 重新打包为 docx
            with zipfile.ZipFile(output_file_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
                for root_dir, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        arc_name = os.path.relpath(file_path, temp_dir)
                        z_out.write(file_path, arc_name)

            logger.info(f"{uid}, {task_id}, XML方式更新文档完成，共修改 {modified_count} 个段落")
            return True

        except Exception as e:
            logger.error(f"XML方式更新文档时出错: {str(e)}", exc_info=True)
            return False
        finally:
            # 清理临时文件
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    @staticmethod
    def _update_para_txt_xml(uid: int, task_id: int, paragraph, new_text: str, namespaces: dict) -> bool:
        """
        更新 XML 段落中的文本内容
        """
        try:
            # 找到所有的文本元素
            text_elements = paragraph.findall('.//w:t', namespaces)

            if text_elements:
                # 更新第一个文本元素
                text_elements[0].text = f"{cfg_util.AI_GEN_TAG}{new_text}"
                for text_elem in text_elements[1:]:
                    parent_elem = paragraph.find(f'.//w:t[@text="{text_elem.text}"]/..')
                    if parent_elem is not None:
                        # 检查父元素是否还有其他子元素
                        if len(parent_elem) == 1:  # 如果只有文本元素，清空文本
                            text_elem.text = ""
                        else:  # 如果有其他子元素，删除文本元素
                            parent_elem.remove(text_elem)
                return True
            else:
                # 如果没有文本元素，创建新的 run 和 text
                run = ET.SubElement(paragraph, f'{{{namespaces["w"]}}}r')
                text_elem = ET.SubElement(run, f'{{{namespaces["w"]}}}t')
                text_elem.text = f"{cfg_util.AI_GEN_TAG}{new_text}"
                return True

        except Exception as e:
            logger.error(f"{uid}, {task_id}, 更新段落文本时出错: {str(e)}")
            return False

    @staticmethod
    def _collect_doc_with_comment_task(uid: int, task_id: int, comments_dict: dict, input_file_path: str) -> int:
        """
        收集含有批注的文档的并行处理任务清单（XML版本）
        :param task_id, 任务ID
        :param comments_dict: 文档批注信息
        :param input_file_path, 需要处理的文件的绝对路径
        """
        tasks = []
        current_heading = []
        logger.info(f"{uid}, {task_id}, 开始收集批注任务，批注字典: {comments_dict}")
        try:
            with zipfile.ZipFile(input_file_path) as z:
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

                # 解析文档结构
                with z.open('word/document.xml') as f:
                    doc_xml = ET.fromstring(f.read())
                    paragraphs = doc_xml.findall('.//w:p', namespaces)
                    para_count = len(paragraphs)
                    logger.info(f"{task_id}, 共 {para_count} 个 XML 段落")
                    for para_id, paragraph in enumerate(paragraphs):
                        # 提取段落文本内容
                        para_text = ' '.join(
                            t.text.strip()
                            for t in paragraph.findall('.//w:t', namespaces)
                            if t.text and t.text.strip()
                        )
                        logger.debug(f"{uid}, {task_id}, para_id: {para_id}, para_text: '{para_text}'")
                        # 更新当前标题（需要从 XML 中判断标题样式）
                        refresh_current_heading_xml(paragraph, current_heading, namespaces)
                        # 检查当前段落是否有批注
                        if para_id not in comments_dict:
                            logger.debug(f"{uid}, {task_id}, 段落 {para_id} 无批注，跳过")
                            continue
                        comment_text = comments_dict[para_id]
                        if not comment_text or not comment_text.strip():
                            logger.debug(f"{uid}, {task_id}, 跳过无批注内容段落: {para_text}")
                            continue
                        task = {
                            'task_id': task_id,
                            'unique_key': f"comment_{para_id}",
                            'para_text': para_text,
                            'user_comment': comment_text,
                            'current_sub_title': current_heading[0] if current_heading else "",
                            'current_heading': current_heading.copy(),
                            'para_id': para_id,
                            'namespaces': namespaces,           # 添加命名空间信息
                        }
                        logger.debug(f"{uid}, {task_id}, 创建批注任务: {task['user_comment']}")
                        tasks.append(task)
                    process_info = f"扫描了 {para_count} 段文本， 已创建 {len(tasks)} 个批处理任务"
                    docx_meta_util.update_process_info(uid, task_id, process_info)
                    logger.info(f"{uid}, {task_id}, start_save_doc_file_info_task")
                    save_para_task(uid, task_id, tasks)
                    set_doc_info_para_task_created_flag(uid, task_id)
                    logger.info(f"{uid}, {task_id}, gen_doc_task_count, {len(tasks)}")
            return len(tasks)
        except Exception as e:
            logger.error(f"{uid}, {task_id}, 解析文档 XML 时出错: {str(e)}", exc_info=True)
            return 0


    def fill_doc_without_prompt(self, uid: int, task_id: int, sys_cfg: dict, doc_info: dict) -> str:
        """
        处理只有三级目录，没有任何写作要求段落的word文档
        :param uid: user id
        :param task_id: 执行任务的ID
        :param sys_cfg: 系统配置信息
        :param doc_info: docx_file_info 字典

        """
        input_file_path = doc_info['input_file_path']
        output_file_path = doc_info['output_file_path']

        try:
            logger.info(f"{uid}, 开始处理无提示词文档 {input_file_path}")
            if doc_info['is_para_task_created']:
                task_count = count_para_task(task_id)[0]['count(1)']
                logger.info(f"{uid}, {task_id}, para_task_created_ignore_collect_task, task_count={task_count}")
            else:
                task_count = DocxWriter._collect_doc_without_prompt_task(uid, task_id, input_file_path)
            if task_count == 0:
                final_info = f"未找到三级标题，输出文档： {output_file_path}"
                logger.info(f"{uid}, {final_info}")
                docx_meta_util.update_process_info(uid, task_id, final_info, 100)
                import shutil
                shutil.copy2(input_file_path, output_file_path)
                return final_info

            initial_info = f"需处理 {task_count} 个三级标题，启动 {self.executor._max_workers} 个任务"
            logger.info(f"{uid}, {initial_info}")
            docx_meta_util.update_process_info(uid, task_id, initial_info)
            doc_gen_results = self._submit_tasks(uid, task_id, doc_info, sys_cfg, include_mermaid=True)
            success = DocxWriter._insert_para_to_doc(uid, task_id)
            if not success:
                error_info = "文档更新失败"
                logger.error(f"{uid}, {task_id}, {error_info}")
                return error_info
            logger.info(f"{uid}, 保存无提示词文档完成: {output_file_path}")
            success_count = len([r for r in doc_gen_results.values() if r.get('success')])
            failed_count = task_count - success_count
            # 处理Mermaid图表
            img_count = 0
            try:
                logger.info(f"{uid}, {task_id}, 开始处理文档中的Mermaid图表")
                current_info = docx_meta_util.get_doc_info(task_id)
                process_info = f"{current_info[0]['process_info']}, 开始处理文档配图"
                docx_meta_util.update_process_info(uid, task_id, process_info, 95)
                mermaid_process_info = DocxWriter._submit_mermaid_task(
                    uid, task_id, output_file_path, sys_cfg['api']['mermaid_api_uri']
                )
                img_count = mermaid_process_info.get('img_count', 0)
                docx_meta_util.update_img_count_by_task_id(task_id, img_count)
                if not mermaid_process_info['success']:
                    failed_count += 1
                logger.info(f"{uid}, {task_id}, Mermaid图表处理完成, {json.dumps(mermaid_process_info, ensure_ascii=False)}")
            except Exception as e:
                failed_count += 1  # 将Mermaid处理失败计入总失败数
                logger.error(f"{uid}, {task_id}, Mermaid图表处理失败: {str(e)}")
            total_time = get_elapsed_time(doc_info['start_time'])
            final_info = (f"文档处理完成，共执行 {task_count} 个文本生成任务，"
                f"成功生成 {success_count} 段文本和 {img_count} 张配图，失败 {failed_count} 段，{total_time}")

            if failed_count > 0:
                final_info += ", 失败标题可在日志中查看详情"

            docx_meta_util.update_process_info(uid, task_id, final_info, 100)
            logger.info(f"{uid}, {task_id}, {final_info}，输出文件: {output_file_path}")
            return final_info
        except Exception as e:
            error_info = f"文档生成过程出现异常: {str(e)}"
            logger.error(f"{uid}, {task_id}, {error_info}")
            docx_meta_util.update_process_info(uid, task_id, error_info, 100)
            return error_info

    @staticmethod
    def _collect_doc_without_prompt_task(uid: int, task_id: int, input_file_path: str) -> int:
        """
        对于只含有目录的文档，收集需处理的段落生成任务
        :param uid: user id
        :param task_id: 任务ID
        :param input_file_path: 输入文件的绝对路径
        """
        doc = Document(input_file_path)
        current_heading = []
        tasks = []
        for para_id, para in enumerate(doc.paragraphs):
            refresh_current_heading(para, current_heading)
            if not is_3rd_heading(para):
                continue
            task = {
                'task_id': task_id,
                'unique_key': f"heading_{para_id}",
                'para_text': "",
                'user_comment': "",
                'current_sub_title': para.text,
                'current_heading': current_heading.copy(),
                'para_id': para_id,
            }
            tasks.append(task)
        docx_meta_util.save_para_task(uid, task_id, tasks)
        set_doc_info_para_task_created_flag(uid, task_id)
        return len(tasks)

    def shutdown(self):
        """主动关闭线程池"""
        self.executor.shutdown(wait=True)
        logger.info("文档生成器线程池已关闭")

    def __del__(self):
        """清理线程池"""
        try:
            self.executor.shutdown(wait=False)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
