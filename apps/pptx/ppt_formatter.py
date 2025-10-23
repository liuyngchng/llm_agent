#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
根据模板样式格式化源 PPT。
应用字体、颜色、布局等规则
"""

from pptx import Presentation
import json

from apps.pptx.content_analyzer import ContentAnalyzer
from apps.pptx.layout_matcher import LayoutMatcher
from apps.pptx.style_applicator import StyleApplicator


class PPTFormatter:
    def __init__(self):
        self.template_styles = {}
        self.content_analyzer = ContentAnalyzer()
        self.layout_matcher = LayoutMatcher({})
        self.style_applicator = StyleApplicator()

    def extract_template_styles(self, template_path):
        """从模板PPT中提取样式信息"""
        template = Presentation(template_path)
        styles = {
            'slide_layouts': [],
            'color_scheme': {},
            'font_styles': {},
            'master_layout': {}
        }

        # 提取母版样式
        for slide_master in template.slide_masters:
            master_info = {
                'background': self._extract_background(slide_master),
                'placeholders': self._extract_placeholders(slide_master)
            }
            styles['master_layout'] = master_info

        # 提取版式样式
        for layout in template.slide_masters[0].slide_layouts:
            layout_info = self._analyze_layout(layout)
            styles['slide_layouts'].append(layout_info)

        return styles


    def _extract_placeholders(self, slide_master):
        """提取占位符信息"""
        placeholders = {}
        for shape in slide_master.shapes:
            if shape.is_placeholder:
                ph = shape.placeholder_format
                placeholders[ph.type] = {
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height,
                    'name': shape.name
                }
        return placeholders

    def _analyze_layout(self, layout):
        """分析版式"""
        placeholders = []
        for shape in layout.shapes:
            if shape.is_placeholder:
                ph = shape.placeholder_format
                placeholders.append({
                    'type': ph.type,
                    'name': shape.name,
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height
                })

        return {
            'name': layout.name,
            'placeholders': placeholders,
            'layout_type': self._classify_layout_type(layout)
        }

    def _extract_background(self, slide_master):
        """提取背景样式"""
        try:
            background = slide_master.background
            fill = background.fill
            return {
                'fill_type': getattr(fill, 'type', None),
                'color': str(fill.fore_color.rgb) if hasattr(fill, 'fore_color') and fill.fore_color.rgb else None,
                'gradient': {
                    'type': fill.gradient_type if hasattr(fill, 'gradient_type') else None,
                    'stops': [{
                        'position': stop.position,
                        'color': str(stop.color.rgb)
                    } for stop in fill.gradient_stops] if hasattr(fill, 'gradient_stops') else []
                } if hasattr(fill, 'type') and fill.type == 'GRADIENT' else None
            }
        except Exception as e:
            print(f"提取背景样式时出错: {e}")
            return {}

    def _classify_layout_type(self, layout):
        """分类版式类型"""
        placeholder_types = [shape.placeholder_format.type for shape in layout.shapes if shape.is_placeholder]

        if 1 in placeholder_types:  # Title
            if len(placeholder_types) == 1:
                return 'title'
            elif len(placeholder_types) == 2 and 2 in placeholder_types:  # Body
                return 'content'
            elif 7 in placeholder_types:  # Chart
                return 'chart'
            elif 8 in placeholder_types:  # Picture
                return 'picture'
            elif 12 in placeholder_types:  # Date
                return 'date'
            elif 14 in placeholder_types:  # Footer
                return 'footer'
        elif 2 in placeholder_types:  # Body
            if 3 in placeholder_types:  # Subtitle
                return 'two_content'
            elif 4 in placeholder_types:  # Notes
                return 'content_with_notes'
        elif 7 in placeholder_types:  # Chart
            return 'chart'
        elif 8 in placeholder_types:  # Picture
            return 'picture'
        elif 12 in placeholder_types:  # Date
            return 'date'
        elif 14 in placeholder_types:  # Footer
            return 'footer'
        else:
            return 'mixed'

    def _find_best_layout(self, source_slide, template_styles):
        """查找最佳版式"""
        slide_analysis = self.content_analyzer.analyze_slide_content(source_slide)
        self.layout_matcher.template_styles = template_styles
        best_layout = self.layout_matcher.find_optimal_layout(slide_analysis)
        
        if not best_layout:
            print("警告：未找到最佳版式，使用默认版式")
            return template_styles['slide_layouts'][0]  # 返回第一个版式作为默认
        
        return best_layout

    def _transfer_content(self, source_slide, new_slide, template_styles):
        """转移内容"""
        for source_shape in source_slide.shapes:
            if source_shape.is_placeholder:
                # 跳过占位符，由版式处理
                continue
            
            # 复制形状到新幻灯片
            new_shape = new_slide.shapes.add_shape(
                source_shape.auto_shape_type,
                source_shape.left,
                source_shape.top,
                source_shape.width,
                source_shape.height
            )
            
            # 复制文本内容
            if hasattr(source_shape, 'text_frame') and source_shape.text_frame.text:
                new_shape.text_frame.text = source_shape.text_frame.text
            
            # 复制图片
            if hasattr(source_shape, 'image') and source_shape.image:
                new_shape.image = source_shape.image
            
            # 应用模板样式
            self.style_applicator.apply_template_styles(source_shape, new_shape, template_styles)

    def analyze_ppt_structure(self, source_path):
        """分析PPT结构"""
        source_ppt = Presentation(source_path)
        analysis = []
        for slide in source_ppt.slides:
            slide_analysis = self.content_analyzer.analyze_slide_content(slide)
            slide_analysis['slide_id'] = slide.slide_id
            slide_analysis['slide_number'] = len(analysis) + 1
            analysis.append(slide_analysis)
        
        return {
            'slides': analysis,
            'total_slides': len(analysis),
            'title': source_ppt.core_properties.title or "Untitled"
        }

    def _check_slide_compliance(self, slide_analysis):
        """检查幻灯片合规性"""
        violations = []
        
        # 检查字体合规性
        font_violations = self._check_font_compliance(slide_analysis)
        violations.extend(font_violations)
        
        # 检查颜色合规性
        color_violations = self._check_color_compliance(slide_analysis)
        violations.extend(color_violations)
        
        # 检查布局合规性
        layout_violations = self._check_layout_compliance(slide_analysis)
        violations.extend(layout_violations)
        
        return violations

    def _check_font_compliance(self, slide_analysis):
        """检查字体合规性"""
        violations = []
        for element in slide_analysis['elements']['text_boxes']:
            font_props = element['text_properties']
            if font_props:
                for style in font_props['font_styles']:
                    if style['size'] != self.template_styles.get('font_size', 12):
                        violations.append(f"字体大小 {style['size']}pt 不符合模板要求")
                    if style['bold'] and not self.template_styles.get('allow_bold', True):
                        violations.append(f"加粗字体不符合模板要求")
        return violations

    def _check_color_compliance(self, slide_analysis):
        """检查颜色合规性"""
        violations = []
        for element in slide_analysis['elements']['text_boxes']:
            font_props = element['text_properties']
            if font_props:
                for style in font_props['font_styles']:
                    if style['color'] not in self.template_styles.get('allowed_colors', []):
                        violations.append(f"颜色 {style['color']} 不符合模板要求")
        return violations

    def _check_layout_compliance(self, slide_analysis):
        """检查布局合规性"""
        violations = []
        layout_type = slide_analysis['layout_pattern']
        if layout_type not in self.template_styles.get('allowed_layouts', []):
            violations.append(f"版式类型 {layout_type} 不符合模板要求")
        return violations

    def generate_compliance_report(self, formatted_ppt):
        """生成合规报告"""
        violations = []
        for slide in formatted_ppt.slides:
            slide_analysis = self.content_analyzer.analyze_slide_content(slide)
            slide_violations = self._check_slide_compliance(slide_analysis)
            if slide_violations:
                violations.append({
                    'slide_id': slide.slide_id,
                    'slide_number': formatted_ppt.slides.index(slide) + 1,
                    'violations': slide_violations
                })
        
        return {
            'status': 'completed',
            'violations': violations,
            'total_violations': len(violations),
            'compliance_score': 100 - (len(violations) * 10) if violations else 100
        }

    def format_ppt(self, source_path, template_styles):
        """根据模板样式格式化源PPT"""
        source_ppt = Presentation(source_path)
        formatted_ppt = Presentation()  # 新建基于模板的PPT

        for slide in source_ppt.slides:
            self._format_slide(slide, formatted_ppt, template_styles)

        return formatted_ppt

    def _format_slide(self, source_slide, target_ppt, template_styles):
        """格式化单个幻灯片"""
        # 智能匹配最合适的版式
        best_layout = self._find_best_layout(source_slide, template_styles)
        new_slide = target_ppt.slides.add_slide(best_layout)

        # 转移内容并应用样式
        self._transfer_content(source_slide, new_slide, template_styles)