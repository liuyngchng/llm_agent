#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
import json
import os
import logging.config
import sys
from typing import Generator

import subprocess
import tempfile

import requests

from apps.doc_forge.code_executor import extract_python_blocks, execute_code, snapshot_dir

import urllib3
# 全局禁用不安全请求警告 InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ALLOWED_EXTENSIONS = {
    'txt', 'md', 'py', 'js', 'html', 'css', 'json',
    'pdf', 'xlsx', 'xls', 'docx', 'doc', 'ppt', 'pptx',
    'jpg', 'jpeg', 'png', 'gif'
}

# 旧 Office 格式 -> 新格式映射（LibreOffice headless 自动转换）
_OLD_FORMAT_MAP = {'doc': 'docx', 'ppt': 'pptx', 'xls': 'xlsx'}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format=LOG_FORMATTER,force=True)
logger = logging.getLogger(__name__)

# ============== 配置常量 ==============
# LLM API 配置（可替换为任何兼容OpenAI API的接口）
class LLMConfig:

    # 请求参数配置
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 8000))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
    TOP_P = float(os.getenv("TOP_P", 0.9))

    # 流式响应配置
    STREAM = True
    TIMEOUT = 600  # 请求超时时间（秒）

    # 系统提示词
    SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "你是一个有用的AI助手。请用中文回答用户的问题。")


def build_doc_processing_system_prompt(file_paths: list[str] = None,
                                        output_dir: str = "output_doc",
                                        upload_dir: str = "upload_doc") -> str:
    """Build system prompt for document processing agent."""
    files_section = ""
    if file_paths:
        files_list = "\n".join(f"  - {fp}" for fp in file_paths)
        files_section = f"""
## 可用文件
以下文件已上传并可供处理（绝对路径）：
{files_list}"""

    return f"""你是一个专业的文档处理助手。你可以帮助用户读取、修改、合并和创建文档（doc/docx、ppt/pptx、xls/xlsx、pdf 等）。

## 核心能力
- 解析和读取 doc/docx、ppt/pptx、xls/xlsx、pdf 文件的内容（旧格式 .doc/.ppt/.xls 自动转为新格式后处理）
- 按用户要求修改文档内容（直接修改原格式文件，保留原始排版和样式）
- 合并多个文档
- 创建新文档
- 提取文档的目录、特定章节等

## 可用的 Python 库
你可以编写 Python 脚本来处理文档。以下库已安装可用：
- python-docx — 读取/创建/修改 Word docx 文档（原生接口，保留格式）
- common.docx_revision_util — Word 修订模式工具（Track Changes），支持以修订模式插入/删除/替换文本
- python-pptx — 读取/创建/修改 PowerPoint pptx 文档（原生接口，保留格式）
- openpyxl — 读取/创建/修改 Excel xlsx 文件（原生接口，保留格式）
- pdfplumber — 解析和提取 PDF 内容
- reportlab — 创建 PDF 文件
- pypandoc — 文档格式转换（仅当用户明确要求转换格式时使用）
- Pillow (PIL) — 图像处理
- LibreOffice — 系统级可用，旧格式文件（.doc/.ppt/.xls）上传时自动转为新格式

## Word 修订模式（Track Changes）
当用户要求审阅、修订、校对 Word 文档，或要求"以修订模式"修改时，使用 `common.docx_revision_util`：

```python
from common.docx_revision_util import (
    tracked_insert_text, tracked_delete_text, tracked_replace_text,
    tracked_replace_in_document, tracked_delete_paragraph,
    accept_all_changes, reject_all_changes, get_tracked_changes_summary,
)

doc = Document(os.path.join(UPLOAD_DIR, 'report.docx'))

# 全文替换（修订模式）
count = tracked_replace_in_document(doc, '旧文本', '新文本', author='Reviewer')
print(f'共修订 {{count}} 处')

# 单段落操作
tracked_insert_text(doc, doc.paragraphs[0], '新增内容。', author='Reviewer')
tracked_delete_text(doc, doc.paragraphs[2], '要删除的文本', author='Reviewer')

# 查看修订摘要
summary = get_tracked_changes_summary(doc)
print(f"插入 {{summary['insertions']}} 处，删除 {{summary['deletions']}} 处")

# 如需最终接受/拒绝所有修订：
# accept_all_changes(doc)
# reject_all_changes(doc)

doc.save(os.path.join(OUTPUT_DIR, 'report_revised.docx'))
```

**重要：** 默认保留修订标记，不要自动 accept_all_changes，除非用户明确要求"接受修订"或"最终版"。

## 文档处理原则（重要）
- **优先使用原生库直接操作原始文件格式**（python-docx、python-pptx、openpyxl），不要先将文档转为 markdown
  处理完再转回去，这样会丢失原始排版、样式、图片等格式信息
- 修改已有文档时，用原生库打开原始文件 → 修改 → 保存回原格式
- 只有用户**明确要求**转换格式（如"把这个 docx 转成 markdown"）时才使用 pypandoc 做格式转换
- 创建新文档时，直接用原生库生成目标格式（docx/pptx/xlsx/pdf），不要先生成 md 再转换

## 脚本编写规则
当需要处理文档时，请在 ```python 代码块中编写完整的 Python 脚本：
- 上传文件目录: `{upload_dir}/`
- 输出文件保存到: `{output_dir}/`
- 脚本执行环境中已预定义变量 UPLOAD_DIR 和 OUTPUT_DIR，可直接使用
- 使用 `print()` 输出处理结果和状态信息
- 代码块第一行用注释简要说明脚本功能（如 `# 修改报告中的表格数据并生成新文件`）
- 代码块内只写 Python 代码，不要混入解释文字

## 使用指南
- 如果用户只是询问文档内容，直接回答即可
- 如果需要修改/创建文档，先简要说明你的方案，然后在一个 ```python 代码块中编写脚本
- 脚本执行后，系统会自动提供下载链接{files_section}"""


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _convert_old_format(filepath: str) -> str:
    """使用 LibreOffice headless 将旧 Office 格式转为新格式，返回转换后文件路径。"""
    ext = os.path.splitext(filepath)[1].lstrip('.').lower()
    target_ext = _OLD_FORMAT_MAP[ext]
    base_name = os.path.splitext(os.path.basename(filepath))[0]

    output_dir = tempfile.mkdtemp(prefix='docforge_')
    result = subprocess.run(
        ['libreoffice', '--headless', '--convert-to', target_ext,
         '--outdir', output_dir, filepath],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip()
        logger.error(f"LibreOffice 转换失败: {filepath} -> {target_ext}: {error_msg}")
        raise RuntimeError(f"旧格式文件转换失败（{ext} -> {target_ext}）")

    output_path = os.path.join(output_dir, f"{base_name}.{target_ext}")
    logger.info(f"旧格式转换成功: {os.path.basename(filepath)} -> {os.path.basename(output_path)}")
    return output_path


def get_pptx_content(filepath) -> str:
    """使用 python-pptx 原生接口提取 pptx 文件内容。"""
    try:
        from pptx import Presentation

        prs = Presentation(filepath)
        slides_text = []
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_lines = [f"## Slide {slide_num}"]
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_lines.append(shape.text.strip())
                if shape.has_table:
                    table = shape.table
                    rows_text = []
                    for row in table.rows:
                        cells = [cell.text.strip() for cell in row.cells]
                        rows_text.append(" | ".join(cells))
                    if rows_text:
                        slide_lines.append("\n".join(rows_text))
            slides_text.append("\n".join(slide_lines))
        result = "\n\n".join(slides_text)
        logger.info(f"pptx_file_parse_success, {filepath}，slides: {len(prs.slides)}，len: {len(result)}")
        return result

    except ImportError:
        logger.warning("需要安装 python-pptx 库来解析PPT文件")
        return "[需要安装 python-pptx 库来解析PPT文件]"
    except Exception as e:
        logger.error(f"读取pptx文件时出错: {str(e)}")
        return f"[读取pptx文件时出错: {str(e)}]"


def extract_text_from_file(filepath, filename):
    """从文件中提取文本内容"""
    try:
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

        logger.info(f"正在提取文件: {filename}, 扩展名: {ext}")

        # 文本文件直接读取
        if ext in ['txt', 'md', 'py', 'js', 'html', 'css', 'json']:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                logger.info(f"文本文件读取成功，长度: {len(content)} 字符")
                return content

        # PDF文件（需要安装PyPDF2或pdfplumber）
        elif ext == 'pdf':
            try:
                import pdfplumber
                text = []
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:  # 添加判断，避免None值
                            text.append(page_text)
                result = '\n'.join(text)
                logger.info(f"pdf_file_parse_success, {filepath}，page_count: {len(pdf.pages)}，file_len: {len(result)}")
                return result
            except ImportError:
                logger.warning("需要安装 pdfplumber 库来解析PDF文件")
                return "[需要安装 pdfplumber 库来解析PDF文件]"

        # Word 文档（.doc 自动通过 LibreOffice 转为 .docx）
        elif ext in ('docx', 'doc'):
            path = _convert_old_format(filepath) if ext == 'doc' else filepath
            return get_docx_content(path)

        # PPT 文档（.ppt 自动通过 LibreOffice 转为 .pptx）
        elif ext in ('pptx', 'ppt'):
            path = _convert_old_format(filepath) if ext == 'ppt' else filepath
            return get_pptx_content(path)

        # Excel 文件（.xls 自动通过 LibreOffice 转为 .xlsx）
        elif ext in ('xlsx', 'xls'):
            path = _convert_old_format(filepath) if ext == 'xls' else filepath
            return get_xlsx_content(path)

        # 图片文件（需要安装PIL和pytesseract）
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            try:
                from PIL import Image
                import pytesseract
                image = Image.open(filepath)
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                logger.info(f"图片文件识别成功，识别到 {len(text)} 字符")
                return text if text else "[图片中未识别到文字]"
            except ImportError:
                logger.warning("需要安装PIL和pytesseract库来识别图片文字")
                return "[需要安装PIL和pytesseract库来识别图片文字]"

        else:
            logger.warning(f"不支持的文件格式: {ext}")
            return f"[不支持的文件格式: {ext}]"

    except Exception as e:
        logger.error(f"读取文件时出错: {str(e)}")
        return f"[读取文件时出错: {str(e)}]"


def get_xlsx_content(filepath) -> str:
    """
    获取 xlsx 文件的内容
    """
    try:
        from openpyxl import load_workbook
        wb = load_workbook(filename=filepath, read_only=True, data_only=True)
        text_lines = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            text_lines.append(f"## {sheet_name}")

            # 获取最大列宽
            max_col = ws.max_column
            max_row = ws.max_row

            if max_row > 0 and max_col > 0:
                # 创建Markdown表格 - 修复这里
                rows = []
                for row in ws.iter_rows(min_row=1, max_row=max_row,
                                        min_col=1, max_col=max_col,
                                        values_only=True):
                    # 不要转义管道符，而是处理空值和特殊字符
                    formatted_row = []
                    for cell in row:
                        if cell is None:
                            formatted_row.append("")
                        else:
                            # 将单元格内容转换为字符串，并处理换行
                            cell_str = str(cell)
                            # 替换换行符为空格，避免破坏表格格式
                            cell_str = cell_str.replace('\n', ' ').replace('\r', ' ')
                            # 清理多余的空白字符
                            cell_str = ' '.join(cell_str.split())
                            formatted_row.append(cell_str)
                    rows.append(formatted_row)

                # 生成Markdown表格
                if rows:
                    # 表头
                    md_lines = ['| ' + ' | '.join(rows[0]) + ' |']
                    # 表头分隔线
                    header_separator = ['---'] * len(rows[0])
                    md_lines.append('| ' + ' | '.join(header_separator) + ' |')
                    # 数据行
                    for row in rows[1:]:
                        md_lines.append('| ' + ' | '.join(row) + ' |')

                    text_lines.append('\n'.join(md_lines))
                text_lines.append('')  # 空行分隔

        result = '\n'.join(text_lines)
        logger.info(f"Excel文件解析成功，工作表数: {len(wb.sheetnames)}，长度: {len(result)} 字符")
        return result
    except ImportError:
        logger.warning("需要安装openpyxl库来解析Excel文件")
        return "[需要安装openpyxl库来解析Excel文件]"
    except Exception as e:
        logger.error(f"读取Excel文件时出错: {str(e)}")
        return f"[读取Excel文件时出错: {str(e)}]"


def get_docx_content(filepath) -> str:
    """
    使用 python-docx 原生接口提取 docx 文件内容。
    保留文档结构（标题层级、表格、列表），不通过 markdown 转换。
    """
    try:
        from docx import Document

        doc = Document(filepath)
        text_parts = []

        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ''
            text = para.text.strip()
            if not text:
                continue

            if style_name.startswith('Heading'):
                try:
                    level = int(style_name.replace('Heading ', ''))
                    prefix = '#' * min(level, 6)
                    text_parts.append(f"\n{prefix} {text}")
                except ValueError:
                    text_parts.append(f"\n## {text}")
            elif 'List' in style_name or 'list' in style_name.lower():
                text_parts.append(f"- {text}")
            else:
                text_parts.append(text)

        for i, table in enumerate(doc.tables):
            text_parts.append(f"\n### 表格 {i + 1}")
            row_data = []
            for row in table.rows:
                cells = [cell.text.strip().replace('\n', ' ').replace('|', '\\|') for cell in row.cells]
                row_data.append('| ' + ' | '.join(cells) + ' |')
            if row_data:
                text_parts.append(row_data[0])
                num_cols = len(table.rows[0].cells)
                text_parts.append('| ' + ' | '.join(['---'] * num_cols) + ' |')
                for row in row_data[1:]:
                    text_parts.append(row)

        for section in doc.sections:
            header = section.header
            if header and header.paragraphs:
                h_text = ' '.join(p.text for p in header.paragraphs if p.text.strip())
                if h_text:
                    text_parts.insert(0, f"[页眉: {h_text}]")
            footer = section.footer
            if footer and footer.paragraphs:
                f_text = ' '.join(p.text for p in footer.paragraphs if p.text.strip())
                if f_text:
                    text_parts.append(f"[页脚: {f_text}]")

        result = '\n'.join(text_parts)
        logger.info(f"docx_file_parse_success, {filepath}, file_len: {len(result)}")
        return result

    except ImportError:
        logger.warning("需要安装 python-docx 库来解析Word文档")
        return "[需要安装 python-docx 库来解析Word文档]"
    except Exception as e:
        logger.error(f"读取docx文件时出错: {str(e)}")
        return f"[读取docx文件时出错: {str(e)}]"


def generate_stream_response(messages: list, llm_cfg: dict, max_tokens: int = None,
                            include_done: bool = True) -> Generator[str, None, None]:
    """
    生成流式响应
    :param include_done: 是否在流结束后发送 [DONE] 信号
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_cfg['llm_api_key']}"
    }

    payload = {
        "model": llm_cfg['llm_model_name'],
        "messages": messages,
        "max_tokens": max_tokens or LLMConfig.MAX_TOKENS,
        "temperature": LLMConfig.TEMPERATURE,
        "top_p": LLMConfig.TOP_P,
        "stream": LLMConfig.STREAM,
    }

    try:
        logger.info(f"向LLM API发送请求，模型: {llm_cfg['llm_model_name']}, 消息数量: {len(messages)}")
        logger.info(f"请求参数: max_tokens={payload['max_tokens']}, temperature={LLMConfig.TEMPERATURE}")

        response = requests.post(
            f"{llm_cfg['llm_api_uri']}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            verify=False,
            timeout=LLMConfig.TIMEOUT
        )

        # 记录响应状态码
        logger.info(f"llm_api_response_code: {response.status_code}")

        # 如果响应不是200，记录详细错误信息
        if response.status_code != 200:
            error_content = response.text
            logger.error(f"llm_api_response_error, {response.status_code}: {error_content}")

            try:
                error_json = response.json()
                logger.error(f"llm_api_response_error_json: {json.dumps(error_json, indent=2, ensure_ascii=False)}")

                # 提取具体错误信息
                if 'error' in error_json:
                    error_msg = error_json['error']
                    if isinstance(error_msg, dict) and 'message' in error_msg:
                        error_detail = error_msg['message']
                    elif isinstance(error_msg, str):
                        error_detail = error_msg
                    else:
                        error_detail = str(error_msg)

                    logger.error(f"错误消息: {error_detail}")
                else:
                    logger.error(f"完整错误响应: {json.dumps(error_json, ensure_ascii=False)}")

            except json.JSONDecodeError:
                logger.error(f"错误响应不是JSON格式，原始内容: {error_content}")
            except Exception as e:
                logger.error(f"解析错误响应时出错: {str(e)}, 原始内容: {error_content}")

            # 向客户端返回错误信息
            error_message = f"API请求失败: {response.status_code} - {response.reason}"
            yield f"data: {json.dumps({'error': error_message})}\n\n"
            if include_done:
                yield "data: [DONE]\n\n"
            return

        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]  # 移除 'data: ' 前缀
                    if data != '[DONE]':
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta and delta['content']:
                                    yield f"data: {json.dumps({'content': delta['content']})}\n\n"
                        except json.JSONDecodeError:
                            logger.warning("解析JSON数据失败")
                            continue

        if include_done:
            yield "data: [DONE]\n\n"

    except requests.exceptions.RequestException as e:
        error_msg = f"API请求错误: {str(e)}"
        logger.error(error_msg)

        # 如果有响应对象，记录更多信息
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_json = e.response.json()
                logger.error(f"请求异常中的错误详情: {json.dumps(error_json, ensure_ascii=False)}")
            except:
                logger.error(f"请求异常中的响应内容: {e.response.text}")

        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        if include_done:
            yield "data: [DONE]\n\n"


def _call_llm_sync(messages: list, llm_cfg: dict, max_tokens: int = None) -> str:
    """同步调用 LLM，收集完整响应文本（非流式）。"""
    full_text = ""
    for chunk in generate_stream_response(messages, llm_cfg, max_tokens, include_done=False):
        if chunk.startswith('data: ') and chunk != 'data: [DONE]\n\n':
            try:
                data = json.loads(chunk[6:].strip())
                if 'content' in data:
                    full_text += data['content']
            except (json.JSONDecodeError, KeyError):
                pass
    return full_text


def generate_stream_response_with_execution(
    messages: list, llm_cfg: dict, output_dir: str = "output_doc",
    upload_dir: str = "upload_doc", max_tokens: int = None
) -> Generator[str, None, None]:
    """
    流式响应 + 代码执行引擎。

    先流式传输 LLM 回复，然后从回复中提取 Python 代码块并在服务器端执行。
    执行结果（stdout/stderr/下载链接）作为额外的 SSE 数据发送给前端。
    """
    import re as _re

    full_response = ""

    # Phase 1: 收集 LLM 完整回复（不直接流式展示，以便过滤代码块）
    for sse_chunk in generate_stream_response(messages, llm_cfg, max_tokens, include_done=False):
        if sse_chunk.startswith('data: ') and sse_chunk != 'data: [DONE]\n\n':
            try:
                chunk_data = json.loads(sse_chunk[6:].strip())
                if 'content' in chunk_data:
                    full_response += chunk_data['content']
            except (json.JSONDecodeError, KeyError):
                pass

    # 将代码块替换为简短摘要，再展示给用户
    def _summarize_code_block(match: _re.Match) -> str:
        code = match.group(1).strip()
        line_count = code.count('\n') + 1
        first_line = code.split('\n')[0] if code else ''
        desc = ""
        if first_line.lstrip().startswith('#'):
            desc = first_line.lstrip('#').strip()
            return f"\n\n> 📝 **脚本**（{line_count} 行）：{desc}\n\n"
        return f"\n\n> 📝 **已生成处理脚本**（{line_count} 行），正在执行...\n\n"

    display_response = _re.sub(
        r'```python\s*\n(.*?)\n\s*```',
        _summarize_code_block,
        full_response,
        flags=_re.DOTALL
    )

    yield f"data: {json.dumps({'content': display_response})}\n\n"

    # Phase 2: 提取并执行代码块（带自动纠错重试）
    MAX_RETRIES = 3
    code_blocks = extract_python_blocks(full_response)
    if code_blocks:
        logger.info(f"从LLM回复中提取到 {len(code_blocks)} 个Python代码块，开始执行...")
        retry_history = messages + [{"role": "assistant", "content": full_response}]

        for i, code in enumerate(code_blocks):
            status = f"\n\n---\n\n**执行脚本 {i+1}/{len(code_blocks)}...**\n\n"
            yield f"data: {json.dumps({'content': status})}\n\n"

            result = execute_code(code, output_dir=output_dir, upload_dir=upload_dir)

            # 自动纠错：出错或有警告时，反馈给 LLM 自查修复
            retry_count = 0
            while (not result['success'] or result['stderr']) and retry_count < MAX_RETRIES:
                error_info = result['stderr'] or result['stdout'] or f"返回码: {result['returncode']}"
                issue_type = "警告" if result['success'] else "错误"
                logger.info(f"脚本执行出现{issue_type}，第 {retry_count + 1} 次自动修复...")

                retry_status = (
                    f"⚠️ 脚本执行出现{issue_type}，正在自动分析修复"
                    f"（第 {retry_count + 1}/{MAX_RETRIES} 次）...\n\n"
                )
                yield f"data: {json.dumps({'content': retry_status})}\n\n"

                retry_msg = (
                    f"以上脚本执行时出现{issue_type}，请自查并修复：\n\n"
                    f"```\n{error_info}\n```\n\n"
                    f"请在 ```python 代码块中输出修复后的完整脚本。"
                    f"如果确认脚本没有问题不需要修改，请说明原因但不要输出代码块。"
                )
                retry_history.append({"role": "user", "content": retry_msg})

                fix_response = _call_llm_sync(retry_history, llm_cfg, max_tokens)
                fixed_blocks = extract_python_blocks(fix_response)

                if fixed_blocks:
                    retry_history.append({"role": "assistant", "content": fix_response})
                    code = fixed_blocks[0]
                    result = execute_code(code, output_dir=output_dir, upload_dir=upload_dir)
                    retry_count += 1
                else:
                    # LLM 认为不需要修改，停止重试
                    logger.info("LLM 确认脚本无需修改，停止自动修复")
                    break

            # 输出最终结果
            output_parts = []
            if retry_count > 0:
                if result['success'] and not result['stderr']:
                    output_parts.append(f"✅ 脚本经 {retry_count} 次自动修复后执行成功")
                else:
                    output_parts.append(f"⚠️ 脚本经 {retry_count} 次自动修复后结果如下")
            if result['stdout']:
                output_parts.append(f"**输出:**\n```\n{result['stdout']}\n```")
            if result['stderr']:
                output_parts.append(f"**错误信息:**\n```\n{result['stderr']}\n```")
            if result['new_files']:
                file_links = "\n".join(
                    f"- [{f}](/download/output/{f})"
                    for f in result['new_files']
                )
                output_parts.append(f"**生成的文件:**\n{file_links}")
            if not result['success'] and not result['stderr'] and not result['stdout']:
                output_parts.append(f"**脚本执行失败** (返回码: {result['returncode']})")

            output_text = "\n\n".join(output_parts) + "\n\n"
            yield f"data: {json.dumps({'content': output_text})}\n\n"

    yield "data: [DONE]\n\n"
