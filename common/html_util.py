#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import os
import time

import markdown
import logging.config

import requests

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)


def get_html_ctx_from_md(abs_path: str) -> tuple[str, str]:
    """
    使用 markdown 库将 markdown 转换为 html
    读取 markdown 文件的内容，转换为可在 html页面模板进行渲染的内容
    :param abs_path markdown 文件的绝对路径
    return
        toc_content 目录信息
        html_content 文本信息
    """
    toc_content = ""
    html_content = ""
    try:
        if os.path.exists(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            md = markdown.Markdown(
                extensions=[
                    'markdown.extensions.extra',
                    'markdown.extensions.codehilite',
                    'markdown.extensions.tables',
                    'markdown.extensions.toc'
                ]
            )
            html_content = md.convert(markdown_content)
            toc_content = md.toc if hasattr(md, 'toc') else ""
        else:
            html_content = f"<p>读取的文件不存在</p>"
    except Exception as e:
        logger.error(f"Error reading markdown file: {e}")
        html_content = f"<p>读取文件时出错: {str(e)}</p>"
    return html_content, toc_content


def convert_markdown_to_html(uid:int, task_id: int, markdown_content: str, sys_cfg:dict, max_retries: int = 2) -> str:
    """
    通过调用 LLM 将Markdown表格内容转换为美观的HTML表格格式

    Args:
        uid: user id
        task_id: 任务 ID
        markdown_content: Markdown格式的表格内容
        sys_cfg: 系统配置
        max_retries: 最大重试次数
    Returns:
        转换后的HTML表格代码
    """
    for attempt in range(max_retries):
        try:
            template = sys_cfg['prompts']['convert_markdown_to_html_msg']
            if not template:
                raise RuntimeError("prompts_convert_markdown_to_html_msg_err")
            prompt = template.format(markdown_content=markdown_content)
            logger.info(f"{uid}, {task_id}, 开始将Markdown转换为HTML (第{attempt + 1}次尝试)")
            # 调用大语言模型API
            html_result = call_llm_api_for_html_conversion(prompt, sys_cfg)

            if html_result and _is_valid_html_table(html_result):
                logger.info(f"{uid}, {task_id}, 成功将Markdown转换为HTML，长度: {len(html_result)}")
                return html_result
            else:
                logger.warning(f"第{attempt + 1}次转换结果无效，准备重试")
                if attempt == max_retries - 1:
                    logger.error("所有重试尝试均失败，返回原始Markdown内容")
                    return markdown_content
                time.sleep(2)  # 重试前等待

        except Exception as e:
            logger.exception(f"Markdown转HTML失败 (第{attempt + 1}次)")
            if attempt == max_retries - 1:
                logger.error("所有重试尝试均异常，返回原始Markdown内容")
                return markdown_content
            time.sleep(2)

    return markdown_content

def call_llm_api_for_html_conversion(prompt: str, sys_cfg: dict) -> str:
    """
    专门用于HTML转换的大语言模型调用

    Args:
        prompt: 转换提示词
        sys_cfg: 系统配置

    Returns:
        HTML代码
    """
    key = sys_cfg['api']['llm_api_key']
    model = sys_cfg['api']['llm_model_name']
    uri = f"{sys_cfg['api']['llm_api_uri']}/chat/completions"

    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}'
        }

        # 构建消息
        messages = [
            {"role": "system",
             "content": "你是一个专业的文档格式转换专家，擅长将Markdown表格转换为美观的HTML表格。请严格按照要求输出完整的HTML代码。"},
            {"role": "user", "content": prompt}
        ]

        # 构建请求体
        payload = {
            'model': model,
            'messages': messages,
            'temperature': 0.1,  # 低温度确保输出稳定
            'max_tokens': 8192,
            'stream': False
        }

        logger.info(f"开始调用LLM进行HTML转换")

        response = requests.post(
            url=uri,
            headers=headers,
            json=payload,
            timeout=300,  # HTML转换可能需要较长时间
            verify=False,
        )

        logger.info(f"LLM HTML转换响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']

            # 清理返回内容，提取纯HTML代码
            html_content = _extract_html_content(content)

            return html_content
        else:
            error_msg = f"LLM HTML转换API调用失败: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return ""

    except requests.exceptions.Timeout:
        logger.warning("LLM HTML转换API调用超时")
        return ""
    except Exception as e:
        logger.error(f"LLM HTML转换API调用异常: {str(e)}")
        return ""

def _extract_html_content(content: str) -> str:
    """
    从LLM返回内容中提取纯HTML代码

    Args:
        content: LLM返回的原始内容

    Returns:
        清理后的HTML代码
    """
    # 如果包含HTML代码块，提取HTML部分
    if '```html' in content:
        # 提取html代码块
        start_idx = content.find('```html') + 7
        end_idx = content.find('```', start_idx)
        if end_idx != -1:
            return content[start_idx:end_idx].strip()

    elif '```' in content:
        # 提取普通代码块
        start_idx = content.find('```') + 3
        end_idx = content.find('```', start_idx)
        if end_idx != -1:
            extracted = content[start_idx:end_idx].strip()
            # 检查是否是HTML
            if extracted.startswith('<') and 'table' in extracted.lower():
                return extracted

    # 如果没有代码块，直接返回内容（假设已经是HTML）
    return content.strip()

def _is_valid_html_table(html_content: str) -> bool:
    """
    验证HTML表格内容是否有效

    Args:
        html_content: HTML内容

    Returns:
        是否有效的HTML表格
    """
    if not html_content or len(html_content.strip()) < 50:
        return False

    # 检查是否包含表格特征
    table_indicators = ['<table', '<tr', '<td', '<th', 'table>']
    indicators_found = sum(1 for indicator in table_indicators if indicator in html_content.lower())

    # 如果找到至少3个表格特征，认为HTML有效
    return indicators_found >= 3


def convert_md_to_html_with_css(md_path: str, html_title: str) -> str:
    """
    转换Markdown为HTML，采用与任务列表页面一致的风格
    """
    import pypandoc

    try:
        # 准备额外参数
        extra_args = [
            '--standalone',
            '--embed-resources',
            '--metadata', f'title={html_title}'
        ]

        html_content = pypandoc.convert_file(
            md_path,
            'html',
            format='md',
            extra_args=extra_args
        )

        # 采用与任务列表页面一致的CSS风格
        consistent_css = """
<style>
body {
    background-color: #f5f7fa;
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #333;
    line-height: 1.6;
    max-width: none !important;
    width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    text-align: center;
    margin-bottom: 30px;
    padding: 20px 0;
    background: linear-gradient(135deg, #4b6cb7 0%, #182848 100%);
    border-radius: 12px;
    color: white;
    box-shadow: 0 4px 15px rgba(75, 108, 183, 0.3);
}

header h1 {
    color: white;
    font-size: 2.2rem;
    margin: 0 0 10px 0;
    font-weight: 600;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

header h1 i {
    color: rgba(255, 255, 255, 0.9);
    margin-right: 12px;
}

header p {
    color: rgba(255, 255, 255, 0.9);
    font-size: 1.1rem;
    margin: 0;
    font-weight: 300;
}

.review-container {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    overflow: hidden;
    border: 1px solid #e1e5e9;
}

.content-area {
    padding: 40px;
}

/* 表格样式优化 */
table {
    width: 100%;
    border-collapse: collapse; /* 改回 collapse 以获得更好的自动列宽 */
    margin: 25px 0;
    background: white;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border: 1px solid #e1e5e9;
    table-layout: auto; /* 确保这是 auto */
}

col[style*="width"] {
    width: auto !important; /* 覆盖 pandoc 设置的固定宽度 */
}

th {
    background: linear-gradient(135deg, #4b6cb7 0%, #5a7bc8 100%);
    color: white;
    font-weight: 600;
    padding: 18px 16px;
    text-align: left;
    border-bottom: 2px solid #4b6cb7;
    font-size: 15px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    position: relative;
    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
    white-space: nowrap; /* 防止表头文字换行 */
}

th:after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 2px;
    background: rgba(255, 255, 255, 0.3);
}

td {
    padding: 16px;
    border-bottom: 1px solid #f0f2f5;
    vertical-align: top;
    font-size: 14px;
    color: #555;
    transition: all 0.2s ease;
    word-wrap: break-word; /* 允许长单词换行 */
    word-break: break-word; /* 中文换行 */
}

tr:last-child td {
    border-bottom: none;
}

tr:hover td {
    background-color: #f8fafd;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(75, 108, 183, 0.1);
}
th:first-child,
td:first-child {
    min-width: 150px; /* 第一列最小宽度 */
}

/* 斑马纹效果 */
tr:nth-child(even) {
    background-color: #fafbfc;
}

tr:nth-child(even):hover td {
    background-color: #f3f7fd;
}

/* 评分样式优化 */
.score-cell {
    font-weight: 700;
    text-align: center;
    font-size: 15px;
    border-radius: 6px;
    padding: 12px 8px;
    margin: 2px;
    min-width: 80px; /* 评分列固定宽度 */
    max-width: 100px;
    background: transparent !important;
    box-shadow: none !important;
    white-space: nowrap; /* 防止评分数字换行 */
}

.score-high {
    color: #28a745;
    font-weight: 800;
}

.score-medium {
    color: #fd7e14;
    font-weight: 800;
}

.score-low {
    color: #dc3545;
    font-weight: 800;
}

/* 项目名称样式优化 */
.project-name {
    font-weight: 700;
    color: #4b6cb7;
    font-size: 16px;
    display: block;
    margin-bottom: 4px;
}

.project-category {
    color: #888;
    font-size: 13px;
    font-weight: 500;
    background: #f8f9fa;
    padding: 4px 8px;
    border-radius: 4px;
    display: inline-block;
}

/* 标题样式 */
h2 {
    color: #2c3e50;
    font-size: 1.6rem;
    margin: 35px 0 25px 0;
    padding-bottom: 12px;
    border-bottom: 3px solid #4b6cb7;
    font-weight: 600;
    position: relative;
}

h2:first-child {
    margin-top: 0;
}

h2:after {
    content: '';
    position: absolute;
    bottom: -3px;
    left: 0;
    width: 80px;
    height: 3px;
    background: linear-gradient(90deg, #4b6cb7, #667eea);
    border-radius: 2px;
}

/* 结论部分样式优化 */
.conclusion-section {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border-left: 4px solid #4b6cb7;
    padding: 25px;
    margin: 30px 0;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.conclusion-section strong {
    color: #2c3e50;
    font-size: 1.2rem;
    display: block;
    margin-bottom: 15px;
    font-weight: 600;
}

/* 列表样式优化 */
ul, ol {
    margin: 12px 0;
    padding-left: 24px;
}

li {
    margin: 6px 0;
    line-height: 1.6;
    color: #555;
}

/* 表格内的特殊样式 */
td ul, td ol {
    margin: 6px 0;
    padding-left: 18px;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .container {
        padding: 10px;
    }

    .content-area {
        padding: 20px;
    }

    header h1 {
        font-size: 1.8rem;
    }

    table {
        font-size: 13px;
    }

    th, td {
        padding: 12px 10px;
    }

    th {
        font-size: 13px;
    }
}

/* 链接样式 */
a {
    color: #4b6cb7;
    text-decoration: none;
    font-weight: 500;
    transition: all 0.2s ease;
}

a:hover {
    color: #3a5aa0;
    text-decoration: underline;
}

/* 代码样式 */
code {
    background: linear-gradient(135deg, #f1f3f4, #e8eaed);
    padding: 3px 8px;
    border-radius: 4px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 0.9em;
    border: 1px solid #e1e5e9;
}

pre {
    background: linear-gradient(135deg, #f8f9fa, #e9ecef);
    padding: 20px;
    border-radius: 8px;
    overflow-x: auto;
    border-left: 4px solid #4b6cb7;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
}

/* 特殊文本样式 */
strong {
    color: #2c3e50;
    font-weight: 600;
}

em {
    color: #6c757d;
    font-style: italic;
}

/* 表格列宽优化 */
col[style*="width"] {
    background: rgba(75, 108, 183, 0.05);
}

/* 表头图标 */
th i {
    margin-right: 8px;
    opacity: 0.9;
}
</style>
"""

        # 插入CSS链接
        css_link = f'\n    <link rel="stylesheet" href="/static/font-awesome.all.min.css">\n    {consistent_css}\n</head>'
        html_content = html_content.replace('</head>', css_link)

        # 添加与任务列表页面一致的结构
        html_content = add_consistent_layout(html_content, html_title)

        # 为分数添加颜色
        html_content = add_score_colors(html_content)
        return html_content

    except Exception as e:
        logger.error(f"转换失败: {str(e)}")
        return ""


def add_consistent_layout(html_content: str, title: str) -> str:
    """
    添加与任务列表页面一致的结构布局
    """
    import re
    body_start = html_content.find('<body>')
    body_end = html_content.find('</body>')

    if body_start != -1 and body_end != -1:
        body_content = html_content[body_start + 6:body_end]

        # 移除pandoc生成的标题
        title_header_pattern = r'<header id="title-block-header">[\s\S]*?</header>'
        body_content = re.sub(title_header_pattern, '', body_content)

        # 移除单独的h1标题（如果有）
        h1_pattern = r'<h1 class="title">.*?</h1>'
        body_content = re.sub(h1_pattern, '', body_content)

        consistent_layout = f'''
<body>
    <div class="container">
        <header>
            <h1><i class="fas fa-file-alt"></i> {title}</h1>
        </header>

        <div class="review-container">
            <div class="content-area">
                {body_content}
            </div>
        </div>
    </div>
</body>'''

        html_content = html_content[:body_start] + consistent_layout + html_content[body_end + 7:]

    return html_content


def add_score_colors(html_content: str) -> str:
    """
    为评分添加颜色类
    """
    import re

    def add_score_class(match):
        score_text = match.group(1)
        try:
            score = float(score_text)
            if score >= 8:
                return f'<td class="score-cell score-high">{score}</td>'
            elif score >= 6:
                return f'<td class="score-cell score-medium">{score}</td>'
            else:
                return f'<td class="score-cell score-low">{score}</td>'
        except ValueError:
            return match.group(0)

    # 匹配分数单元格（只匹配纯数字的td）
    pattern = r'<td>(\d+\.?\d*)</td>'
    html_content = re.sub(pattern, add_score_class, html_content)

    # 为项目名称添加样式
    html_content = html_content.replace('lyc的可行性研究报告',
                                        '<span class="project-name">lyc的可行性研究报告</span><div class="project-category">项目可行性研究评审</div>')

    return html_content