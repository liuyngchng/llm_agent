#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import logging.config
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import threading

from docx import Document
from docx.shared import RGBColor, Cm

import docx_meta_util
from agt_util import gen_txt
from docx_util import get_elapsed_time, get_reference_from_vdb, AI_GEN_TAG, is_3rd_heading, is_prompt_para
from sys_init import init_yml_cfg

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class DocxGenerator:
    """
    DOCX文档生成器，使用多线程并行生成文本内容
    """

    def __init__(self, max_workers=3, timeout=300):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.timeout = timeout
        self.lock = threading.Lock()
        self.start_time = None

    def fill_doc_with_prompt_parallel(self, task_id: int, doc_ctx: str, target_doc: str,
                                      target_doc_catalogue: str, vdb_dir: str,
                                      sys_cfg: dict, output_file_name: str) -> str:
        """
        并行填充word文档（改进错误处理和统计）
        """
        start_time = time.time() * 1000
        doc = Document(target_doc)

        try:
            logger.info(f"开始处理文档 {target_doc}")
            tasks = DocxGenerator._collect_generation_tasks(doc, doc_ctx, target_doc_catalogue,
                                                   vdb_dir, sys_cfg)

            if not tasks:
                final_info = "未检测到需要生成的文本段落"
                logger.info(f"{final_info}, {target_doc}")
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
                doc.save(output_file_name)
                return final_info

            initial_info = f"开始并行处理 {len(tasks)} 个段落，使用 {self.executor._max_workers} 个线程"
            logger.info(initial_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, initial_info, 0)
            results = self._execute_parallel_generation(tasks, task_id, start_time, len(tasks))
            self._insert_results_to_doc(doc, results)

            # 保存文档
            doc.save(output_file_name)
            logger.info(f"保存文档完成，{output_file_name}，耗时 {get_elapsed_time(start_time)}")
            docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)

            # 计算详细统计信息
            success_count = len([r for r in results.values() if r.get('success')])
            failed_count = len(tasks) - success_count
            total_time = get_elapsed_time(start_time)

            final_info = (f"任务完成！共处理 {len(tasks)} 个段落，"
                          f"成功生成 {success_count} 段文本，失败 {failed_count} 段，{total_time}")

            if failed_count > 0:
                final_info += f"，失败段落可在日志中查看详情"

            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            logger.info(f"{final_info}，输出文件: {output_file_name}")
            return final_info

        except Exception as e:
            error_info = f"文档生成过程出现异常: {str(e)}"
            logger.error(error_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            try:
                doc.save(output_file_name)
            except Exception:
                pass
            return error_info

    @staticmethod
    def _collect_generation_tasks(doc: Document, doc_ctx: str,
                                  target_doc_catalogue: str, vdb_dir: str,
                                  sys_cfg: dict) -> List[Dict[str, Any]]:
        """
        收集所有需要生成文本的任务信息
        """
        tasks = []
        current_heading = []

        for para in doc.paragraphs:
            try:
                is_prompt = is_prompt_para(para, current_heading, sys_cfg)
            except Exception as e:
                logger.error(f"判断写作要求段落失败: {e}，跳过该段落")
                continue

            if not is_prompt:
                continue
            task = {
                'unique_key': f"para_{len(tasks)}",
                'write_context': doc_ctx,
                'paragraph_prompt': para.text,
                'catalogue': target_doc_catalogue,
                'current_sub_title': current_heading[0] if current_heading else "",
                'cfg': sys_cfg,
                'vdb_dir': vdb_dir,
                'original_para': para,
                'current_heading': current_heading.copy()
            }
            tasks.append(task)

        return tasks

    def _execute_parallel_generation(self, tasks: List[Dict[str, Any]],
                                     task_id: int, start_time: float,
                                     total_tasks: int) -> Dict[str, Dict]:
        """
        并行执行文本生成任务（优化进度更新频率）
        """
        results = {}
        completed = 0
        future_to_key = {}
        last_update_time = time.time()
        update_interval = 2  # 每2秒更新一次进度，避免过于频繁

        # 提交所有任务到线程池
        for task in tasks:
            future = self.executor.submit(DocxGenerator._generate_single_paragraph, task)
            future_to_key[future] = task['unique_key']

        # 监控任务进度并收集结果
        for future in as_completed(future_to_key, timeout=self.timeout):
            key = future_to_key[future]
            try:
                result = future.result()
                results[key] = result
            except Exception as e:
                logger.error(f"段落生成失败 {key}: {str(e)}")
                results[key] = {
                    'success': False,
                    'error': str(e),
                    'original_task': tasks[int(key.split('_')[1])]
                }

            # 更新进度（控制更新频率）
            completed += 1
            current_time = time.time()

            # 只有超过更新间隔或完成时才更新
            if current_time - last_update_time >= update_interval or completed == total_tasks:
                percent = int(completed / total_tasks * 100)
                elapsed_time = get_elapsed_time(start_time)

                # 计算预估剩余时间
                if completed > 0:
                    elapsed_seconds = (time.time() * 1000 - start_time) / 1000
                    avg_time_per_task = elapsed_seconds / completed
                    remaining_tasks = total_tasks - completed
                    estimated_remaining = avg_time_per_task * remaining_tasks

                    if estimated_remaining < 60:
                        remaining_str = f"约{int(estimated_remaining)}秒"
                    else:
                        remaining_str = f"约{int(estimated_remaining / 60)}分{int(estimated_remaining % 60)}秒"

                    progress_info = f"正在生成文本 {completed}/{total_tasks}，{elapsed_time}，剩余{remaining_str}"
                else:
                    progress_info = f"正在生成文本 {completed}/{total_tasks}，{elapsed_time}"

                docx_meta_util.update_docx_file_process_info_by_task_id(
                    task_id, progress_info, percent)
                last_update_time = current_time

        return results

    @staticmethod
    def _generate_single_paragraph(task: Dict[str, Any]) -> Dict:
        """
        单个段落的生成任务（移除 signal 超时处理）
        """
        try:
            # 获取参考文本
            references = get_reference_from_vdb(
                task['paragraph_prompt'],
                task['vdb_dir'],
                task['cfg']['api']
            )

            # 生成文本
            llm_txt = gen_txt(
                write_context=task['write_context'],
                references=references,
                paragraph_prompt=task['paragraph_prompt'],
                catalogue=task['catalogue'],
                current_sub_title=task['current_sub_title'],
                cfg=task['cfg']
            )

            return {
                'success': True,
                'generated_text': f"{AI_GEN_TAG}{llm_txt}",
                'original_para': task['original_para'],
                'current_heading': task['current_heading']
            }

        except Exception as e:
            logger.error(f"生成段落失败: {str(e)}")
            raise

    @staticmethod
    def _insert_results_to_doc(doc: Document, results: Dict[str, Dict]):
        """
        将生成的结果插入到文档中
        """
        # 按原始段落顺序处理结果
        sorted_keys = sorted(results.keys(), key=lambda x: int(x.split('_')[1]))

        for key in sorted_keys:
            result = results[key]
            if not result.get('success'):
                continue

            original_para = result['original_para']
            generated_text = result['generated_text']

            # 创建新段落并插入
            new_para = doc.add_paragraph()
            new_para.paragraph_format.first_line_indent = Cm(1)
            red_run = new_para.add_run(generated_text)
            red_run.font.color.rgb = RGBColor(0, 0, 0)

            # 插入到原始段落后面
            original_para._p.addnext(new_para._p)

    def fill_doc_without_prompt_parallel(self, task_id: int, doc_ctx: str, target_doc: str,
                                         target_doc_catalogue: str, vdb_dir: str,
                                         sys_cfg: dict, output_file_name: str) -> str:
        """
        并行填充word文档（只有三级目录的版本）
        """
        start_time = time.time() * 1000
        doc = Document(target_doc)

        # 收集三级标题任务
        tasks = []
        for para in doc.paragraphs:
            if not is_3rd_heading(para):
                continue

            task = {
                'unique_key': f"heading_{len(tasks)}",
                'write_context': doc_ctx,
                'paragraph_prompt': para.text,
                'catalogue': target_doc_catalogue,
                'current_sub_title': para.text,
                'cfg': sys_cfg,
                'vdb_dir': vdb_dir,
                'original_para': para
            }
            tasks.append(task)

        if not tasks:
            final_info = "未找到三级标题"
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            doc.save(output_file_name)
            return final_info

        # 并行执行并插入结果
        results = self._execute_parallel_generation(tasks, task_id, start_time, len(tasks))
        self._insert_results_to_doc(doc, results)

        # 保存文档
        doc.save(output_file_name)
        docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)

        success_count = len([r for r in results.values() if r.get('success')])
        final_info = f"任务完成，共处理 {len(tasks)} 个标题，成功生成 {success_count} 段文本，{get_elapsed_time(start_time)}"
        docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
        logger.info(f"{final_info}，输出文件: {output_file_name}")
        return final_info

    def modify_para_with_comment_prompt_in_parallel(self, task_id: int, target_doc: str,
                                                    doc_ctx: str, comments_dict: dict,
                                                    vdb_dir: str, cfg: dict,
                                                    output_file_name: str) -> str:
        """
        并行处理带有批注的文档
        :param task_id: 执行任务的ID
        :param target_doc: 需要修改的文档路径
        :param doc_ctx: 文档写作的背景信息
        :param comments_dict: 段落ID和段落批注的对应关系字典
        :param vdb_dir: 向量数据库的目录
        :param cfg: 系统配置，用于使用大模型的能力
        :param output_file_name: 输出文档的文件名
        """
        if not os.path.exists(target_doc):
            error_info = f"输入文件不存在: {target_doc}"
            logger.error(error_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            return error_info

        if not comments_dict:
            warning_info = "文件批注信息为空"
            logger.warning(warning_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, warning_info, 100)
            return warning_info

        start_time = time.time() * 1000
        doc = Document(target_doc)

        try:
            logger.info(f"开始处理带批注的文档 {target_doc}，共 {len(comments_dict)} 个批注")

            # 收集批注处理任务
            tasks = DocxGenerator._collect_comment_tasks(doc, doc_ctx, comments_dict, vdb_dir, cfg)

            if not tasks:
                final_info = "未找到有效的批注处理任务"
                logger.info(final_info)
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
                doc.save(output_file_name)
                return final_info

            initial_info = f"开始并行处理 {len(tasks)} 个批注段落，使用 {self.executor._max_workers} 个线程"
            logger.info(initial_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, initial_info, 0)

            # 执行并行生成
            results = self._execute_parallel_generation(tasks, task_id, start_time, len(tasks))
            # 更新文档内容
            DocxGenerator._update_doc_with_comments(results)
            # 保存文档
            doc.save(output_file_name)
            logger.info(f"保存批注处理文档完成: {output_file_name}")
            docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)
            # 统计结果
            success_count = len([r for r in results.values() if r.get('success')])
            failed_count = len(tasks) - success_count
            total_time = get_elapsed_time(start_time)

            final_info = (f"批注处理完成！共处理 {len(tasks)} 个批注段落，"
                          f"成功生成 {success_count} 段文本，失败 {failed_count} 段，{total_time}")
            if failed_count > 0:
                final_info += "，失败段落可在日志中查看详情"
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            logger.info(f"{final_info}，输出文件: {output_file_name}")
            return final_info
        except Exception as e:
            error_info = f"批注文档处理过程出现异常: {str(e)}"
            logger.error(error_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            try:
                doc.save(output_file_name)
            except Exception:
                pass
            return error_info

    @staticmethod
    def _collect_comment_tasks(doc: Document, doc_ctx: str,
                               comments_dict: dict, vdb_dir: str,
                               cfg: dict) -> List[Dict[str, Any]]:
        """
        收集批注处理任务
        """
        tasks = []
        current_heading = []

        for para_idx, para in enumerate(doc.paragraphs):
            # 更新当前标题
            try:
                from docx_util import refresh_current_heading
                refresh_current_heading(para, current_heading)
            except Exception as e:
                logger.warning(f"更新标题失败: {e}，继续处理")

            # 检查当前段落是否有批注
            if para_idx not in comments_dict:
                continue

            comment_text = comments_dict[para_idx]
            if not comment_text or not comment_text.strip():
                continue

            # 获取目录
            try:
                from docx_cmt_util import get_catalogue
                catalogue = get_catalogue(doc.part.blob)
            except:
                catalogue = ""

            task = {
                'unique_key': f"comment_{para_idx}",
                'write_context': doc_ctx,
                'paragraph_prompt': comment_text,
                'catalogue': catalogue,
                'current_sub_title': current_heading[0] if current_heading else "",
                'cfg': cfg,
                'vdb_dir': vdb_dir,
                'original_para': para,
                'para_index': para_idx,
                'comment_text': comment_text
            }
            tasks.append(task)

        return tasks

    @staticmethod
    def _update_doc_with_comments(results: Dict[str, Dict]):
        """
        用生成的结果更新文档中的批注段落
        """
        # 按段落索引排序处理
        sorted_keys = sorted(results.keys(), key=lambda x: int(x.split('_')[1]))

        for key in sorted_keys:
            result = results[key]
            if not result.get('success'):
                continue

            original_para = result['original_para']
            generated_text = result['generated_text']

            # 清空原段落内容并添加生成文本
            original_para.clear()
            original_para.paragraph_format.first_line_indent = Cm(1)
            run = original_para.add_run(generated_text)
            run.font.color.rgb = RGBColor(0, 0, 0)

    def fill_doc_without_prompt_in_parallel(self, task_id: int, doc_ctx: str, target_doc: str,
                                            target_doc_catalogue: str, vdb_dir: str,
                                            sys_cfg: dict, output_file_name: str) -> str:
        """
        并行填充word文档（只有三级目录，无需段落提示词）
        :param task_id: 执行任务的ID
        :param doc_ctx: 文档写作背景信息
        :param target_doc: 需要写的文档三级目录
        :param vdb_dir: 向量数据库的目录
        :param sys_cfg: 系统配置信息
        :param target_doc_catalogue: 需要写的文档的三级目录文本信息
        :param output_file_name: 输出文档的文件名
        """
        start_time = time.time() * 1000
        doc = Document(target_doc)

        try:
            logger.info(f"开始处理无提示词文档 {target_doc}")
            # 收集三级标题任务
            tasks = []
            for para in doc.paragraphs:
                if not is_3rd_heading(para):
                    continue

                task = {
                    'unique_key': f"heading_{len(tasks)}",
                    'write_context': doc_ctx,
                    'paragraph_prompt': "",  # 无具体写作要求
                    'catalogue': target_doc_catalogue,
                    'current_sub_title': para.text,
                    'cfg': sys_cfg,
                    'vdb_dir': vdb_dir,
                    'original_para': para
                }
                tasks.append(task)

            if not tasks:
                final_info = f"未找到三级标题，输出文档： {output_file_name}"
                logger.info(final_info)
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
                doc.save(output_file_name)
                return final_info

            initial_info = f"开始并行处理 {len(tasks)} 个三级标题，使用 {self.executor._max_workers} 个线程"
            logger.info(initial_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, initial_info, 0)

            # 执行并行生成
            results = self._execute_parallel_generation(tasks, task_id, start_time, len(tasks))

            # 插入生成结果到文档
            DocxGenerator._insert_results_to_doc(doc, results)

            # 保存文档
            doc.save(output_file_name)
            logger.info(f"保存无提示词文档完成: {output_file_name}")
            docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)

            # 统计结果
            success_count = len([r for r in results.values() if r.get('success')])
            failed_count = len(tasks) - success_count
            total_time = get_elapsed_time(start_time)

            final_info = (f"无提示词文档处理完成！共处理 {len(tasks)} 个三级标题，"
                          f"成功生成 {success_count} 段文本，失败 {failed_count} 段，{total_time}")

            if failed_count > 0:
                final_info += "，失败标题可在日志中查看详情"

            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            logger.info(f"{final_info}，输出文件: {output_file_name}")
            return final_info

        except Exception as e:
            error_info = f"无提示词文档生成过程出现异常: {str(e)}"
            logger.error(error_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            try:
                doc.save(output_file_name)
            except Exception:
                pass
            return error_info

    def shutdown(self):
        """主动关闭线程池"""
        self.executor.shutdown(wait=True)
        logger.info("文档生成器线程池已关闭")

    def __del__(self):
        """清理线程池"""
        try:
            self.executor.shutdown(wait=False)
        except:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


if __name__ == '__main__':
    catalogue_text = "1.1 概述\n1.2 背景\n1.3 需求描述\n1.4 需求分析\n1.5 需求规格\n1.6 需求计划\n1.7 需求评估"
    my_template_file = "/home/rd/doc/文档生成/template.docx"
    config = init_yml_cfg()

    with DocxGenerator(max_workers=3) as generator:
        result = generator.fill_doc_with_prompt_parallel(
            task_id=12345,
            doc_ctx="可行性研究报告",
            target_doc=my_template_file,
            target_doc_catalogue=catalogue_text,
            vdb_dir="./vdb",
            sys_cfg=config,
            output_file_name="output.docx"
        )
        logger.info(result)