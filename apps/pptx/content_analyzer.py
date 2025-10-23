


class ContentAnalyzer:
    def analyze_slide_content(self, slide):
        """深度分析幻灯片内容结构"""
        content_analysis = {
            'content_type': self._determine_content_type(slide),
            'elements': self._catalog_slide_elements(slide),
            'layout_pattern': self._identify_layout_pattern(slide),
            'complexity_score': self._calculate_complexity(slide)
        }
        return content_analysis

    def _determine_content_type(self, slide):
        """确定内容类型 - 需要实现"""
        elements = self._catalog_slide_elements(slide)

        if elements['images'] or elements['charts']:
            if elements['text_boxes']:
                return 'mixed'
            return 'visual'
        elif elements['text_boxes']:
            return 'content'
        else:
            return 'title'

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
                'height': shape.height
            },
            'text_properties': self._extract_text_properties(shape),
            'visual_properties': self._extract_visual_properties(shape)
        }
        return element

    def _classify_shape_type(self, shape):
        """分类形状类型"""
        if shape.is_placeholder:
            if shape.placeholder_format.type == 1:  # Title
                return 'title'
            elif shape.placeholder_format.type == 2:  # Body
                return 'text'

        if hasattr(shape, 'image'):
            return 'image'
        elif hasattr(shape, 'chart'):
            return 'chart'
        elif hasattr(shape, 'table'):
            return 'table'
        elif hasattr(shape, 'text_frame') and shape.text_frame.text.strip():
            return 'text'
        else:
            return 'shape'

    def _extract_text_properties(self, shape):
        """提取文本属性"""
        if not hasattr(shape, 'text_frame'):
            return None

        text_frame = shape.text_frame
        properties = {
            'text_length': len(text_frame.text.strip()),
            'paragraph_count': len(text_frame.paragraphs),
            'font_styles': []
        }

        for paragraph in text_frame.paragraphs:
            font = paragraph.font
            font_style = {
                'size': font.size,
                'bold': font.bold,
                'italic': font.italic,
                'color': str(font.color.rgb) if font.color.rgb else None,
                'alignment': paragraph.alignment
            }
            properties['font_styles'].append(font_style)

        return properties

    def _identify_layout_pattern(self, slide):
        """识别布局模式 - 需要实现"""
        # 简化的布局识别
        elements = self._catalog_slide_elements(slide)
        if len(elements['text_boxes']) > 1:
            return 'multi_column'
        return 'single_column'

    def _calculate_complexity(self, slide):
        """计算复杂度 - 需要实现"""
        elements = self._catalog_slide_elements(slide)
        total_elements = sum(len(elements[key]) for key in elements)
        return min(total_elements / 10, 1.0)  # 归一化到0-1

    def _extract_visual_properties(self, shape):
        """提取视觉属性 - 需要实现"""
        if hasattr(shape, 'fill'):
            return {
                'fill_type': getattr(shape.fill, 'type', None),
                'line_color': str(getattr(shape.line.color.rgb, 'rgb', None)) if hasattr(shape, 'line') else None
            }
        return {}