#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
按照 PPT 模板格式化用户的 PPT 文件
"""
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
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

    @staticmethod
    def _get_background_info(slide_master):
        """获取背景信息"""
        try:
            background = slide_master.background
            fill = background.fill

            bg_info = {
                'type': getattr(fill, 'type', None),
                'transparency': getattr(fill, 'transparency', None)
            }

            # 处理纯色背景
            if hasattr(fill, 'fore_color') and fill.fore_color.rgb:
                bg_info['color'] = str(fill.fore_color.rgb)
            elif hasattr(fill, 'back_color') and fill.back_color.rgb:
                bg_info['color'] = str(fill.back_color.rgb)

            # 处理渐变背景
            if hasattr(fill, 'gradient_stops'):
                bg_info['gradient_stops'] = [
                    {
                        'position': stop.position,
                        'color': str(stop.color.rgb) if stop.color.rgb else None
                    }
                    for stop in fill.gradient_stops
                ]

            return bg_info
        except Exception as e:
            print(f"提取背景信息时出错: {e}")
            return {}

    def _extract_master_shapes(self, master):
        """提取母版形状信息"""
        shapes_info = []
        for shape in master.shapes:
            shape_info = {
                'name': shape.name,
                'type': self._get_shape_type(shape),
                'left': shape.left,
                'top': shape.top,
                'width': shape.width,
                'height': shape.height,
                'text': self._extract_shape_text(shape),
                'fill': self._extract_shape_fill(shape),
                'line': self._extract_shape_line(shape)
            }
            shapes_info.append(shape_info)
        return shapes_info

    @staticmethod
    def _get_shape_type(shape):
        """获取形状类型"""
        if shape.is_placeholder:
            return f"placeholder_{shape.placeholder_format.type}"
        elif hasattr(shape, 'shape_type'):
            return str(shape.shape_type)
        else:
            return "unknown"

    def _extract_shape_text(self, shape):
        """提取形状文本"""
        if hasattr(shape, 'text_frame') and shape.text_frame.text:
            return {
                'content': shape.text_frame.text,
                'paragraphs': [
                    {
                        'text': paragraph.text,
                        'alignment': str(paragraph.alignment) if paragraph.alignment else None,
                        'level': paragraph.level,
                        'font': self._extract_paragraph_font(paragraph)
                    }
                    for paragraph in shape.text_frame.paragraphs
                ]
            }
        return None

    @staticmethod
    def _extract_paragraph_font(paragraph):
        """提取段落字体信息"""
        font = paragraph.font
        return {
            'name': font.name,
            'size': font.size,
            'bold': font.bold,
            'italic': font.italic,
            'color': str(font.color.rgb) if font.color.rgb else None,
            'underline': font.underline
        }

    @staticmethod
    def _extract_shape_fill(shape):
        """提取形状填充信息"""
        try:
            if hasattr(shape, 'fill'):
                fill = shape.fill
                fill_info = {
                    'type': getattr(fill, 'type', None)
                }

                if hasattr(fill, 'fore_color') and fill.fore_color.rgb:
                    fill_info['fore_color'] = str(fill.fore_color.rgb)
                if hasattr(fill, 'back_color') and fill.back_color.rgb:
                    fill_info['back_color'] = str(fill.back_color.rgb)

                return fill_info
        except:
            pass
        return None

    @staticmethod
    def _extract_shape_line(shape):
        """提取形状线条信息"""
        try:
            if hasattr(shape, 'line'):
                line = shape.line
                line_info = {
                    'width': getattr(line, 'width', None),
                    'style': getattr(line, 'style', None)
                }

                if hasattr(line, 'color') and line.color.rgb:
                    line_info['color'] = str(line.color.rgb)

                return line_info
        except:
            pass
        return None

    @staticmethod
    def _extract_shape_font(shape):
        """提取形状字体信息"""
        font_info = {}
        try:
            if hasattr(shape, 'text_frame'):
                # 获取第一个段落的字体作为代表
                for paragraph in shape.text_frame.paragraphs:
                    font = paragraph.font
                    font_info = {
                        'name': font.name,
                        'size': font.size,
                        'bold': font.bold,
                        'italic': font.italic,
                        'color': str(font.color.rgb) if font.color.rgb else None
                    }
                    break  # 只取第一个段落
        except:
            pass
        return font_info

    @staticmethod
    def _get_text_alignment(shape):
        """获取文本对齐方式"""
        try:
            if hasattr(shape, 'text_frame'):
                for paragraph in shape.text_frame.paragraphs:
                    return str(paragraph.alignment) if paragraph.alignment else None
        except:
            pass
        return None

    @staticmethod
    def _classify_layout_type(layout):
        """分类版式类型"""
        placeholder_types = []
        for shape in layout.shapes:
            if shape.is_placeholder:
                placeholder_types.append(shape.placeholder_format.type)

        # 根据占位符类型判断版式类型
        if 1 in placeholder_types:  # 标题
            if len(placeholder_types) == 1:
                return 'title'
            elif 2 in placeholder_types:  # 正文
                if len(placeholder_types) == 2:
                    return 'content'
                elif len(placeholder_types) > 2:
                    return 'mixed_content'
        elif 7 in placeholder_types:  # 图表
            return 'chart'
        elif 8 in placeholder_types:  # 图片
            return 'picture'
        elif 12 in placeholder_types:  # 仅标题
            return 'title_only'

        return 'custom'


    def _analyze_layout_placeholders(self, layout):
        """分析版式占位符"""
        placeholders = []
        for shape in layout.shapes:
            if shape.is_placeholder:
                ph = shape.placeholder_format
                placeholder_info = {
                    'type': ph.type,
                    'name': shape.name,
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height,
                    'font': self._extract_shape_font(shape),
                    'alignment': self._get_text_alignment(shape)
                }
                placeholders.append(placeholder_info)
        return placeholders

    def _identify_content_areas(self, layout):
        """识别内容区域"""
        content_areas = []
        for shape in layout.shapes:
            if shape.is_placeholder:
                area_type = self._get_placeholder_content_type(shape.placeholder_format.type)
                content_areas.append({
                    'type': area_type,
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height
                })
        return content_areas

    @staticmethod
    def _get_placeholder_content_type(placeholder_type):
        """获取占位符内容类型"""
        type_mapping = {
            1: 'title',
            2: 'body',
            3: 'centered_title',
            7: 'chart',
            8: 'picture',
            12: 'title_only',
            14: 'subtitle'
        }
        return type_mapping.get(placeholder_type, 'unknown')

    @staticmethod
    def _extract_color_scheme(template):
        """提取颜色方案"""
        color_scheme = {}
        try:
            # 提取主题颜色
            for master in template.slide_masters:
                if hasattr(master, 'color_scheme'):
                    for color in master.color_scheme._colors:
                        if color and hasattr(color, 'rgb'):
                            color_scheme[color._name] = str(color.rgb)
        except Exception as e:
            print(f"提取颜色方案时出错: {e}")
        return color_scheme

    @staticmethod
    def _extract_font_themes(template):
        """提取字体主题"""
        font_themes = {}
        try:
            for master in template.slide_masters:
                if hasattr(master, 'font_scheme'):
                    font_scheme = master.font_scheme
                    if font_scheme:
                        font_themes['major'] = {
                            'latin': getattr(font_scheme.major_font, 'latin', None),
                            'ea': getattr(font_scheme.major_font, 'ea', None)
                        }
                        font_themes['minor'] = {
                            'latin': getattr(font_scheme.minor_font, 'latin', None),
                            'ea': getattr(font_scheme.minor_font, 'ea', None)
                        }
        except Exception as e:
            print(f"提取字体主题时出错: {e}")
        return font_themes

    def _extract_background_styles(self, template):
        """提取背景样式"""
        background_styles = {}
        try:
            for master in template.slide_masters:
                background_styles[master.name] = self._get_background_info(master)

                # 提取所有版式的背景
                for layout in master.slide_layouts:
                    layout_bg = self._get_layout_background(layout)
                    if layout_bg:
                        background_styles[f"{master.name}_{layout.name}"] = layout_bg

        except Exception as e:
            print(f"提取背景样式时出错: {e}")
        return background_styles

    def _get_layout_background(self, layout):
        """获取版式背景"""
        try:
            background = layout.background
            if background:
                return self._get_background_info_from_element(background)
        except:
            pass
        return None

    @staticmethod
    def _get_background_info_from_element(background):
        """从背景元素获取背景信息"""
        try:
            fill = background.fill
            bg_info = {
                'type': getattr(fill, 'type', None)
            }

            if hasattr(fill, 'fore_color') and fill.fore_color.rgb:
                bg_info['color'] = str(fill.fore_color.rgb)

            return bg_info
        except:
            return {}

    def save_template_data(self, file_path):
        """保存模板数据到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # 转换无法序列化的对象
                serializable_data = self._make_serializable(self.template_data)
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            print(f"模板数据已保存到: {file_path}")
        except Exception as e:
            print(f"保存模板数据时出错: {e}")

    def _make_serializable(self, obj):
        """使对象可序列化"""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        else:
            return str(obj)


# 使用示例
if __name__ == '__main__':
    extractor = TemplateExtractor()

    try:
        # 提取模板信息
        template_data = extractor.extract_complete_template('company_template.pptx')

        # 保存到文件
        extractor.template_data = template_data
        extractor.save_template_data('template_analysis.json')

        print("模板提取完成！")
        print(f"找到 {len(template_data['slide_masters'])} 个母版")
        print(f"找到 {len(template_data['slide_layouts'])} 个版式")

    except FileNotFoundError:
        print("模板文件未找到，请确保 'company_template.pptx' 存在")
    except Exception as e:
        print(f"处理过程中出错: {e}")