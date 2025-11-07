#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
将模板样式应用到 PPT 中的具体元素（如文本、形状）。
确保样式一致性
"""
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
import copy
import os


class StyleApplicator:
    def __init__(self):
        self.content_analyzer = ContentAnalyzer()  # 假设有这个类

    def apply_template_styles(self, source_slide, target_slide, template_styles):
        """应用模板样式到目标幻灯片"""
        try:
            print(f"开始应用样式到幻灯片...")

            # 1. 应用背景
            self._apply_background_style(source_slide, target_slide, template_styles)

            # 2. 清除目标幻灯片上的默认占位符内容
            self._clear_placeholder_content(target_slide)

            # 3. 重新排列内容到匹配的占位符
            self._redistribute_content(source_slide, target_slide, template_styles)

            # 4. 应用字体和颜色样式
            self._apply_text_styles(target_slide, template_styles)

            # 5. 调整元素样式
            self._adjust_element_styles(target_slide, template_styles)

            print("样式应用完成")

        except Exception as e:
            print(f"应用模板样式时出错: {e}")
            raise

    def _apply_background_style(self, source_slide, target_slide, template_styles):
        """应用背景样式"""
        try:
            # 获取模板背景信息
            background_info = template_styles.get('background_styles', {})
            if not background_info:
                return

            # 这里简化实现：应用纯色背景
            # 实际应用中需要处理渐变、图片背景等复杂情况
            master_bg = background_info.get('master', {})
            if master_bg.get('color'):
                try:
                    # 设置背景颜色
                    background = target_slide.background
                    fill = background.fill
                    fill.solid()
                    fill.fore_color.rgb = RGBColor.from_string(master_bg['color'])
                except Exception as e:
                    print(f"设置背景颜色时出错: {e}")

        except Exception as e:
            print(f"应用背景样式时出错: {e}")

    def _clear_placeholder_content(self, slide):
        """清除占位符的默认内容"""
        for shape in slide.shapes:
            if shape.is_placeholder and hasattr(shape, 'text_frame'):
                shape.text_frame.text = ""

    def _redistribute_content(self, source_slide, target_slide, template_styles):
        """重新分配内容到合适的占位符"""
        try:
            # 分析源幻灯片内容
            source_elements = self._extract_all_elements(source_slide)

            # 获取目标幻灯片的占位符
            target_placeholders = self._get_available_placeholders(target_slide)

            if not target_placeholders:
                print("目标幻灯片没有可用的占位符")
                return

            # 智能匹配元素到占位符
            element_mapping = self._match_elements_to_placeholders(
                source_elements, target_placeholders, template_styles)

            # 转移内容
            for element, placeholder_info in element_mapping.items():
                self._transfer_element_content(element, placeholder_info['placeholder'])

        except Exception as e:
            print(f"重新分配内容时出错: {e}")

    def _extract_all_elements(self, slide):
        """提取所有元素"""
        elements = []
        for shape in slide.shapes:
            element_type = self._classify_element_type(shape)
            element_info = {
                'shape': shape,
                'type': element_type,
                'text': self._extract_shape_text(shape),
                'position': {
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height
                },
                'placeholder_type': shape.placeholder_format.type if shape.is_placeholder else None,
                'has_image': hasattr(shape, 'image'),
                'has_chart': hasattr(shape, 'chart'),
                'has_table': hasattr(shape, 'table')
            }
            elements.append(element_info)
        return elements

    def _classify_element_type(self, shape):
        """分类元素类型"""
        if shape.is_placeholder:
            ph_type = shape.placeholder_format.type
            if ph_type == 1:  # Title
                return 'title'
            elif ph_type == 2:  # Body
                return 'body'
            else:
                return f'placeholder_{ph_type}'
        elif hasattr(shape, 'text_frame') and shape.text_frame.text.strip():
            return 'text_box'
        elif hasattr(shape, 'image'):
            return 'image'
        elif hasattr(shape, 'chart'):
            return 'chart'
        elif hasattr(shape, 'table'):
            return 'table'
        else:
            return 'shape'

    def _extract_shape_text(self, shape):
        """提取形状文本"""
        if hasattr(shape, 'text_frame') and shape.text_frame.text:
            text_content = {
                'raw_text': shape.text_frame.text,
                'paragraphs': []
            }

            for paragraph in shape.text_frame.paragraphs:
                para_info = {
                    'text': paragraph.text,
                    'level': paragraph.level,
                    'alignment': str(paragraph.alignment) if paragraph.alignment else None,
                    'font': self._extract_font_info(paragraph.font)
                }
                text_content['paragraphs'].append(para_info)

            return text_content
        return None

    def _extract_font_info(self, font):
        """提取字体信息"""
        return {
            'name': font.name,
            'size': font.size,
            'bold': font.bold,
            'italic': font.italic,
            'color': str(font.color.rgb) if font.color and font.color.rgb else None,
            'underline': font.underline
        }

    def _get_available_placeholders(self, slide):
        """获取可用占位符"""
        placeholders = []
        for shape in slide.shapes:
            if shape.is_placeholder:
                placeholder_info = {
                    'shape': shape,
                    'type': shape.placeholder_format.type,
                    'name': shape.name,
                    'position': {
                        'left': shape.left,
                        'top': shape.top,
                        'width': shape.width,
                        'height': shape.height
                    }
                }
                placeholders.append(placeholder_info)
        return placeholders

    def _match_elements_to_placeholders(self, elements, placeholders, template_styles):
        """智能匹配元素到占位符"""
        mapping = {}
        used_placeholders = set()

        # 首先匹配标题
        title_elements = [e for e in elements if e['type'] == 'title']
        title_placeholders = [p for p in placeholders if p['type'] == 1]  # Title placeholder

        if title_elements and title_placeholders:
            mapping[title_elements[0]] = {'placeholder': title_placeholders[0]['shape']}
            used_placeholders.add(title_placeholders[0]['shape'])

        # 匹配正文内容
        body_elements = [e for e in elements if e['type'] in ['body', 'text_box']]
        body_placeholders = [p for p in placeholders if
                             p['type'] == 2 and p['shape'] not in used_placeholders]  # Body placeholder

        for i, element in enumerate(body_elements):
            if i < len(body_placeholders):
                mapping[element] = {'placeholder': body_placeholders[i]['shape']}
                used_placeholders.add(body_placeholders[i]['shape'])

        # 匹配其他元素到剩余占位符
        other_elements = [e for e in elements if e not in mapping]
        available_placeholders = [p for p in placeholders if p['shape'] not in used_placeholders]

        for i, element in enumerate(other_elements):
            if i < len(available_placeholders):
                mapping[element] = {'placeholder': available_placeholders[i]['shape']}

        return mapping

    def _transfer_element_content(self, element, placeholder):
        """转移元素内容"""
        try:
            if element['type'] in ['title', 'body', 'text_box'] and element['text']:
                # 转移文本内容
                self._transfer_text_content(element, placeholder)

            elif element['type'] == 'image' and hasattr(element['shape'], 'image'):
                # 转移图片（这里需要复杂的图片处理逻辑）
                print(f"需要处理图片元素: {element['shape'].name}")

            elif element['type'] == 'chart' and hasattr(element['shape'], 'chart'):
                # 转移图表（这里需要复杂的图表处理逻辑）
                print(f"需要处理图表元素: {element['shape'].name}")

        except Exception as e:
            print(f"转移元素内容时出错: {e}")

    def _transfer_text_content(self, element, placeholder):
        """转移文本内容"""
        try:
            if not hasattr(placeholder, 'text_frame'):
                return

            # 清除占位符的默认文本
            placeholder.text_frame.text = ""

            # 转移文本内容
            text_content = element['text']
            if text_content and 'raw_text' in text_content:
                placeholder.text_frame.text = text_content['raw_text']

                # 尝试应用段落格式
                self._apply_paragraph_formatting(placeholder, text_content)

        except Exception as e:
            print(f"转移文本内容时出错: {e}")

    def _apply_paragraph_formatting(self, placeholder, text_content):
        """应用段落格式"""
        try:
            if 'paragraphs' not in text_content:
                return

            # 确保有足够的段落
            while len(placeholder.text_frame.paragraphs) < len(text_content['paragraphs']):
                placeholder.text_frame.add_paragraph()

            # 应用段落格式
            for i, para_info in enumerate(text_content['paragraphs']):
                if i < len(placeholder.text_frame.paragraphs):
                    paragraph = placeholder.text_frame.paragraphs[i]
                    if para_info.get('alignment'):
                        # 这里需要将字符串对齐方式转换为枚举值
                        pass
        except Exception as e:
            print(f"应用段落格式时出错: {e}")

    def _apply_text_styles(self, slide, template_styles):
        """应用文本样式"""
        try:
            font_themes = template_styles.get('font_themes', {})
            if not font_themes:
                return

            for shape in slide.shapes:
                if hasattr(shape, 'text_frame'):
                    for paragraph in shape.text_frame.paragraphs:
                        self._apply_paragraph_style(paragraph, template_styles)

        except Exception as e:
            print(f"应用文本样式时出错: {e}")

    def _apply_paragraph_style(self, paragraph, template_styles):
        """应用段落样式"""
        try:
            font = paragraph.font
            font_themes = template_styles.get('font_themes', {})

            # 使用主要字体主题
            major_font = font_themes.get('major', {})
            if major_font.get('latin'):
                font.name = major_font['latin']

            # 应用默认字体大小
            if paragraph.level == 0:  # 标题级别
                font.size = None  # 让PPT使用默认大小
            elif paragraph.level == 1:  # 一级正文
                font.size = None

        except Exception as e:
            print(f"应用段落样式时出错: {e}")

    def _adjust_element_styles(self, slide, template_styles):
        """调整元素样式"""
        try:
            color_scheme = template_styles.get('color_scheme', {})

            for shape in slide.shapes:
                # 调整形状填充颜色
                self._adjust_shape_fill(shape, color_scheme)

                # 调整形状线条颜色
                self._adjust_shape_line(shape, color_scheme)

        except Exception as e:
            print(f"调整元素样式时出错: {e}")

    def _adjust_shape_fill(self, shape, color_scheme):
        """调整形状填充颜色"""
        try:
            if hasattr(shape, 'fill') and color_scheme:
                # 这里可以实现根据颜色方案调整填充颜色
                pass
        except:
            pass

    def _adjust_shape_line(self, shape, color_scheme):
        """调整形状线条颜色"""
        try:
            if hasattr(shape, 'line') and color_scheme:
                # 这里可以实现根据颜色方案调整线条颜色
                pass
        except:
            pass


# 假设的 ContentAnalyzer 类（需要你提供或实现）
class ContentAnalyzer:
    def analyze_slide_content(self, slide):
        """分析幻灯片内容"""
        return {
            'content_type': 'mixed',
            'elements': []
        }