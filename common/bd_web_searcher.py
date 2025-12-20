#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网页搜索工具 - 搜索关键词并获取前10个结果的详细内容（仅网页版）

pip install fake_useragent
"""

import os
import random
import sys
import time
import json
import re
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote, unquote, urljoin

import logging.config
import requests
import urllib3
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tqdm import tqdm

# 配置日志
log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(category=InsecureRequestWarning)


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    abstract: str
    rank: int
    source: str = ""  # 来源网站
    content: str = ""  # 网页正文内容
    content_length: int = 0
    fetch_time: str = ""
    fetch_status: str = "pending"  # pending, success, failed, timeout
    error_msg: str = ""
    images: List[str] = field(default_factory=list)  # 网页中的图片
    links: List[str] = field(default_factory=list)  # 网页中的链接


@dataclass
class SearchReport:
    """搜索报告"""
    keyword: str
    search_time: str
    total_results: int
    successful_fetches: int
    failed_fetches: int
    average_content_length: int
    results: List[SearchResult]


class BaiduWebSearcher:
    """百度网页搜索工具类（仅处理网页内容）"""

    def __init__(self,
                 max_results: int = 10,
                 timeout: int = 15,
                 retry_times: int = 2,
                 output_dir: str = "search_results",
                 enable_images: bool = False,
                 enable_links: bool = False):
        """
        初始化百度搜索器

        Args:
            max_results: 最大搜索结果数量
            timeout: 请求超时时间（秒）
            retry_times: 失败重试次数
            output_dir: 输出目录
            enable_images: 是否提取图片
            enable_links: 是否提取链接
        """
        self.max_results = max_results
        self.timeout = timeout
        self.retry_times = retry_times
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.enable_images = enable_images
        self.enable_links = enable_links

        # 初始化 UserAgent
        self.ua = UserAgent()

        # 百度搜索基础URL
        self.search_url = "https://www.baidu.com/s"

        # 请求头
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

        # 常见的不需要爬取的内容类型
        self.skip_patterns = [
            r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|gz|tar)$',
            r'\.(mp4|avi|mov|wmv|flv|mkv)$',
            r'\.(mp3|wav|flac|aac)$',
            r'\.(exe|dmg|pkg|apk|ipa)$',
        ]

        # 常见的中文新闻网站（优先处理）
        self.news_sites = [
            'people.com.cn', 'xinhuanet.com', 'cctv.com', 'gmw.cn',
            'china.com.cn', 'sina.com.cn', '163.com', 'qq.com',
            'sohu.com', 'ifeng.com', 'china.com', 'southcn.com',
        ]

        logger.info(f"百度网页搜索器初始化完成，最大结果数: {max_results}")

    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        return self.ua.random

    def is_valid_url(self, url: str) -> bool:
        """检查URL是否有效"""
        if not url or not url.startswith(('http://', 'https://')):
            return False

        # 检查是否需要跳过
        for pattern in self.skip_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.debug(f"跳过非网页URL: {url}")
                return False

        parsed = urlparse(url)
        return bool(parsed.netloc)

    @staticmethod
    def clean_html_content(html: str) -> str:
        """清理HTML内容，提取正文"""
        if not html:
            return ""

        try:
            soup = BeautifulSoup(html, 'lxml')

            # 移除不需要的标签
            for tag in soup(['script', 'style', 'nav', 'footer', 'header',
                             'aside', 'iframe', 'noscript', 'form', 'button',
                             'input', 'select', 'textarea']):
                tag.decompose()

            # 尝试多种方法提取正文

            # 方法1：查找article标签
            article = soup.find('article')
            if article:
                text = article.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    return text

            # 方法2：查找main标签
            main = soup.find('main')
            if main:
                text = main.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    return text

            # 方法3：查找包含文章内容的div
            content_divs = soup.find_all(['div', 'section'],
                                         class_=re.compile(r'content|article|post|main|body|text', re.I))
            if content_divs:
                # 选择最长的div
                contents = [div.get_text(separator='\n', strip=True) for div in content_divs]
                longest = max(contents, key=len)
                if len(longest) > 200:
                    return longest

            # 方法4：使用启发式方法 - 查找包含最多文字的段落
            paragraphs = soup.find_all(['p', 'div'])
            if paragraphs:
                # 合并连续的段落
                text_parts = []
                for p in paragraphs:
                    p_text = p.get_text(strip=True)
                    if len(p_text) > 50:  # 只保留较长的段落
                        text_parts.append(p_text)

                if text_parts:
                    text = '\n\n'.join(text_parts)
                    if len(text) > 200:
                        return text

            # 方法5：回退到body标签
            body = soup.find('body')
            if body:
                # 移除body中可能残留的无关元素
                for tag in body(['nav', 'footer', 'header', 'aside', 'ad', 'sidebar']):
                    tag.decompose()

                text = body.get_text(separator='\n', strip=True)
                # 清理多余的空行
                text = re.sub(r'\n\s*\n+', '\n\n', text)
                return text

            return ""

        except Exception as e:
            logger.error(f"清理HTML内容失败: {str(e)}")
            return ""

    def extract_images_and_links(self, soup: BeautifulSoup, base_url: str) -> Tuple[List[str], List[str]]:
        """提取网页中的图片和链接"""
        images = []
        links = []

        try:
            if self.enable_images:
                # 提取图片
                for img in soup.find_all('img', src=True):
                    img_url = img['src']
                    if img_url.startswith(('http://', 'https://')):
                        images.append(img_url)
                    elif img_url.startswith('//'):
                        images.append(f'https:{img_url}')
                    elif img_url.startswith('/'):
                        images.append(urljoin(base_url, img_url))

            if self.enable_links:
                # 提取链接
                for a in soup.find_all('a', href=True):
                    link = a['href']
                    if link.startswith(('http://', 'https://')):
                        links.append(link)
                    elif link.startswith('//'):
                        links.append(f'https:{link}')
                    elif link.startswith('/'):
                        links.append(urljoin(base_url, link))

        except Exception as e:
            logger.error(f"提取图片和链接失败: {str(e)}")

        return images, links

    def fetch_webpage(self, url: str) -> Tuple[bool, str, Optional[BeautifulSoup]]:
        """
        获取网页内容

        Returns:
            Tuple[成功标志, 错误信息/内容, BeautifulSoup对象]
        """
        if not self.is_valid_url(url):
            return False, "无效的URL", None

        for attempt in range(self.retry_times):
            try:
                # 更新User-Agent
                self.headers['User-Agent'] = self.get_random_user_agent()

                logger.debug(f"获取网页: {url} (尝试 {attempt + 1}/{self.retry_times})")

                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False  # 注意：生产环境应设为True
                )

                # 检查响应状态
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    logger.warning(f"获取失败 {url}: {error_msg}")
                    if attempt < self.retry_times - 1:
                        time.sleep(1)
                        continue
                    return False, error_msg, None

                # 检查内容类型
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    error_msg = f"非HTML内容: {content_type}"
                    logger.warning(f"非HTML内容 {url}: {content_type}")
                    return False, error_msg, None

                # 检查编码
                response.encoding = response.apparent_encoding or 'utf-8'
                html_content = response.text

                if len(html_content) < 100:
                    error_msg = "内容过短"
                    logger.warning(f"内容过短 {url}")
                    return False, error_msg, None

                # 解析HTML
                soup = BeautifulSoup(html_content, 'lxml')

                logger.info(f"成功获取网页: {url} ({len(html_content)} 字符)")
                return True, html_content, soup

            except requests.exceptions.Timeout:
                error_msg = "请求超时"
                logger.warning(f"请求超时 {url}")
                if attempt < self.retry_times - 1:
                    time.sleep(2)
                    continue

            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                logger.warning(f"请求异常 {url}: {error_msg}")
                if attempt < self.retry_times - 1:
                    time.sleep(1)
                    continue

            except Exception as e:
                error_msg = f"未知错误: {str(e)}"
                logger.error(f"获取网页异常 {url}: {error_msg}")
                return False, error_msg, None

        return False, error_msg, None

    def search_baidu(self, keyword: str, page: int = 1) -> List[SearchResult]:
        """
        在百度搜索关键词

        Args:
            keyword: 搜索关键词
            page: 页码

        Returns:
            搜索结果列表
        """
        results = []

        try:
            # 准备搜索参数
            params = {
                'wd': keyword,
                'pn': (page - 1) * 10,  # 百度每页10个结果
                'rn': 10,
                'ie': 'utf-8',
                'tn': 'baidulocal',
            }

            # 更新User-Agent
            self.headers['User-Agent'] = self.get_random_user_agent()

            logger.info(f"搜索百度: {keyword} (第{page}页)")

            response = requests.get(
                self.search_url,
                params=params,
                headers=self.headers,
                timeout=self.timeout,
                verify=False,
                proxies=None
            )

            if response.status_code != 200:
                logger.error(f"百度搜索失败: HTTP {response.status_code}")
                return results

            response.encoding = 'utf-8'
            html = response.text
            logger.debug(f"get_html_result, {html}")
            # 解析搜索结果
            soup = BeautifulSoup(html, 'lxml')

            # 查找所有结果容器
            result_containers = soup.find_all('div', class_='result')
            if not result_containers:
                # 尝试其他选择器
                result_containers = soup.find_all('div', {'class': re.compile(r'c-container')})

            for i, container in enumerate(result_containers[:self.max_results]):
                try:
                    # 提取标题和链接
                    title_elem = container.find('h3')
                    if not title_elem:
                        continue

                    link_elem = title_elem.find('a')
                    if not link_elem or not link_elem.get('href'):
                        continue

                    title = link_elem.get_text(strip=True)
                    url = link_elem['href']

                    # 处理百度跳转链接
                    if 'baidu.com/link?' in url:
                        # 尝试获取真实URL
                        match = re.search(r'url=([^&]+)', url)
                        if match:
                            url = unquote(match.group(1))

                    # 提取摘要
                    abstract_elem = container.find('div', class_=re.compile(r'abstract|content'))
                    abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""

                    # 提取来源网站
                    source = ""
                    source_elem = container.find('span', class_='c-showurl')
                    if source_elem:
                        source = source_elem.get_text(strip=True).replace(' ', '')

                    # 创建结果对象
                    result = SearchResult(
                        title=title,
                        url=url,
                        abstract=abstract,
                        rank=i + 1,
                        source=source
                    )

                    results.append(result)
                    logger.debug(f"找到结果 {i + 1}: {title[:50]}...")

                except Exception as e:
                    logger.error(f"解析搜索结果失败: {str(e)}")
                    continue

            logger.info(f"找到 {len(results)} 个搜索结果")
            return results

        except Exception as e:
            logger.error(f"百度搜索异常: {str(e)}")
            return results

    def fetch_all_contents(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        获取所有搜索结果的内容

        Args:
            results: 搜索结果列表

        Returns:
            更新后的结果列表
        """
        logger.info(f"开始获取 {len(results)} 个网页的内容...")

        for result in tqdm(results, desc="获取网页内容", unit="页"):
            try:
                if not self.is_valid_url(result.url):
                    result.fetch_status = "failed"
                    result.error_msg = "无效的URL"
                    continue

                # 获取网页
                success, content_or_error, soup = self.fetch_webpage(result.url)

                if success and soup:
                    # 提取正文内容
                    content = self.clean_html_content(content_or_error)

                    # 提取图片和链接（如果需要）
                    images, links = [], []
                    if self.enable_images or self.enable_links:
                        images, links = self.extract_images_and_links(soup, result.url)

                    # 更新结果
                    result.content = content
                    result.content_length = len(content)
                    result.fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    result.fetch_status = "success"
                    result.images = images if self.enable_images else []
                    result.links = links if self.enable_links else []

                    logger.debug(f"成功获取: {result.title[:30]}... ({result.content_length} 字符)")

                else:
                    result.fetch_status = "failed"
                    result.error_msg = content_or_error
                    logger.warning(f"获取失败: {result.title[:30]}... - {content_or_error}")

                # 避免请求过快
                time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                result.fetch_status = "failed"
                result.error_msg = f"异常: {str(e)}"
                logger.error(f"处理结果异常: {result.title[:30]}... - {str(e)}")

        return results

    def generate_report(self, keyword: str, results: List[SearchResult]) -> SearchReport:
        """生成搜索报告"""
        successful = sum(1 for r in results if r.fetch_status == "success")
        failed = len(results) - successful

        # 计算平均内容长度
        contents = [r.content_length for r in results if r.content_length > 0]
        avg_length = sum(contents) // len(contents) if contents else 0

        report = SearchReport(
            keyword=keyword,
            search_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_results=len(results),
            successful_fetches=successful,
            failed_fetches=failed,
            average_content_length=avg_length,
            results=results
        )

        return report

    def save_results(self, report: SearchReport, format_type: str = "all"):
        """
        保存搜索结果

        Args:
            report: 搜索报告
            format_type: 保存格式 (json, markdown, html, all)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        keyword_safe = re.sub(r'[^\w\-_]', '_', report.keyword)[:50]
        base_filename = f"{keyword_safe}_{timestamp}"

        # 保存为JSON
        if format_type in ["json", "all"]:
            json_path = self.output_dir / f"{base_filename}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(report), f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存为JSON: {json_path}")

        # 保存为Markdown
        if format_type in ["markdown", "all"]:
            md_path = self.output_dir / f"{base_filename}.md"
            self._save_as_markdown(report, md_path)
            logger.info(f"结果已保存为Markdown: {md_path}")

        # 保存为HTML
        if format_type in ["html", "all"]:
            html_path = self.output_dir / f"{base_filename}.html"
            self._save_as_html(report, html_path)
            logger.info(f"结果已保存为HTML: {html_path}")

    def _save_as_markdown(self, report: SearchReport, filepath: Path):
        """保存为Markdown格式"""
        with open(filepath, 'w', encoding='utf-8') as f:
            # 报告头信息
            f.write(f"# 百度搜索报告: {report.keyword}\n\n")
            f.write(f"**搜索时间**: {report.search_time}\n")
            f.write(f"**总结果数**: {report.total_results}\n")
            f.write(f"**成功获取**: {report.successful_fetches}\n")
            f.write(f"**失败获取**: {report.failed_fetches}\n")
            f.write(f"**平均内容长度**: {report.average_content_length} 字符\n\n")

            f.write("---\n\n")

            # 详细结果
            for result in report.results:
                f.write(f"## {result.rank}. {result.title}\n\n")
                f.write(f"**URL**: [{result.url}]({result.url})\n\n")
                f.write(f"**来源**: {result.source}\n\n")
                f.write(f"**状态**: {result.fetch_status}")
                if result.error_msg:
                    f.write(f" ({result.error_msg})")
                f.write("\n\n")
                f.write(f"**获取时间**: {result.fetch_time}\n\n")
                f.write(f"**内容长度**: {result.content_length} 字符\n\n")

                f.write("**摘要**:\n")
                f.write(f"> {result.abstract}\n\n")

                f.write("**详细内容**:\n")
                f.write(f"{result.content[:1000]}...\n\n")  # 只保存前1000字符

                if self.enable_images and result.images:
                    f.write("**相关图片**:\n")
                    for img in result.images[:5]:  # 最多5张图片
                        f.write(f"![]({img})\n")
                    f.write("\n")

                if self.enable_links and result.links:
                    f.write("**相关链接**:\n")
                    for link in result.links[:10]:  # 最多10个链接
                        f.write(f"- [{link}]({link})\n")
                    f.write("\n")

                f.write("---\n\n")

    def _save_as_html(self, report: SearchReport, filepath: Path):
        """保存为HTML格式"""
        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>百度搜索报告: {keyword}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .header {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .result {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                .success {{ border-left: 5px solid #28a745; }}
                .failed {{ border-left: 5px solid #dc3545; }}
                .title {{ color: #1a0dab; font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .url {{ color: #006621; font-size: 14px; margin-bottom: 10px; }}
                .content {{ margin-top: 10px; padding: 10px; background: #f9f9f9; border-radius: 3px; }}
                .stats {{ background: #e9ecef; padding: 10px; border-radius: 3px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>百度搜索报告: {keyword}</h1>
                <div class="stats">
                    <p><strong>搜索时间:</strong> {search_time}</p>
                    <p><strong>总结果数:</strong> {total_results}</p>
                    <p><strong>成功获取:</strong> {successful_fetches}</p>
                    <p><strong>失败获取:</strong> {failed_fetches}</p>
                    <p><strong>平均内容长度:</strong> {average_length} 字符</p>
                </div>
            </div>

            {results_html}

            <footer style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
                <p>生成时间: {current_time} | 百度搜索工具 v1.0</p>
            </footer>
        </body>
        </html>
        """

        # 生成每个结果的HTML
        results_html = ""
        for result in report.results:
            status_class = "success" if result.fetch_status == "success" else "failed"

            # 处理内容（限制长度）
            content_preview = result.content[:500] + "..." if len(result.content) > 500 else result.content

            results_html += f"""
            <div class="result {status_class}">
                <div class="title">{result.rank}. {result.title}</div>
                <div class="url">
                    <a href="{result.url}" target="_blank">{result.url}</a>
                    <br>
                    <small>来源: {result.source} | 状态: {result.fetch_status} | 获取时间: {result.fetch_time}</small>
                </div>
                <div>
                    <strong>摘要:</strong>
                    <p>{result.abstract}</p>
                </div>
                <div>
                    <strong>详细内容 ({result.content_length} 字符):</strong>
                    <div class="content">{content_preview}</div>
                </div>
            </div>
            """

        # 填充模板
        html_content = html_template.format(
            keyword=report.keyword,
            search_time=report.search_time,
            total_results=report.total_results,
            successful_fetches=report.successful_fetches,
            failed_fetches=report.failed_fetches,
            average_length=report.average_content_length,
            results_html=results_html,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def search_and_fetch(self,
                         keyword: str,
                         pages: int = 1,
                         save_format: str = "all",
                         fetch_content: bool = True) -> SearchReport:
        """
        完整的搜索和获取流程

        Args:
            keyword: 搜索关键词
            pages: 搜索页数（每页10个结果）
            save_format: 保存格式
            fetch_content: 是否获取详细内容

        Returns:
            搜索报告
        """
        logger.info(f"开始搜索: '{keyword}' (页数: {pages})")

        # 1. 搜索百度
        all_results = []
        for page in range(1, pages + 1):
            logger.info(f"搜索第 {page} 页...")
            page_results = self.search_baidu(keyword, page)
            all_results.extend(page_results)

            if len(all_results) >= self.max_results:
                all_results = all_results[:self.max_results]
                break

            time.sleep(random.uniform(1, 2))  # 避免请求过快

        # 限制结果数量
        all_results = all_results[:self.max_results]

        # 2. 获取详细内容
        if fetch_content and all_results:
            all_results = self.fetch_all_contents(all_results)

        # 3. 生成报告
        report = self.generate_report(keyword, all_results)

        # 4. 保存结果
        if all_results:
            self.save_results(report, save_format)

        # 5. 打印摘要
        self.print_summary(report)

        return report

    def print_summary(self, report: SearchReport):
        """打印搜索摘要"""
        print("\n" + "=" * 60)
        print(f"搜索完成: '{report.keyword}'")
        print("=" * 60)
        print(f"搜索时间: {report.search_time}")
        print(f"总结果数: {report.total_results}")
        print(f"成功获取: {report.successful_fetches}")
        print(f"失败获取: {report.failed_fetches}")
        print(f"平均内容长度: {report.average_content_length} 字符")
        print("\n前5个结果:")
        print("-" * 60)

        for i, result in enumerate(report.results[:5], 1):
            status_icon = "✓" if result.fetch_status == "success" else "✗"
            print(f"{i}. [{status_icon}] {result.title[:50]}...")
            print(f"   URL: {result.url}")
            print(f"   长度: {result.content_length} 字符")
            print()

        print("详细报告已保存至:", self.output_dir.resolve())
        print("=" * 60)


# 异步版本（可选）
class AsyncBaiduSearcher:
    """异步版本的百度搜索器"""

    def __init__(self, max_results=10, timeout=15):
        self.max_results = max_results
        self.timeout = timeout
        self.searcher = BaiduWebSearcher(max_results, timeout)

    async def async_search_and_fetch(self, keyword: str):
        """异步搜索和获取"""
        import aiohttp

        # 先同步搜索获取URL
        results = self.searcher.search_baidu(keyword)

        async def fetch_one(result):
            """异步获取单个网页"""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(result.url, timeout=self.timeout) as response:
                        if response.status == 200:
                            html = await response.text()
                            result.content = self.searcher.clean_html_content(html)
                            result.content_length = len(result.content)
                            result.fetch_status = "success"
                        else:
                            result.fetch_status = "failed"
                            result.error_msg = f"HTTP {response.status}"
            except Exception as e:
                result.fetch_status = "failed"
                result.error_msg = str(e)

            result.fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return result

        # 并发获取所有网页
        tasks = [fetch_one(result) for result in results]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤异常
        results = [r for r in results if not isinstance(r, Exception)]

        report = self.searcher.generate_report(keyword, results)
        return report


def main():
    """命令行入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description="百度网页搜索工具")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("-n", "--num", type=int, default=10, help="最大结果数 (默认: 10)")
    parser.add_argument("-p", "--pages", type=int, default=1, help="搜索页数 (默认: 1)")
    parser.add_argument("-t", "--timeout", type=int, default=15, help="超时时间(秒) (默认: 15)")
    parser.add_argument("-o", "--output", default="search_results", help="输出目录 (默认: search_results)")
    parser.add_argument("-f", "--format", default="all", choices=["json", "markdown", "html", "all"],
                        help="输出格式 (默认: all)")
    parser.add_argument("--no-content", action="store_true", help="不获取详细内容")
    parser.add_argument("--images", action="store_true", help="提取图片")
    parser.add_argument("--links", action="store_true", help="提取链接")

    args = parser.parse_args()

    # 创建搜索器
    searcher = BaiduWebSearcher(
        max_results=args.num,
        timeout=args.timeout,
        output_dir=args.output,
        enable_images=args.images,
        enable_links=args.links
    )

    try:
        # 执行搜索
        report = searcher.search_and_fetch(
            keyword=args.keyword,
            pages=args.pages,
            save_format=args.format,
            fetch_content=not args.no_content
        )

        # 返回成功
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n搜索被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"搜索失败: {str(e)}")
        logger.error(f"搜索失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # 示例使用
    try:
        keyword = "Python 编程"
        searcher = BaiduWebSearcher(max_results=5, timeout=10)
        report = searcher.search_and_fetch(keyword, pages=1)

    except KeyboardInterrupt:
        print("\n再见！")