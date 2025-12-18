#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install python-pptx
"""
import logging.config

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

# 配置日志
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

def create_ppt(output_path: str):
    """创建新PPT"""
    prs = Presentation()
    prs.save(output_path)

def open_ppt(file_path: str) -> Presentation:
    """打开现有PPT"""
    return Presentation(file_path)


def add_slide(prs, layout_name='标题和内容'):
    """添加指定布局的幻灯片"""
    layouts = {
        '标题': 0,
        '标题和内容': 1,
        '节标题': 2,
        '两栏内容': 3
    }
    return prs.slides.add_slide(prs.slide_layouts[layouts[layout_name]])


def add_title(slide, text: str, font_size=32):
    """添加/修改标题"""
    title = slide.shapes.title
    title.text = text
    title.text_frame.paragraphs[0].font.size = Pt(font_size)

def add_textbox(slide, text: str, left, top, width, height):
    """添加文本框"""
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.text = text
    return tf

def add_image(slide, image_path, left, top, width=None, height=None):
    """添加图片"""
    if not width: width = Inches(4)
    if not height: height = Inches(3)
    slide.shapes.add_picture(image_path, Inches(left), Inches(top), width, height)


def set_text_format(text_frame, font_name='微软雅黑', size=12,
                   bold=False, color=RGBColor(0,0,0), alignment='left'):
    """设置文本格式"""
    align_map = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}
    for paragraph in text_frame.paragraphs:
        paragraph.alignment = align_map.get(alignment, PP_ALIGN.LEFT)
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color

def extract_text(ppt_path: str) -> list:
    """提取PPT所有文本"""
    prs = Presentation(ppt_path)
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                texts.append(shape.text.strip())
    return [t for t in texts if t]


if __name__ == '__main__':
    my_template_file = '/home/rd/doc/文档生成/pptx/template.pptx'
    my_pic_file = "/home/rd/doc/文档生成/pptx/1.png"
    output_file = "/home/rd/doc/文档生成/pptx/output_report.pptx"
    # 加载模板
    logger.info(f"start gen_pptx from template {my_template_file}")
    prs = Presentation(my_template_file)
    # 创建新PPT
    # prs = Presentation()
    slide = add_slide(prs, '标题和内容')
    # 添加标题
    add_title(slide, "新添加的项目报告", font_size=36)
    # 添加内容
    content = add_textbox(slide, "核心数据:\n• 增长25%\n• 用户超百万",
        left=1, top=2, width=6, height=3)
    set_text_format(content, size=18, color=RGBColor(59, 89, 152))
    # 添加图片
    add_image(slide, my_pic_file, left=7, top=2, width=Inches(4))
    logger.info(f"output_file {output_file}")
    prs.save(output_file)