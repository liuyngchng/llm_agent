#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
按照 PPT 模板格式化用户的 PPT 文件
"""
from pptx import Presentation
import json


class TemplateExtractor:
    def __init__(self):
        self.template_data = {}

    def extract_complete_template(self, template_path):
        """完整提取模板所有样式信息"""
        template = Presentation(template_path)

        return {
            'slide_masters': self._extract_slide_masters(template),
            'slide_layouts': self._extract_slide_layouts(template),
            'color_scheme': self._extract_color_scheme(template),
            'font_themes': self._extract_font_themes(template),
            'background_styles': self._extract_background_styles(template)
        }

    def _extract_slide_masters(self, template):
        """提取所有幻灯片母版"""
        masters = []
        for master in template.slide_masters:
            master_info = {
                'name': master.name,
                'background': self._get_background_info(master),
                'shapes': self._extract_master_shapes(master),
                'placeholders': self._analyze_placeholders(master)
            }
            masters.append(master_info)
        return masters

    def _extract_slide_layouts(self, template):
        """提取所有版式样式"""
        layouts = []
        for master in template.slide_masters:
            for layout in master.slide_layouts:
                layout_info = {
                    'name': layout.name,
                    'layout_type': self._classify_layout_type(layout),
                    'placeholders': self._analyze_layout_placeholders(layout),
                    'content_areas': self._identify_content_areas(layout)
                }
                layouts.append(layout_info)
        return layouts

    def _analyze_placeholders(self, master):
        """分析母版中的占位符"""
        placeholders = {}
        for shape in master.shapes:
            if shape.is_placeholder:
                ph = shape.placeholder_format
                placeholders[ph.type] = {
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height,
                    'font': self._extract_shape_font(shape),
                    'alignment': self._get_text_alignment(shape)
                }
        return placeholders