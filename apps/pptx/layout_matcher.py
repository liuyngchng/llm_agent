

class LayoutMatcher:
    def __init__(self, template_styles):
        self.template_styles = template_styles

    def find_optimal_layout(self, slide_analysis):
        """为幻灯片找到最优版式"""
        candidate_layouts = self._prefilter_layouts(slide_analysis)

        best_layout = None
        best_score = -1

        for layout in candidate_layouts:
            score = self._calculate_match_score(slide_analysis, layout)
            if score > best_score:
                best_score = score
                best_layout = layout

        return best_layout

    def _calculate_match_score(self, slide_analysis, layout):
        """计算匹配分数"""
        score = 0

        # 1. 内容类型匹配 (30%)
        content_match = self._score_content_type_match(slide_analysis, layout)
        score += content_match * 0.3

        # 2. 占位符数量匹配 (25%)
        placeholder_match = self._score_placeholder_match(slide_analysis, layout)
        score += placeholder_match * 0.25

        # 3. 元素位置兼容性 (25%)
        position_match = self._score_position_compatibility(slide_analysis, layout)
        score += position_match * 0.25

        # 4. 特殊元素支持 (20%)
        special_element_match = self._score_special_elements(slide_analysis, layout)
        score += special_element_match * 0.2

        return score

    def _score_content_type_match(self, slide_analysis, layout):
        """评分内容类型匹配度"""
        slide_type = slide_analysis['content_type']
        layout_type = layout['layout_type']

        type_compatibility = {
            'title': ['title', 'section_header'],
            'content': ['content', 'two_content', 'comparison'],
            'visual': ['visual', 'image', 'chart'],
            'mixed': ['mixed', 'content', 'visual']
        }

        if layout_type in type_compatibility.get(slide_type, []):
            return 1.0
        else:
            return 0.3  # 基本兼容性分数

    def _score_placeholder_match(self, slide_analysis, layout):
        """评分占位符数量匹配度"""
        required_placeholders = self._count_required_placeholders(slide_analysis)
        available_placeholders = len(layout['placeholders'])

        if available_placeholders >= required_placeholders:
            return 1.0
        else:
            return available_placeholders / required_placeholders

    def _prefilter_layouts(self, slide_analysis):
        """预过滤版式 - 需要实现"""
        content_type = slide_analysis['content_type']
        compatible_layouts = []

        for layout in self.template_styles.get('slide_layouts', []):
            if self._is_layout_compatible(layout, content_type):
                compatible_layouts.append(layout)

        return compatible_layouts

    def _is_layout_compatible(self, layout, content_type):
        """检查版式兼容性 - 需要实现"""
        layout_type = layout.get('layout_type', '')
        compatibility = {
            'title': ['title'],
            'content': ['content', 'mixed'],
            'visual': ['visual', 'mixed'],
            'mixed': ['content', 'visual', 'mixed']
        }
        return layout_type in compatibility.get(content_type, [])

    def _count_required_placeholders(self, slide_analysis):
        """计算所需占位符数量 - 需要实现"""
        elements = slide_analysis['elements']
        # 简单逻辑：每个非空元素类型需要一个占位符
        required = 0
        for element_type, element_list in elements.items():
            if element_list and element_type != 'shapes':  # 忽略普通形状
                required += 1
        return max(required, 1)  # 至少需要1个

    def _score_position_compatibility(self, slide_analysis, layout):
        """评分位置兼容性 - 需要实现"""
        # 简化实现
        return 0.7

    def _score_special_elements(self, slide_analysis, layout):
        """评分特殊元素支持"""
        elements = slide_analysis['elements']
        has_charts = bool(elements['charts'])
        has_tables = bool(elements['tables'])

        layout_name = layout.get('name', '').lower()
        layout_type = layout.get('layout_type', '').lower()

        # 1. 图表支持
        if has_charts:
            if 'chart' in layout_name or 'visual' in layout_type:
                return 1.0
            elif 'mixed' in layout_type:
                return 0.8

        # 2. 表格支持
        if has_tables:
            if 'table' in layout_name or 'content' in layout_type:
                return 1.0
            elif 'mixed' in layout_type:
                return 0.8

        # 3. 默认分数
        return 0.5 if has_charts or has_tables else 0.0