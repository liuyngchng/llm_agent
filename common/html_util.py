#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import functools
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


@functools.lru_cache(maxsize=128)
def convert_md_to_html_with_css(md_path: str, html_title: str,
    css_link: str = '<link rel="stylesheet" href="/static/paper_review_result.css">') -> str:
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

        # 插入CSS链接
        full_css_link = f'\n    <link rel="stylesheet" href="/static/font-awesome.all.min.css">\n    {css_link}\n</head>'
        html_content = html_content.replace('</head>', full_css_link)

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