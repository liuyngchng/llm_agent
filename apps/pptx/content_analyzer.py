#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
解析 PPT 中的文本、图片、表格等内容。
提取内容类型和结构信息
"""
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor


class ContentAnalyzer:
    def analyze_slide_content(self, slide):
        """深度分析幻灯片内容结构"""
        content_analysis = {
            'content_type': self._determine_content_type(slide),
            'elements': self._catalog_slide_elements(slide),
            'layout_pattern': self._identify_layout_pattern(slide),
            'complexity_score': self._calculate_complexity(slide),
            'slide_size': self._get_slide_size(slide),
            'element_distribution': self._analyze_element_distribution(slide),
            'content_density': self._calculate_content_density(slide)
        }
        return content_analysis

    def _determine_content_type(self, slide):
        """确定内容类型"""
        elements = self._catalog_slide_elements(slide)

        # 统计各类元素数量
        image_count = len(elements['images'])
        chart_count = len(elements['charts'])
        table_count = len(elements['tables'])
        text_count = len(elements['text_boxes'])
        title_count = len(elements['titles'])
        shape_count = len(elements['shapes'])

        # 判断逻辑
        if title_count > 0 and text_count == 0 and image_count == 0:
            return 'title'
        elif image_count > 0 or chart_count > 0:
            if text_count > 0:
                return 'mixed_visual'
            else:
                return 'visual'
        elif table_count > 0:
            if text_count > 0:
                return 'mixed_data'
            else:
                return 'data'
        elif text_count > 0:
            if text_count == 1 and self._is_bullet_list(elements['text_boxes'][0]):
                return 'bullet_list'
            elif text_count >= 3:
                return 'multi_content'
            else:
                return 'content'
        elif shape_count > 0:
            return 'diagram'
        else:
            return 'blank'

    def _catalog_slide_elements(self, slide):
        """分类记录幻灯片中的所有元素"""
        elements = {
            'titles': [],
            'text_boxes': [],
            'images': [],
            'charts': [],
            'tables': [],
            'shapes': []
        }

        for shape in slide.shapes:
            element_info = self._analyze_single_element(shape)

            if element_info['type'] == 'title':
                elements['titles'].append(element_info)
            elif element_info['type'] == 'text':
                elements['text_boxes'].append(element_info)
            elif element_info['type'] == 'image':
                elements['images'].append(element_info)
            elif element_info['type'] == 'chart':
                elements['charts'].append(element_info)
            elif element_info['type'] == 'table':
                elements['tables'].append(element_info)
            else:
                elements['shapes'].append(element_info)

        return elements

    def _analyze_single_element(self, shape):
        """分析单个元素的详细属性"""
        element = {
            'name': shape.name,
            'type': self._classify_shape_type(shape),
            'position': {
                'left': shape.left,
                'top': shape.top,
                'width': shape.width,
                'height': shape.height,
                'right': shape.left + shape.width,
                'bottom': shape.top + shape.height
            },
            'area': shape.width * shape.height,
            'text_properties': self._extract_text_properties(shape),
            'visual_properties': self._extract_visual_properties(shape),
            'placeholder_info': self._extract_placeholder_info(shape),
            'z_order': self._get_z_order(shape)
        }
        return element

    def _classify_shape_type(self, shape):
        """分类形状类型"""
        if shape.is_placeholder:
            ph_type = shape.placeholder_format.type
            type_mapping = {
                1: 'title',
                2: 'text',
                3: 'text',
                7: 'chart',
                8: 'image',
                12: 'title',
                14: 'text'
            }
            return type_mapping.get(ph_type, 'text')

        # 优先检查是否为线条类型
        if hasattr(shape, 'shape_type') and shape.shape_type == MSO_SHAPE_TYPE.LINE:
            return 'line'
        elif hasattr(shape, 'image') and shape.image:
            return 'image'
        elif hasattr(shape, 'chart') and shape.chart:
            return 'chart'
        elif hasattr(shape, 'table') and shape.table:
            return 'table'
        elif hasattr(shape, 'text_frame') and shape.text_frame.text.strip():
            return 'text'
        elif hasattr(shape, 'shape_type'):
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                return 'image'
            elif shape.shape_type == MSO_SHAPE_TYPE.CHART:
                return 'chart'
            elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
                return 'table'
            else:
                return 'shape'
        elif hasattr(shape, 'auto_shape_type'):
            return 'shape'
        else:
            return 'unknown'



    def _extract_text_properties(self, shape):
        """提取文本属性"""
        if not hasattr(shape, 'text_frame') or not shape.text_frame.text.strip():
            return None

        text_frame = shape.text_frame
        properties = {
            'text_length': len(text_frame.text.strip()),
            'paragraph_count': len(text_frame.paragraphs),
            'line_count': self._count_text_lines(text_frame),
            'word_count': self._count_words(text_frame.text),
            'font_styles': [],
            'text_structure': self._analyze_text_structure(text_frame),
            'has_bullets': self._has_bullet_points(text_frame)
        }

        for i, paragraph in enumerate(text_frame.paragraphs):
            font = paragraph.font
            font_style = {
                'paragraph_index': i,
                'level': paragraph.level,
                'text': paragraph.text,
                'text_length': len(paragraph.text),
                'size': font.size,
                'bold': font.bold,
                'italic': font.italic,
                'underline': font.underline,
                'color': self._extract_color_info(font.color),
                'alignment': self._get_alignment_name(paragraph.alignment),
                'line_spacing': getattr(paragraph, 'line_spacing', None),
                'space_before': getattr(paragraph, 'space_before', None),
                'space_after': getattr(paragraph, 'space_after', None)
            }
            properties['font_styles'].append(font_style)

        return properties

    def _extract_visual_properties(self, shape):
        """提取视觉属性"""
        visual_props = {
            'fill': self._extract_fill_properties(shape),
            'line': self._extract_line_properties(shape),
            'effects': self._extract_effect_properties(shape),
            'rotation': getattr(shape, 'rotation', 0)
        }

        # 特殊元素属性
        if hasattr(shape, 'image') and shape.image:
            visual_props['image'] = self._extract_image_properties(shape)
        elif hasattr(shape, 'chart') and shape.chart:
            visual_props['chart'] = self._extract_chart_properties(shape)
        elif hasattr(shape, 'table') and shape.table:
            visual_props['table'] = self._extract_table_properties(shape)

        return visual_props

    def _identify_layout_pattern(self, slide):
        """识别布局模式"""
        elements = self._catalog_slide_elements(slide)
        element_count = sum(len(elements[key]) for key in elements)

        if element_count == 0:
            return 'blank'
        elif element_count == 1:
            return 'centered'

        # 分析元素位置分布
        positions = []
        for element_type, element_list in elements.items():
            for element in element_list:
                positions.append({
                    'center_x': element['position']['left'] + element['position']['width'] / 2,
                    'center_y': element['position']['top'] + element['position']['height'] / 2
                })

        # 判断布局类型
        if self._is_two_column_layout(positions):
            return 'two_column'
        elif self._is_three_column_layout(positions):
            return 'three_column'
        elif self._is_grid_layout(positions):
            return 'grid'
        elif self._is_header_content_layout(elements):
            return 'header_content'
        else:
            return 'free_form'

    def _calculate_complexity(self, slide):
        """计算复杂度"""
        elements = self._catalog_slide_elements(slide)

        # 基础元素数量分数
        element_count = sum(len(elements[key]) for key in elements)
        element_score = min(element_count / 8, 1.0)

        # 文本复杂度分数
        text_complexity = self._calculate_text_complexity(elements)

        # 视觉复杂度分数
        visual_complexity = self._calculate_visual_complexity(elements)

        # 布局复杂度分数
        layout_complexity = self._calculate_layout_complexity(elements)

        # 综合分数
        total_score = (element_score * 0.3 +
                       text_complexity * 0.3 +
                       visual_complexity * 0.25 +
                       layout_complexity * 0.15)

        return min(total_score, 1.0)

    def _get_slide_size(self, slide):
        """获取幻灯片尺寸"""
        try:
            return {
                'width': slide.slide_width,
                'height': slide.slide_height,
                'aspect_ratio': slide.slide_width / slide.slide_height
            }
        except:
            return {'width': 0, 'height': 0, 'aspect_ratio': 0}

    def _analyze_element_distribution(self, slide):
        """分析元素分布"""
        elements = self._catalog_slide_elements(slide)
        distribution = {
            'total_elements': sum(len(elements[key]) for key in elements),
            'by_type': {key: len(elements[key]) for key in elements},
            'area_coverage': self._calculate_area_coverage(slide, elements),
            'quadrant_distribution': self._analyze_quadrant_distribution(slide, elements)
        }
        return distribution

    def _calculate_content_density(self, slide):
        """计算内容密度"""
        elements = self._catalog_slide_elements(slide)
        total_area = slide.slide_layout.slide_master.slide_width * slide.slide_layout.slide_master.slide_height

        if total_area == 0:
            return 0

        occupied_area = 0
        for element_type, element_list in elements.items():
            for element in element_list:
                occupied_area += element['area']

        return min(occupied_area / total_area, 1.0)

    # 辅助方法实现
    def _is_bullet_list(self, text_element):
        """判断是否为项目符号列表"""
        if not text_element.get('text_properties'):
            return False

        props = text_element['text_properties']
        return props.get('has_bullets', False) or props.get('paragraph_count', 0) > 1

    def _count_text_lines(self, text_frame):
        """计算文本行数"""
        try:
            line_count = 0
            for paragraph in text_frame.paragraphs:
                # 简单估算：每40个字符为一行
                line_count += max(1, len(paragraph.text) // 40)
            return line_count
        except:
            return 0

    def _count_words(self, text):
        """计算单词数"""
        try:
            return len(text.split())
        except:
            return 0

    def _analyze_text_structure(self, text_frame):
        """分析文本结构"""
        structure = {
            'has_title': False,
            'has_subtitle': False,
            'has_body': False,
            'hierarchy_levels': set()
        }

        for paragraph in text_frame.paragraphs:
            level = paragraph.level
            structure['hierarchy_levels'].add(level)

            if level == 0:
                structure['has_title'] = True
            elif level == 1:
                structure['has_subtitle'] = True
            else:
                structure['has_body'] = True

        return structure

    def _has_bullet_points(self, text_frame):
        """判断是否有项目符号"""
        for paragraph in text_frame.paragraphs:
            if paragraph.level > 0:  # 非0级通常有项目符号
                return True
        return False

    def _extract_color_info(self, color):
        """提取颜色信息"""
        if not color or not hasattr(color, 'rgb') or not color.rgb:
            return None

        return {
            'rgb': str(color.rgb),
            'type': getattr(color, 'type', None)
        }

    def _get_alignment_name(self, alignment):
        """获取对齐方式名称"""
        alignment_map = {
            PP_ALIGN.LEFT: 'left',
            PP_ALIGN.CENTER: 'center',
            PP_ALIGN.RIGHT: 'right',
            PP_ALIGN.JUSTIFY: 'justify',
            PP_ALIGN.DISTRIBUTE: 'distribute'
        }
        return alignment_map.get(alignment, 'unknown')

    def _extract_fill_properties(self, shape):
        """提取填充属性"""
        try:
            if not hasattr(shape, 'fill'):
                return None

            fill = shape.fill
            fill_info = {
                'type': getattr(fill, 'type', None),
                'transparency': getattr(fill, 'transparency', None)
            }

            if hasattr(fill, 'fore_color') and fill.fore_color.rgb:
                fill_info['fore_color'] = self._extract_color_info(fill.fore_color)
            if hasattr(fill, 'back_color') and fill.back_color.rgb:
                fill_info['back_color'] = self._extract_color_info(fill.back_color)

            return fill_info
        except:
            return None

    def _extract_line_properties(self, shape):
        """提取线条属性"""
        try:
            if not hasattr(shape, 'line'):
                return None

            line = shape.line
            line_info = {
                'width': getattr(line, 'width', None),
                'style': getattr(line, 'style', None),
                'dash_style': getattr(line, 'dash_style', None)
            }

            if hasattr(line, 'color') and line.color.rgb:
                line_info['color'] = self._extract_color_info(line.color)

            return line_info
        except:
            return None

    def _extract_effect_properties(self, shape):
        """提取效果属性"""
        try:
            effects = {}
            if hasattr(shape, 'shadow'):
                shadow = shape.shadow
                if shadow:
                    effects['shadow'] = {
                        'visible': getattr(shadow, 'visible', False),
                        'blur_radius': getattr(shadow, 'blur_radius', None)
                    }
            return effects
        except:
            return {}

    def _extract_image_properties(self, shape):
        """提取图片属性"""
        try:
            return {
                'size': getattr(shape, 'image', {}).get('size', {}),
                'crop': getattr(shape, 'crop', {})
            }
        except:
            return {}

    def _extract_chart_properties(self, shape):
        """提取图表属性"""
        try:
            chart = shape.chart
            return {
                'type': getattr(chart, 'chart_type', None),
                'has_title': hasattr(chart, 'chart_title') and chart.chart_title,
                'series_count': len(chart.series) if hasattr(chart, 'series') else 0
            }
        except:
            return {}

    def _extract_table_properties(self, shape):
        """提取表格属性"""
        try:
            table = shape.table
            return {
                'rows': len(table.rows),
                'columns': len(table.columns),
                'has_header': len(table.rows) > 0
            }
        except:
            return {}

    def _extract_placeholder_info(self, shape):
        """提取占位符信息"""
        if not shape.is_placeholder:
            return None

        return {
            'type': shape.placeholder_format.type,
            'index': getattr(shape.placeholder_format, 'idx', None)
        }

    def _get_z_order(self, shape):
        """获取Z轴顺序（简单实现）"""
        # 在实际应用中，可能需要更复杂的逻辑来确定Z轴顺序
        return 0

    def _is_two_column_layout(self, positions):
        """判断是否为两栏布局"""
        if len(positions) < 2:
            return False

        x_positions = [pos['center_x'] for pos in positions]
        # 简单的聚类判断
        left_count = sum(1 for x in x_positions if x < 4000000)  # 假设幻灯片宽度约8000000
        right_count = len(x_positions) - left_count

        return left_count > 0 and right_count > 0

    def _is_three_column_layout(self, positions):
        """判断是否为三栏布局"""
        if len(positions) < 3:
            return False

        x_positions = [pos['center_x'] for pos in positions]
        # 简化的三栏判断
        return len(set(int(x / 2500000) for x in x_positions)) >= 3

    def _is_grid_layout(self, positions):
        """判断是否为网格布局"""
        if len(positions) < 4:
            return False

        # 检查是否有明显的行列结构
        x_positions = sorted([pos['center_x'] for pos in positions])
        y_positions = sorted([pos['center_y'] for pos in positions])

        # 简化的网格检测
        return True

    def _is_header_content_layout(self, elements):
        """判断是否为标题-内容布局"""
        return len(elements['titles']) > 0 and (len(elements['text_boxes']) > 0 or
                                                len(elements['images']) > 0 or
                                                len(elements['charts']) > 0)

    def _calculate_text_complexity(self, elements):
        """计算文本复杂度"""
        total_text_length = 0
        total_paragraphs = 0

        for text_box in elements['text_boxes']:
            if text_box.get('text_properties'):
                props = text_box['text_properties']
                total_text_length += props.get('text_length', 0)
                total_paragraphs += props.get('paragraph_count', 0)

        # 归一化处理
        length_score = min(total_text_length / 1000, 1.0)
        paragraph_score = min(total_paragraphs / 10, 1.0)

        return (length_score + paragraph_score) / 2

    def _calculate_visual_complexity(self, elements):
        """计算视觉复杂度"""
        visual_elements = (len(elements['images']) +
                           len(elements['charts']) +
                           len(elements['tables']) +
                           len(elements['shapes']))

        return min(visual_elements / 6, 1.0)

    def _calculate_layout_complexity(self, elements):
        """计算布局复杂度"""
        total_elements = sum(len(elements[key]) for key in elements)

        if total_elements <= 1:
            return 0.1
        elif total_elements <= 3:
            return 0.3
        elif total_elements <= 6:
            return 0.6
        else:
            return 0.9

    def _calculate_area_coverage(self, slide, elements):
        """计算面积覆盖率"""
        total_area = slide.slide_layout.slide_master.slide_width * slide.slide_layout.slide_master.slide_height
        if total_area == 0:
            return 0

        occupied_area = 0
        for element_type, element_list in elements.items():
            for element in element_list:
                occupied_area += element['area']

        return occupied_area / total_area

    def _analyze_quadrant_distribution(self, slide, elements):
        """分析象限分布"""
        quadrants = {'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0}
        center_x = slide.slide_width / 2
        center_y = slide.slide_height / 2

        for element_type, element_list in elements.items():
            for element in element_list:
                pos = element['position']
                elem_center_x = pos['left'] + pos['width'] / 2
                elem_center_y = pos['top'] + pos['height'] / 2

                if elem_center_x < center_x and elem_center_y < center_y:
                    quadrants['q1'] += 1
                elif elem_center_x >= center_x and elem_center_y < center_y:
                    quadrants['q2'] += 1
                elif elem_center_x < center_x and elem_center_y >= center_y:
                    quadrants['q3'] += 1
                else:
                    quadrants['q4'] += 1

        return quadrants