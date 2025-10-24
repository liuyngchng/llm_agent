#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
定义字体、颜色、布局等校验规则。
实现具体的校验逻辑（如字体合规、颜色合规、布局合规）
"""
class FormattingRules:
    def __init__(self):
        self.rules = self._load_default_rules()

    def _load_default_rules(self):
        return {
            'font_mapping': {
                'source_fonts': ['Arial', 'Calibri'],
                'target_font': 'Microsoft YaHei'
            },
            'color_mapping': {
                'source_colors': ['FF0000', '00FF00'],  # RGB values
                'target_colors': ['E60012', '00A650']  # Brand colors
            },
            'layout_preferences': {
                'prefer_title_slides': True,
                'max_text_length': 500,
                'image_placement': 'balanced'
            },
            'content_rules': {
                'title_case': True,
                'bullet_consistency': True,
                'image_scaling': 'fit_proportional'
            }
        }

    def validate_slide_compliance(self, slide, template_styles):
        """验证幻灯片是否符合规范"""
        violations = []

        # 检查字体合规
        font_violations = self._check_font_compliance(slide, template_styles)
        violations.extend(font_violations)

        # 检查颜色合规
        color_violations = self._check_color_compliance(slide, template_styles)
        violations.extend(color_violations)

        # 检查布局合规
        layout_violations = self._check_layout_compliance(slide, template_styles)
        violations.extend(layout_violations)

        return violations

    def _check_font_compliance(self, slide, template_styles):
        """检查字体合规"""
        violations = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    font = run.font
                    if font.name not in template_styles.get('font_mapping', {}).get('target_fonts', []):
                        violations.append(f"字体 '{font.name}' 不符合模板要求")
                    if font.size and font.size.pt != template_styles.get('font_size', 12):
                        violations.append(f"字体大小 {font.size.pt}pt 不符合模板要求")
        return violations

    def _check_color_compliance(self, slide, template_styles):
        """检查颜色合规"""
        violations = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    font = run.font
                    if font.color.rgb != template_styles.get('color_mapping', {}).get('target_colors', []):
                        violations.append(f"颜色值 {font.color.rgb} 不符合模板要求")
        return violations

    def _check_layout_compliance(self, slide, template_styles):
        """检查布局合规"""
        violations = []
        slide_layout = slide.slide_layout
        if slide_layout.name not in [layout.name for layout in template_styles.get('slide_layouts', [])]:
            violations.append(f"版式 '{slide_layout.name}' 不符合模板要求")
        return violations