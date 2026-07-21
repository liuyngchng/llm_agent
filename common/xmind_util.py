#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
XMind 文件解析工具类
XMind 文件本质上是 ZIP 压缩包，包含 content.xml 来描述思维导图的层级结构。
本模块负责将 XMind 文件转换为可用于 RAG 检索的文本。
"""

import json
import logging.config
import os
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET
from typing import Optional

from langchain_core.documents import Document

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

# XMind 文件命名空间
NS_MAP = {
    '': 'urn:xmind:xmap:xmlns:content:2.0',
    'fo': 'http://www.w3.org/1999/XSL/Format',
    'svg': 'http://www.w3.org/2000/svg',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'xlink': 'http://www.w3.org/1999/xlink',
}


def _ns(tag: str) -> str:
    """构建带命名空间的标签"""
    return f'{{{NS_MAP[""]}}}{tag}'


def _find_child(element: ET.Element, tag: str) -> Optional[ET.Element]:
    """查找直接子元素（带命名空间）"""
    return element.find(_ns(tag))


def _find_all(element: ET.Element, tag: str) -> list[ET.Element]:
    """查找所有直接子元素（带命名空间）"""
    return element.findall(_ns(tag))


def _get_title(topic: ET.Element) -> str:
    """获取 topic 的标题文本"""
    title_el = _find_child(topic, 'title')
    if title_el is not None and title_el.text:
        return title_el.text.strip()
    return ''


def _get_notes(topic: ET.Element) -> Optional[str]:
    """获取 topic 的备注（notes）"""
    notes_el = _find_child(topic, 'notes')
    if notes_el is not None:
        # notes 内可能包含 html 富文本
        html_el = notes_el.find(f'{{{NS_MAP["xhtml"]}}}p')
        if html_el is None:
            plain_el = _find_child(notes_el, 'plain')
            if plain_el is not None and plain_el.text:
                return plain_el.text.strip()
        else:
            # 递归提取所有文本
            texts = []
            _extract_html_text(notes_el, texts)
            return ' '.join(texts).strip()
    return None


def _extract_html_text(element: ET.Element, texts: list):
    """递归提取 HTML 元素中的文本"""
    if element.text:
        texts.append(element.text.strip())
    for child in element:
        _extract_html_text(child, texts)
        if child.tail:
            texts.append(child.tail.strip())


def _get_labels(topic: ET.Element) -> list[str]:
    """获取 topic 的标签"""
    labels_el = _find_child(topic, 'labels')
    if labels_el is not None:
        return [lab.text.strip() for lab in _find_all(labels_el, 'label') if lab.text]
    return []


def _get_markers(topic: ET.Element) -> list[str]:
    """获取 topic 的标记（如优先级、完成状态等）"""
    markers_el = _find_child(topic, 'markers')
    if markers_el is not None:
        marker_list = []
        for marker in _find_all(markers_el, 'marker'):
            marker_id = marker.get('marker-id', '')
            if marker_id:
                marker_list.append(marker_id)
        return marker_list
    return []


def _get_children(topics_element: Optional[ET.Element]) -> list[ET.Element]:
    """获取 children > topics 下的所有 topic 元素"""
    if topics_element is None:
        return []
    topics_container = _find_child(topics_element, 'topics')
    if topics_container is not None:
        return _find_all(topics_container, 'topic')
    # 兼容旧版本: children 直接包含 topic
    direct_topics = _find_all(topics_element, 'topic')
    if direct_topics:
        return direct_topics
    return []


def parse_xmind_to_text(file_path: str) -> tuple[str, list[dict]]:
    """
    解析 XMind 文件，返回:
        (full_text, branches)

    full_text: 整个思维导图的文本表示（包含层级缩进）
    branches: 每条从根到叶子的路径，适合作为 RAG 检索的独立片段
        每条 branch 包含: path (层级路径), full_path (完整描述),
        labels, markers, notes
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"XMind 文件不存在: {abs_path}")

    with zipfile.ZipFile(abs_path, 'r') as zf:
        # 检查是否有 content.xml
        if 'content.xml' not in zf.namelist():
            raise ValueError(f"XMind 文件格式异常，缺少 content.xml: {abs_path}")

        content_xml = zf.read('content.xml')

    # 解析 XML
    root = ET.fromstring(content_xml)

    # 查找所有 sheet
    sheets = root.findall(_ns('sheet'))
    if not sheets:
        raise ValueError(f"XMind 文件中未找到 sheet: {abs_path}")

    all_branches = []
    all_text_parts = []

    for sheet_idx, sheet in enumerate(sheets):
        sheet_title_el = _find_child(sheet, 'title')
        sheet_name = sheet_title_el.text.strip() if sheet_title_el is not None and sheet_title_el.text else f'Sheet{sheet_idx + 1}'

        root_topic = _find_child(sheet, 'topic')
        if root_topic is None:
            continue

        if len(sheets) > 1:
            all_text_parts.append(f'# {sheet_name}')

        # 递归遍历
        branches, tree_text = _traverse_topic(root_topic, depth=0, path_prefix='')
        all_branches.extend(branches)
        all_text_parts.append(tree_text)

    full_text = '\n'.join(all_text_parts)
    return full_text, all_branches


def _traverse_topic(topic: ET.Element, depth: int, path_prefix: str) -> tuple[list[dict], str]:
    """
    递归遍历 topic 节点，返回:
        (branches, tree_text)

    branches: 从当前节点到每个叶子的路径列表
    tree_text: 当前节点及其子树的缩进文本表示
    """
    title = _get_title(topic)
    labels = _get_labels(topic)
    markers = _get_markers(topic)
    notes = _get_notes(topic)

    # 构建当前路径
    if path_prefix:
        current_path = f'{path_prefix} > {title}'
    else:
        current_path = title

    # 构建当前节点的标记信息
    suffix_parts = []
    if labels:
        suffix_parts.append(f'[标签: {", ".join(labels)}]')
    if markers:
        suffix_parts.append(f'[标记: {", ".join(markers)}]')

    suffix = ' ' + ' '.join(suffix_parts) if suffix_parts else ''

    # 缩进文本
    indent = '  ' * depth
    line = f'{indent}- {title}{suffix}'
    if notes:
        line += f'\n{indent}  备注: {notes}'

    children_el = _find_child(topic, 'children')
    child_topics = _get_children(children_el)

    if not child_topics:
        # 叶子节点
        branch = {
            'path': current_path,
            'title': title,
            'labels': labels,
            'markers': markers,
            'notes': notes,
        }
        # 叶子节点的完整文本包括备注
        leaf_text_parts = [current_path + suffix]
        if notes:
            leaf_text_parts.append(f'备注: {notes}')
        branch['full_text'] = '\n'.join(leaf_text_parts)
        return [branch], line

    # 非叶子节点: 递归处理子节点
    all_branches = []
    child_lines = [line]

    for child in child_topics:
        child_branches, child_text = _traverse_topic(child, depth + 1, current_path)
        all_branches.extend(child_branches)
        child_lines.append(child_text)

    # 非叶子节点也生成一个描述分支（包含直接子节点概述），便于检索
    child_titles = [_get_title(c) for c in child_topics if _get_title(c)]
    overview = f'{current_path}{suffix}'
    if child_titles:
        overview += f'（包含: {", ".join(child_titles[:10])}）'
    branch = {
        'path': current_path,
        'title': title,
        'labels': labels,
        'markers': markers,
        'notes': notes,
        'full_text': overview + (f'\n备注: {notes}' if notes else ''),
    }
    all_branches.insert(0, branch)

    return all_branches, '\n'.join(child_lines)


def parse_xmind_to_documents(file_path: str) -> list[Document]:
    """
    将 XMind 文件解析为 LangChain Document 列表。

    每个 Document 包含:
    - page_content: 思维导图的一条分支路径的文本描述（适合 RAG 检索）
    - metadata: 包含源文件、路径、标签、标记等信息
    """
    abs_path = os.path.abspath(file_path)
    full_text, branches = parse_xmind_to_text(abs_path)

    if not branches:
        logger.warning(f"XMind 文件中未提取到有效内容: {abs_path}")
        return []

    documents = []
    for i, branch in enumerate(branches):
        doc = Document(
            page_content=branch.get('full_text', branch.get('path', '')),
            metadata={
                'source': abs_path,
                'file_type': 'xmind',
                'branch_index': i,
                'path': branch.get('path', ''),
                'title': branch.get('title', ''),
                'labels': json.dumps(branch.get('labels', []), ensure_ascii=False),
                'markers': json.dumps(branch.get('markers', []), ensure_ascii=False),
            }
        )
        documents.append(doc)

    return documents


class XMindLoader:
    """
    XMind 文档加载器，兼容 LangChain Document Loader 接口。
    用法:
        loader = XMindLoader(file_path)
        documents = loader.load()
    """

    def __init__(self, file_path: str, encoding: str = 'utf-8'):
        self.file_path = file_path
        self.encoding = encoding

    def load(self) -> list[Document]:
        """加载 XMind 文件并返回 Document 列表"""
        return parse_xmind_to_documents(self.file_path)


# ======== 测试代码 ========
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('用法: python xmind_util.py <xmind_file_path>')
        sys.exit(1)

    test_file = sys.argv[1]
    print(f'=== 解析 XMind 文件: {test_file} ===\n')

    # 测试全文本输出
    full_text, branches = parse_xmind_to_text(test_file)
    print('--- 层级文本 ---')
    print(full_text)
    print(f'\n--- 共提取 {len(branches)} 条分支路径 ---\n')

    for i, branch in enumerate(branches):
        print(f'Branch {i}: {branch.get("full_text", branch.get("path", ""))[:120]}...')

    # 测试 Document 输出
    print('\n--- LangChain Documents ---')
    docs = parse_xmind_to_documents(test_file)
    for doc in docs:
        print(f'  [{doc.metadata.get("branch_index")}] {doc.metadata.get("path")}')
        print(f'     content: {doc.page_content[:100]}...')
