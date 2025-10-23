#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

class StyleApplicator:
    def apply_template_styles(self, source_slide, target_slide, template_styles):
        """应用模板样式到目标幻灯片"""
        # 1. 应用背景
        self._apply_background_style(source_slide, target_slide, template_styles)

        # 2. 重新排列内容到匹配的占位符
        self._redistribute_content(source_slide, target_slide, template_styles)

        # 3. 应用字体和颜色样式
        self._apply_text_styles(target_slide, template_styles)

        # 4. 调整元素样式
        self._adjust_element_styles(target_slide, template_styles)

    def _redistribute_content(self, source_slide, target_slide, template_styles):
        """重新分配内容到合适的占位符"""
        source_elements = self._extract_all_elements(source_slide)
        target_placeholders = self._get_available_placeholders(target_slide)

        # 智能匹配元素到占位符
        element_mapping = self._match_elements_to_placeholders(
            source_elements, target_placeholders)

        # 转移内容
        for element, placeholder in element_mapping.items():
            self._transfer_element_content(element, placeholder)

    def _apply_text_styles(self, slide, template_styles):
        """应用文本样式"""
        for shape in slide.shapes:
            if hasattr(shape, 'text_frame'):
                for paragraph in shape.text_frame.paragraphs:
                    self._apply_paragraph_style(paragraph, template_styles)

    def _apply_paragraph_style(self, paragraph, template_styles):
        """应用段落样式"""
        font = paragraph.font
        template_font = template_styles['font_themes'].get(paragraph.level, {})

        if template_font.get('name'):
            font.name = template_font['name']
        if template_font.get('size'):
            font.size = template_font['size']
        if template_font.get('color'):
            font.color.rgb = template_font['color']

    def _apply_background_style(self, source_slide, target_slide, template_styles):
        """应用背景样式 - 基础实现"""
        # 这里可以复制背景样式，但需要复杂的背景处理逻辑
        pass

    def _extract_all_elements(self, slide):
        """提取所有元素 - 基础实现"""
        elements = []
        for shape in slide.shapes:
            element_info = {
                'shape': shape,
                'type': self._classify_element_type(shape),
                'text': shape.text if hasattr(shape, 'text') else None
            }
            elements.append(element_info)
        return elements

    @staticmethod
    def _classify_element_type(shape):
        """分类元素类型"""
        if hasattr(shape, 'text_frame') and shape.text_frame.text:
            return 'text'
        elif hasattr(shape, 'image'):
            return 'image'
        elif hasattr(shape, 'chart'):
            return 'chart'
        else:
            return 'shape'

    @staticmethod
    def _get_available_placeholders(slide):
        """获取可用占位符"""
        placeholders = []
        for shape in slide.shapes:
            if shape.is_placeholder:
                placeholders.append(shape)
        return placeholders

    @staticmethod
    def _match_elements_to_placeholders(elements, placeholders):
        """匹配元素到占位符 - 简化实现"""
        mapping = {}
        # 简单的一对一匹配
        for i, element in enumerate(elements):
            if i < len(placeholders):
                mapping[element] = placeholders[i]
        return mapping

    @staticmethod
    def _transfer_element_content(element, placeholder):
        """转移元素内容 - 基础实现"""
        try:
            if element['type'] == 'text' and hasattr(placeholder, 'text_frame'):
                # 转移文本内容
                placeholder.text_frame.text = element['text']
        except Exception as e:
            print(f"转移内容时出错: {e}")

    def _adjust_element_styles(self, slide, template_styles):
        """调整元素样式"""
        # 这里可以实现更复杂的样式调整逻辑
        pass