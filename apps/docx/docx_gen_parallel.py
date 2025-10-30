#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
生成并行任务，处理 docx 文档中的文本填充、文本修改
"""
import json
import logging.config
import multiprocessing
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import threading
import psutil
from xml.etree import ElementTree as ET

from apps.docx import docx_meta_util
from docx import Document
from docx.shared import RGBColor, Cm

from apps.docx.docx_file_cmt_util import refresh_current_heading_xml
from common import cfg_util
from apps.docx.txt_gen_util import gen_txt
from apps.docx.docx_file_txt_util import get_elapsed_time, get_reference_from_vdb, \
    is_3rd_heading, is_txt_para, refresh_current_heading
from apps.docx.mermaid_render import MermaidRenderer

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


class DocxGenerator:
    """
    DOCX文档生成器，使用多线程并行生成文本内容
    任务一共分为3种：
        (1) 只含有目录的 docx 文件；
        (2) 含有目录和段落写作要求文本的 docx 文件;
        (3) 含有word 批注内容的 docx 文件；
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
            max_workers = self._calculate_dynamic_workers()

        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.timeout = timeout
        self.lock = threading.Lock()
        self.start_time = None

        logger.info(f"初始化文档生成器 - 工作线程: {self.max_workers}, "
                    f"CPU核心: {multiprocessing.cpu_count()}, "
                    f"内存: {self._get_memory_info()}")

    def _calculate_dynamic_workers(self) -> int:
        """
        基于系统资源动态计算工作线程数
        考虑CPU核心数、内存使用情况等
        """
        try:
            cpu_count = multiprocessing.cpu_count()
            memory_info = DocxGenerator._get_memory_usage()
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
    def _get_memory_usage() -> dict:
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
    def _get_memory_info() -> str:
        """获取内存信息字符串"""
        try:
            memory = DocxGenerator._get_memory_usage()
            return f"{memory['available_percent']:.1f}%可用"
        except:
            return "未知"

    def fill_doc_with_prompt_in_parallel(self, task_id: int, doc_ctx: str, target_doc: str,
                                         target_doc_catalogue: str, vdb_dir: str,
                                         sys_cfg: dict, output_file_name: str) -> str:
        """
        处理有目录，并且有段落写作要求的 Word 文档
        """
        start_time = time.time() * 1000
        doc = Document(target_doc)
        try:
            logger.info(f"{task_id}, 开始处理文档 {target_doc}")
            tasks = DocxGenerator._collect_doc_with_prompt_gen_tasks(task_id, target_doc, doc_ctx, target_doc_catalogue,
                                                                     vdb_dir, sys_cfg)
            if not tasks:
                final_info = f"未检测到需要生成的文本段落"
                logger.info(f"{task_id}, {final_info}, {target_doc}")
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
                doc.save(output_file_name)
                return final_info

            initial_info = f"需处理 {len(tasks)} 个段落，启动 {self.executor._max_workers} 个任务"
            logger.info(f"{task_id}, {initial_info}")
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, initial_info, 0)
            doc_gen_results = self._exec_tasks(tasks, task_id, start_time, len(tasks), include_mermaid=True)
            self._insert_gen_para_to_doc(target_doc, doc_gen_results)

            # 保存文档
            doc.save(output_file_name)
            logger.info(f"{task_id}, 保存文档完成，{output_file_name}，耗时 {get_elapsed_time(start_time)}")
            docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)
            # 计算详细统计信息
            success_count = len([r for r in doc_gen_results.values() if r.get('success')])
            failed_count = len(tasks) - success_count
            # 处理Mermaid图表
            img_count = 0
            try:
                logger.info(f"{task_id}, 开始处理文档中的Mermaid图表")
                current_info = docx_meta_util.get_docx_info_by_task_id(task_id)
                docx_meta_util.update_docx_file_process_info_by_task_id(
                    task_id,
                    f"{current_info[0]['process_info']}, 开始处理文档配图",
                    95
                )
                mermaid_process_info = DocxGenerator._process_mermaid_in_document(
                    task_id,
                    output_file_name,
                    sys_cfg['api']['mermaid_api_uri'],
                    doc_gen_results
                )
                img_count = mermaid_process_info.get('img_count', 0)
                docx_meta_util.update_img_count_by_task_id(task_id, img_count)
                if not mermaid_process_info['success']:
                    failed_count += 1
                logger.info(f"{task_id}, Mermaid图表处理完成, {json.dumps(mermaid_process_info, ensure_ascii=False)}")
            except Exception as e:
                failed_count += 1
                logger.error(f"{task_id}, Mermaid图表处理失败: {str(e)}")
            total_time = get_elapsed_time(start_time)
            final_info = (f"文档处理完成，共执行 {len(tasks)} 个文本生成任务，"
                          f"成功生成 {success_count} 段文本和 {img_count} 张配图，失败任务 {failed_count} 个，{total_time}")

            if failed_count > 0:
                final_info += f"，失败任务的原因可在日志中查看具体的失败原因"
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            logger.info(f"{task_id}, {final_info}，输出文件: {output_file_name}")
            return final_info

        except Exception as e:
            error_info = f"文档生成过程出现异常: {str(e)}"
            logger.error(f"{task_id}, {error_info}")
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            try:
                doc.save(output_file_name)
            except Exception:
                pass
            return error_info

    @staticmethod
    def _collect_doc_with_prompt_gen_tasks(task_id: int, target_doc: str, doc_ctx: str,
                                           target_doc_catalogue: str, vdb_dir: str,
                                           sys_cfg: dict) -> List[Dict[str, Any]]:
        """
        收集含有目录和段落写作要求的docx文档的文本生成任务
        """
        logger.info(f"{task_id}, start_collect_task")
        tasks = []
        current_heading = []
        doc = Document(target_doc)
        para_count = len(doc.paragraphs)
        for index, para in enumerate(doc.paragraphs):
            refresh_current_heading(para, current_heading)
            check_if_is_txt_para = is_txt_para(para, current_heading, sys_cfg)
            if not check_if_is_txt_para:
                logger.info(f"{task_id}, 跳过非描述性的文本段落 {para.text}")
                continue
            task = {
                'task_id': task_id,
                'unique_key': f"para_{len(tasks)}",
                'write_context': doc_ctx,
                'paragraph_prompt': para.text,
                'user_comment': "",
                'catalogue': target_doc_catalogue,
                'current_sub_title': current_heading[0] if current_heading else "",
                'current_heading': current_heading.copy(),
                'sys_cfg': sys_cfg,
                'vdb_dir': vdb_dir,
                'original_para': para,
            }
            tasks.append(task)
            process_info = f"正在处理第 {index}/{para_count}  段文本， 已创建 {len(tasks)} 个处理任务"
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, process_info)
        logger.info(f"_collect_task, {len(tasks)}")
        return tasks

    def _exec_tasks(self, tasks: List[Dict[str, Any]],
                    task_id: int, start_time: float,
                    total_tasks: int, include_mermaid: bool = False) -> Dict[str, Dict]:
        """
        并行执行文本生成任务
        :param tasks: 任务列表
        :param task_id: 任务ID
        :param start_time: 开始时间
        :param total_tasks: 总任务数
        :param include_mermaid: 是否包含Mermaid处理任务
        :return 执行完任务的结果
        """
        results = {}
        completed = 0
        future_to_key = {}
        last_update_time = time.time()
        update_interval = 2  # 每2秒更新一次进度，避免过于频繁

        # 如果包含Mermaid任务，总任务数需要加1
        actual_total_tasks = total_tasks + 1 if include_mermaid else total_tasks

        # 提交所有任务到线程池
        for task in tasks:
            future = self.executor.submit(DocxGenerator._gen_single_doc_paragraph, task)
            future_to_key[future] = task['unique_key']

        # 监控任务进度并收集结果
        for future in as_completed(future_to_key, timeout=self.timeout):
            key = future_to_key[future]
            try:
                result = future.result()
                results[key] = result
            except Exception as e:
                logger.error(f"{task_id}, 段落生成失败 {key}: {str(e)}, {task_id}")
                results[key] = {
                    'success': False,
                    'error': str(e),
                    'original_task': tasks[int(key.split('_')[1])]
                }

            completed += 1
            current_time = time.time()
            if current_time - last_update_time >= update_interval or completed == total_tasks:
                # 计算进度百分比时考虑Mermaid任务
                percent = int(completed / actual_total_tasks * 100)
                elapsed_time = get_elapsed_time(start_time)
                # 计算预估剩余时间
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

                docx_meta_util.update_docx_file_process_info_by_task_id(
                    task_id, progress_info, percent)
                last_update_time = current_time

        return results

    @staticmethod
    def _gen_single_doc_paragraph(task: Dict[str, Any]) -> Dict:
        """
        单个段落文本的生成任务（支持Mermaid图表）
        """
        try:
            # 获取参考文本
            references = get_reference_from_vdb(
                task['paragraph_prompt'],
                task['vdb_dir'],
                task['sys_cfg']['api']
            )
            logger.debug(f"gen_txt_user_comment, {task['user_comment']}")

            # 生成文本
            if not task['task_id']:
                raise RuntimeError('task_id_null_exception')

            docx_file_info = docx_meta_util.get_docx_info_by_task_id(task['task_id'])
            uid = docx_file_info[0]['uid']
            llm_txt = gen_txt(
                uid=uid,
                write_context=task['write_context'],
                references=references,
                paragraph_prompt=task['paragraph_prompt'],
                catalogue=task['catalogue'],
                current_sub_title=task['current_sub_title'],
                user_comment=task['user_comment'],
                cfg=task['sys_cfg']
            )
            word_count = len(llm_txt)

            # 根据任务类型返回不同的结果结构
            result = {
                'success': True,
                'generated_text': f"{cfg_util.AI_GEN_TAG}{llm_txt}",
                'current_heading': task['current_heading'],
                'contains_mermaid': '<mermaid>' in llm_txt,
                'word_count': word_count,
            }
            if 'original_para_xml' in task:
                result['para_index'] = task['para_index']
                result['namespaces'] = task['namespaces']
            else:
                result['original_para'] = task['original_para']
            return result

        except Exception as e:
            heading_info = task['current_heading']
            logger.exception(f"生成段落失败: {str(e)}, single_task_args, {heading_info}")
            raise

    @staticmethod
    def _process_mermaid_in_document(task_id:int, doc_path: str, mermaid_api_uri: str, results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        处理文档中的Mermaid图表
        :return: 处理结果信息
        """
        try:
            # 检查是否有包含Mermaid的内容
            has_mermaid = any(result.get('contains_mermaid') for result in results.values() if result.get('success'))
            mermaid_count = sum(1 for result in results.values() if result.get('success') and result.get('contains_mermaid'))
            if has_mermaid:
                logger.info(f"{task_id}, 检测到文档包含Mermaid图表 {mermaid_count}，开始处理: {doc_path}")
                mermaid_instance = MermaidRenderer(kroki_url=mermaid_api_uri)
                img_count = mermaid_instance.batch_process_mermaid_in_docx(task_id, doc_path)
                logger.info(f"{task_id}, 文档包含Mermaid图表处理完成: {doc_path}")
                return {
                    'success': True,
                    'mermaid_count': mermaid_count,
                    'has_mermaid': True,
                    'img_count': img_count,
                }
            else:
                logger.info(f"{task_id}, 文档未包含Mermaid图表，跳过处理: {doc_path}")
                return {
                    'success': True,
                    'mermaid_count': 0,
                    'has_mermaid': False,
                    'img_count':0,
                }
        except Exception as e:
            logger.error(f"{task_id}, 处理Mermaid图表时发生异常: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'img_count': 0,
            }

    @staticmethod
    def _insert_gen_para_to_doc(target_doc: str, results: Dict[str, Dict]):
        """
        将生成的结果插入到文档中
        :param target_doc: 需要处理的目标文档的路径
        """
        doc = Document(target_doc)
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

    def modify_para_with_comment_prompt_in_parallel(self, task_id: int, target_doc: str, catalogue: str,
                                                    doc_ctx: str, comments_dict: dict,
                                                    vdb_dir: str, cfg: dict,
                                                    output_file_name: str) -> str:
        """
        处理添加了Word批注的文档,采用直接修改xml的方式修改 word文档，保证与提取批注的方式一致
        :param task_id: 执行任务的ID
        :param target_doc: 需要修改的文档路径
        :param catalogue: 文档的三级目录
        :param doc_ctx: 文档写作的背景信息
        :param comments_dict: 段落ID和段落批注的对应关系字典
        :param vdb_dir: 向量数据库的目录
        :param cfg: 系统配置，用于使用大模型的能力
        :param output_file_name: 输出文档的文件名
        """
        if not os.path.exists(target_doc):
            error_info = f"输入文件不存在, file_not_exists, {target_doc}"
            logger.error(error_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            return error_info

        if not comments_dict:
            warning_info = "文件里未找到批注信息, no_comment_found"
            logger.warning(f"{warning_info}, {target_doc}")
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, warning_info, 100)
            return warning_info
        logger.debug(f"comments_dict: {comments_dict}")
        start_time = time.time() * 1000

        try:
            info = f"处理带批注的文档 {target_doc}，共找到 {len(comments_dict)} 个批注"
            logger.info(info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, info)
            # 收集批注处理任务（XML方式）
            tasks = DocxGenerator._collect_doc_with_comment_gen_tasks_xml(
                task_id,
                target_doc,
                catalogue,
                doc_ctx,
                comments_dict,
                vdb_dir,
                cfg
            )
            if not tasks:
                final_info = "未找到有效的批注处理任务"
                logger.info(final_info)
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
                import shutil
                shutil.copy2(target_doc, output_file_name)
                return final_info

            initial_info = f"需处理 {len(tasks)} 个批注段落，启动 {self.executor._max_workers} 个任务"
            logger.info(initial_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, initial_info, 0)
            doc_gen_results = self._exec_tasks(tasks, task_id, start_time, len(tasks), include_mermaid=True)

            # 使用 XML 方式更新文档
            success = DocxGenerator._update_doc_with_comments_xml(
                target_doc,
                output_file_name,
                doc_gen_results
            )

            if not success:
                error_info = "XML方式更新文档失败"
                logger.error(error_info)
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
                return error_info

            logger.info(f"保存批注处理文档完成: {output_file_name}")
            docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)

            # 统计结果
            success_count = len([r for r in doc_gen_results.values() if r.get('success')])
            failed_count = len(tasks) - success_count

            # 处理Mermaid图表
            img_count = 0
            try:
                logger.info(f"{task_id}, 开始处理文档中的Mermaid图表")
                current_info = docx_meta_util.get_docx_info_by_task_id(task_id)
                docx_meta_util.update_docx_file_process_info_by_task_id(
                    task_id,
                    f"{current_info[0]['process_info']}, 开始处理文档配图",
                    95
                )
                mermaid_process_info = DocxGenerator._process_mermaid_in_document(
                    task_id,
                    output_file_name,
                    cfg['api']['mermaid_api_uri'],
                    doc_gen_results
                )
                img_count = mermaid_process_info.get('img_count', 0)
                docx_meta_util.update_img_count_by_task_id(task_id, img_count)
                if not mermaid_process_info['success']:
                    failed_count += 1
                logger.info(f"{task_id}, Mermaid图表处理完成")
            except Exception as e:
                failed_count += 1
                logger.error(f"{task_id}, Mermaid图表处理失败: {str(e)}")
            total_time = get_elapsed_time(start_time)
            final_info = (f"批注文档处理完成，共处理 {len(tasks)} 个批注段落，"
                          f"成功生成 {success_count} 段文本和 {img_count} 张配图，失败 {failed_count} 段，{total_time}")
            if failed_count > 0:
                final_info += "，失败段落可在日志中查看详情"
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            logger.info(f"{task_id}, {final_info}，输出文件: {output_file_name}")
            return final_info

        except Exception as e:
            error_info = f"批注文档处理过程出现异常: {str(e)}"
            logger.error(f"{task_id}, {error_info}")
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, error_info, 100)
            return error_info

    @staticmethod
    def _update_doc_with_comments_xml(input_doc: str, output_doc: str, results: Dict[str, Dict]) -> bool:
        """
        使用 XML 方式更新文档中的批注段落
        """
        import shutil
        import tempfile

        temp_dir = None
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()

            # 解压 docx 文件
            with zipfile.ZipFile(input_doc, 'r') as z:
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
            for result in results.values():
                if not result.get('success'):
                    continue

                para_index = result.get('para_index')
                if para_index is None or para_index >= len(paragraphs):
                    logger.warning(f"段落索引 {para_index} 超出范围，跳过")
                    continue

                paragraph = paragraphs[para_index]
                generated_text = result['generated_text'].replace(cfg_util.AI_GEN_TAG, '').strip()

                # 更新段落文本
                if DocxGenerator._update_paragraph_text_xml(paragraph, generated_text, namespaces):
                    modified_count += 1
                    logger.debug(f"已更新段落 {para_index}")

            # 保存修改后的 XML
            tree.write(document_xml_path, encoding='UTF-8', xml_declaration=True)

            # 重新打包为 docx
            with zipfile.ZipFile(output_doc, 'w', zipfile.ZIP_DEFLATED) as z_out:
                for root_dir, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        z_out.write(file_path, arcname)

            logger.info(f"XML方式更新文档完成，共修改 {modified_count} 个段落")
            return True

        except Exception as e:
            logger.error(f"XML方式更新文档时出错: {str(e)}", exc_info=True)
            return False
        finally:
            # 清理临时文件
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    @staticmethod
    def _update_paragraph_text_xml(paragraph, new_text: str, namespaces: dict) -> bool:
        """
        更新 XML 段落中的文本内容
        """
        try:
            # 找到所有的文本元素
            text_elements = paragraph.findall('.//w:t', namespaces)

            if text_elements:
                # 更新第一个文本元素，清空其他文本元素
                text_elements[0].text = new_text
                for text_elem in text_elements[1:]:
                    parent = text_elem.getparent()
                    if parent is not None:
                        # 如果父元素只有这个文本元素，则清空文本；否则删除整个元素
                        if len(parent.findall('*')) == 1:
                            text_elem.text = ""
                        else:
                            parent.remove(text_elem)
                return True
            else:
                # 如果没有文本元素，创建新的 run 和 text
                run = ET.SubElement(paragraph, f'{{{namespaces["w"]}}}r')
                text_elem = ET.SubElement(run, f'{{{namespaces["w"]}}}t')
                text_elem.text = new_text
                return True

        except Exception as e:
            logger.error(f"更新段落文本时出错: {str(e)}")
            return False

    @staticmethod
    def _collect_doc_with_comment_gen_tasks_xml(task_id: int, doc_path: str, catalogue: str, doc_ctx: str,
            comments_dict: dict, vdb_dir: str, cfg: dict) -> List[Dict[str, Any]]:
        """
        收集含有批注的文档的并行处理任务清单（XML版本）
        :param task_id, 任务ID
        :param doc_path, 需要处理的文档的路径
        :param catalogue: 文档目录
        """
        tasks = []
        current_heading = []
        logger.info(f"{task_id}, 开始收集批注任务，批注字典: {comments_dict}")

        try:
            with zipfile.ZipFile(doc_path) as z:
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

                # 解析文档结构
                with z.open('word/document.xml') as f:
                    doc_xml = ET.fromstring(f.read())
                    paragraphs = doc_xml.findall('.//w:p', namespaces)

                    para_count = len(paragraphs)
                    logger.info(f"{task_id}, 共 {para_count} 个 XML 段落")

                    for para_idx, paragraph in enumerate(paragraphs):
                        # 提取段落文本内容
                        para_text = ' '.join(
                            t.text.strip()
                            for t in paragraph.findall('.//w:t', namespaces)
                            if t.text and t.text.strip()
                        )

                        logger.debug(f"{task_id}, para_idx: {para_idx}, para_text: '{para_text}'")

                        # 更新当前标题（需要从 XML 中判断标题样式）
                        refresh_current_heading_xml(paragraph, current_heading, namespaces)

                        # 检查当前段落是否有批注
                        if para_idx not in comments_dict:
                            logger.debug(f"{task_id}, 段落 {para_idx} 无批注，跳过")
                            continue

                        comment_text = comments_dict[para_idx]
                        if not comment_text or not comment_text.strip():
                            logger.debug(f"{task_id}, 跳过无批注内容段落: {para_text}")
                            continue

                        task = {
                            'task_id': task_id,
                            'unique_key': f"comment_{para_idx}",
                            'write_context': doc_ctx,
                            'paragraph_prompt': para_text,
                            'user_comment': comment_text,
                            'catalogue': catalogue,
                            'current_sub_title': current_heading[0] if current_heading else "",
                            'current_heading': current_heading.copy(),
                            'sys_cfg': cfg,
                            'vdb_dir': vdb_dir,
                            'original_para_xml': paragraph,  # 改为保存 XML 元素
                            'para_index': para_idx,
                            'namespaces': namespaces  # 添加命名空间信息
                        }
                        logger.debug(f"{task_id}, 创建批注任务: {task['user_comment']}")
                        tasks.append(task)

                        docx_meta_util.update_docx_file_process_info_by_task_id(
                            task_id,
                            f"正在处理第 {para_idx}/{para_count} 段文本，已创建 {len(tasks)} 个处理任务"
                        )

        except Exception as e:
            logger.error(f"{task_id}, 解析文档 XML 时出错: {str(e)}", exc_info=True)
            return []

        logger.info(f"{task_id}, 完成批注任务收集，共创建 {len(tasks)} 个任务")
        return tasks


    def fill_doc_without_prompt_in_parallel(self, task_id: int, doc_ctx: str, target_doc: str,
                                        target_doc_catalogue: str, vdb_dir: str,
                                        sys_cfg: dict, output_file_name: str) -> str:
        """
        处理只有三级目录，没有任何写作要求段落的word文档
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
                    'task_id': task_id,
                    'unique_key': f"heading_{len(tasks)}",
                    'write_context': doc_ctx,
                    'paragraph_prompt': "",
                    'user_comment': "",
                    'catalogue': target_doc_catalogue,
                    'current_sub_title': para.text,
                    'current_heading': [para.text],
                    'sys_cfg': sys_cfg,
                    'vdb_dir': vdb_dir,
                    'original_para': para,

                }
                tasks.append(task)

            if not tasks:
                final_info = f"未找到三级标题，输出文档： {output_file_name}"
                logger.info(final_info)
                docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
                doc.save(output_file_name)
                return final_info

            initial_info = f"需处理 {len(tasks)} 个三级标题，启动 {self.executor._max_workers} 个任务"
            logger.info(initial_info)
            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, initial_info, 0)
            results = self._exec_tasks(tasks, task_id, start_time, len(tasks), include_mermaid=True)
            DocxGenerator._insert_gen_para_to_doc(doc, results)
            doc.save(output_file_name)
            logger.info(f"保存无提示词文档完成: {output_file_name}")
            docx_meta_util.save_docx_output_file_path_by_task_id(task_id, output_file_name)
            success_count = len([r for r in results.values() if r.get('success')])
            failed_count = len(tasks) - success_count
            # 处理Mermaid图表
            img_count = 0
            try:
                logger.info(f"{task_id}, 开始处理文档中的Mermaid图表")
                current_info = docx_meta_util.get_docx_info_by_task_id(task_id)
                docx_meta_util.update_docx_file_process_info_by_task_id(
                    task_id,
                    f"{current_info[0]['process_info']}, 开始处理文档配图",
                    95
                )
                mermaid_process_info = DocxGenerator._process_mermaid_in_document(
                    task_id,
                    output_file_name,
                    sys_cfg['api']['mermaid_api_uri'],
                    results
                )
                img_count = mermaid_process_info.get('img_count', 0)
                docx_meta_util.update_img_count_by_task_id(task_id, img_count)
                if not mermaid_process_info['success']:
                    failed_count += 1
                logger.info(f"{task_id}, Mermaid图表处理完成, {json.dumps(mermaid_process_info, ensure_ascii=False)}")
            except Exception as e:
                failed_count += 1  # 将Mermaid处理失败计入总失败数
                logger.error(f"{task_id}, Mermaid图表处理失败: {str(e)}")
            total_time = get_elapsed_time(start_time)
            final_info = (f"文档处理完成，共执行 {len(tasks)} 个文本生成任务，"
                          f"成功生成 {success_count} 段文本和 {img_count} 张配图，失败 {failed_count} 段，{total_time}")

            if failed_count > 0:
                final_info += "，失败标题可在日志中查看详情"

            docx_meta_util.update_docx_file_process_info_by_task_id(task_id, final_info, 100)
            logger.info(f"{task_id}, {final_info}，输出文件: {output_file_name}")
            return final_info
        except Exception as e:
            error_info = f"文档生成过程出现异常: {str(e)}"
            logger.error(f"{task_id}, {error_info}")
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
