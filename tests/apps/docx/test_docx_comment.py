import logging.config
import os
import zipfile
from xml.etree import ElementTree as ET  # 添加这行导入语
from docx import Document

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO,format= LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    规范化文本，使其在不同解析方式下保持一致
    """
    if not text:
        return ""

    # 1. 替换所有连续空白字符为单个空格
    import re
    text = re.sub(r'\s+', ' ', text)

    # 2. 去除首尾空格
    text = text.strip()

    # 3. 处理全角/半角空格（可选）
    text = text.replace('　', ' ')  # 全角空格转半角

    # 4. 统一标点符号周围的空格（可选）
    text = re.sub(r'\s*([，。！？；：])\s*', r'\1', text)

    return text


def get_comments_by_content(target_doc: str) -> dict:
    """
    通过段落内容匹配批注，返回格式: {paragraph_text: comment_text}
    """
    if not os.path.exists(target_doc):
        logger.error(f"文件不存在: {target_doc}")
        return {}

    comments_dict = {}
    try:
        with zipfile.ZipFile(target_doc) as z:
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

            # 建立段落内容到批注的映射
            para_to_comments = {}

            # 解析文档结构
            with z.open('word/document.xml') as f:
                doc_xml = ET.fromstring(f.read())
                paragraphs = doc_xml.findall('.//w:p', namespaces)

                for paragraph in paragraphs:
                    # 提取段落文本内容
                    para_text = ' '.join(
                        t.text.strip()
                        for t in paragraph.findall('.//w:t', namespaces)
                        if t.text and t.text.strip()
                    )

                    if not para_text:  # 跳过空段落
                        continue

                    # 规范化文本
                    normalized_text = normalize_text(para_text)

                    # 查找当前段落中的批注引用
                    comment_refs = paragraph.findall('.//w:commentReference', namespaces)
                    comment_ids = []
                    for ref in comment_refs:
                        ref_id = ref.get(f'{{{namespaces["w"]}}}id')
                        if ref_id:
                            comment_ids.append(ref_id)

                    if comment_ids:
                        para_to_comments[normalized_text] = comment_ids
                        logger.debug(f"XML段落内容(规范化后): '{normalized_text}'")

            # 解析批注内容
            with z.open('word/comments.xml') as f:
                comments_xml = ET.fromstring(f.read())
                comment_texts = {}

                for comment in comments_xml.findall('.//w:comment', namespaces):
                    comment_id = comment.get(f'{{{namespaces["w"]}}}id')
                    if not comment_id:
                        continue

                    # 提取批注文本
                    comment_text_parts = []
                    for t in comment.findall('.//w:t', namespaces):
                        if t.text:
                            comment_text_parts.append(t.text.strip())

                    comment_texts[comment_id] = ' '.join(comment_text_parts).strip()

            # 建立段落内容到合并批注的映射
            for para_text, comment_ids in para_to_comments.items():
                merged_comment_text = ' '.join(
                    comment_texts[cid] for cid in comment_ids if cid in comment_texts
                ).strip()
                if merged_comment_text:
                    comments_dict[para_text] = merged_comment_text

    except Exception as e:
        logger.error(f"解析文档时出错: {str(e)}", exc_info=True)

    logger.info(f"提取到批注信息: {comments_dict}")
    return comments_dict


def apply_comments_to_document(doc_path: str, output_path: str):
    """
    根据批注修改文档
    """
    # 获取基于内容的批注映射
    comments_by_content = get_comments_by_content(doc_path)

    if not comments_by_content:
        logger.info("没有找到需要处理的批注")
        return

    doc = Document(doc_path)

    for paragraph in doc.paragraphs:
        para_text = paragraph.text.strip() if paragraph.text else ""
        if para_text:
            # 对 python-docx 读取的文本也进行规范化
            normalized_para_text = normalize_text(para_text)

            if normalized_para_text in comments_by_content:
                comment = comments_by_content[normalized_para_text]
                logger.info(f"找到需要修改的段落: '{normalized_para_text}'")
                logger.info(f"对应批注: {comment}")

                # 在这里根据批注内容修改段落
                # 例如：paragraph.text = modified_text
                # 或者调用你的修改逻辑

    # 保存修改后的文档
    doc.save(output_path)
    logger.info(f"文档已保存: {output_path}")


def test_get_comment():
    my_file = "/home/rd/Desktop/1.docx"
    apply_comments_to_document(my_file, 'test.docx')
if __name__ == "__main__":
    test_get_comment()