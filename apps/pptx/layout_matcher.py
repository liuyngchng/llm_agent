#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
为幻灯片匹配最优版式。
计算版式匹配分数（基于内容类型、占位符数量、特殊元素支持等）
"""
class LayoutMatcher:
    def __init__(self, template_styles):
        self.template_styles = template_styles
        self.layout_compatibility_rules = self._initialize_compatibility_rules()

    def find_optimal_layout(self, slide_analysis):
        """为幻灯片找到最优版式"""
        candidate_layouts = self._prefilter_layouts(slide_analysis)

        if not candidate_layouts:
            print("警告：没有找到兼容的版式，使用默认版式")
            return self._get_default_layout()

        best_layout = None
        best_score = -1
        scored_layouts = []

        for layout in candidate_layouts:
            score = self._calculate_match_score(slide_analysis, layout)
            scored_layouts.append((layout, score))

            if score > best_score:
                best_score = score
                best_layout = layout

        # 输出匹配结果用于调试
        self._log_matching_results(slide_analysis, scored_layouts, best_layout)

        return best_layout

    def _calculate_match_score(self, slide_analysis, layout):
        """计算匹配分数"""
        score = 0

        # 1. 内容类型匹配 (25%)
        content_match = self._score_content_type_match(slide_analysis, layout)
        score += content_match * 0.25

        # 2. 占位符数量匹配 (20%)
        placeholder_match = self._score_placeholder_match(slide_analysis, layout)
        score += placeholder_match * 0.20

        # 3. 元素位置兼容性 (20%)
        position_match = self._score_position_compatibility(slide_analysis, layout)
        score += position_match * 0.20

        # 4. 特殊元素支持 (15%)
        special_element_match = self._score_special_elements(slide_analysis, layout)
        score += special_element_match * 0.15

        # 5. 布局复杂度匹配 (10%)
        complexity_match = self._score_complexity_match(slide_analysis, layout)
        score += complexity_match * 0.10

        # 6. 语义匹配 (10%)
        semantic_match = self._score_semantic_match(slide_analysis, layout)
        score += semantic_match * 0.10

        return min(score, 1.0)  # 确保不超过1.0

    def _score_content_type_match(self, slide_analysis, layout):
        """评分内容类型匹配度"""
        slide_type = slide_analysis['content_type']
        layout_type = layout.get('layout_type', 'unknown')

        # 扩展的内容类型兼容性规则
        type_compatibility = {
            'title': ['title', 'title_only', 'section_header', 'blank'],
            'content': ['content', 'text', 'two_content', 'comparison', 'blank'],
            'bullet_list': ['content', 'text', 'list', 'two_content'],
            'multi_content': ['content', 'two_content', 'comparison', 'multi_column'],
            'visual': ['visual', 'picture', 'image', 'blank'],
            'mixed_visual': ['mixed', 'content_with_picture', 'text_and_image'],
            'data': ['content', 'table', 'chart_and_text'],
            'mixed_data': ['mixed', 'content', 'table_and_text'],
            'diagram': ['blank', 'content', 'visual'],
            'blank': ['blank', 'title', 'content']
        }

        compatible_types = type_compatibility.get(slide_type, ['content', 'mixed'])

        if layout_type in compatible_types:
            return 1.0
        elif any(comp_type in layout_type for comp_type in compatible_types):
            return 0.8
        else:
            return 0.3  # 基本兼容性分数

    def _score_placeholder_match(self, slide_analysis, layout):
        """评分占位符数量匹配度"""
        required_placeholders = self._count_required_placeholders(slide_analysis)
        available_placeholders = len(layout.get('placeholders', []))

        if available_placeholders == 0:
            return 0.1  # 几乎没有占位符的版式得分很低

        if available_placeholders >= required_placeholders:
            # 完美匹配或有多余占位符
            excess_ratio = (available_placeholders - required_placeholders) / max(required_placeholders, 1)
            excess_penalty = max(0, 1.0 - excess_ratio * 0.2)  # 多余占位符有轻微惩罚
            return 1.0 * excess_penalty
        else:
            # 占位符不足
            match_ratio = available_placeholders / required_placeholders
            return match_ratio * 0.8  # 不足时最高得0.8

    def _prefilter_layouts(self, slide_analysis):
        """预过滤版式"""
        content_type = slide_analysis['content_type']
        compatible_layouts = []

        for layout in self.template_styles.get('slide_layouts', []):
            if self._is_layout_compatible(layout, content_type, slide_analysis):
                compatible_layouts.append(layout)

        # 如果没有找到兼容版式，返回所有版式
        if not compatible_layouts:
            print(f"警告：没有找到与内容类型 '{content_type}' 兼容的版式，返回所有可用版式")
            return self.template_styles.get('slide_layouts', [])

        return compatible_layouts

    def _is_layout_compatible(self, layout, content_type, slide_analysis=None):
        """检查版式兼容性"""
        layout_type = layout.get('layout_type', '')
        layout_name = layout.get('name', '').lower()

        # 基础兼容性检查
        base_compatibility = {
            'title': ['title', 'title_only', 'section_header'],
            'content': ['content', 'text', 'two_content', 'comparison'],
            'bullet_list': ['content', 'text', 'list'],
            'visual': ['visual', 'picture', 'image'],
            'data': ['content', 'table'],
            'blank': ['blank', 'title']
        }

        # 检查基础兼容性
        compatible_types = base_compatibility.get(content_type, ['content', 'mixed'])
        base_match = layout_type in compatible_types or any(ct in layout_type for ct in compatible_types)

        # 特殊元素兼容性检查
        special_compatibility = self._check_special_element_compatibility(layout, slide_analysis)

        return base_match and special_compatibility

    def _check_special_element_compatibility(self, layout, slide_analysis):
        """检查特殊元素兼容性"""
        if not slide_analysis:
            return True

        elements = slide_analysis.get('elements', {})

        # 检查图表兼容性
        if elements.get('charts') and not self._layout_supports_charts(layout):
            return False

        # 检查表格兼容性
        if elements.get('tables') and not self._layout_supports_tables(layout):
            return False

        # 检查图片兼容性
        if elements.get('images') and not self._layout_supports_images(layout):
            return False

        return True

    def _count_required_placeholders(self, slide_analysis):
        """计算所需占位符数量"""
        elements = slide_analysis['elements']
        required = 0

        # 标题需要1个占位符
        if elements['titles']:
            required += 1

        # 正文文本框需要占位符
        if elements['text_boxes']:
            required += len(elements['text_boxes'])

        # 图片需要占位符
        if elements['images']:
            required += len(elements['images'])

        # 图表需要占位符
        if elements['charts']:
            required += len(elements['charts'])

        # 表格需要占位符
        if elements['tables']:
            required += len(elements['tables'])

        # 确保至少需要1个占位符
        return max(required, 1)

    def _score_position_compatibility(self, slide_analysis, layout):
        """评分位置兼容性"""
        slide_elements = slide_analysis['elements']
        layout_placeholders = layout.get('placeholders', [])

        if not slide_elements or not layout_placeholders:
            return 0.5  # 中性分数

        # 分析幻灯片元素的位置分布
        element_positions = self._analyze_element_positions(slide_elements)
        placeholder_positions = self._analyze_placeholder_positions(layout_placeholders)

        # 计算位置匹配度
        position_score = self._calculate_position_similarity(element_positions, placeholder_positions)

        return position_score

    def _analyze_element_positions(self, elements):
        """分析元素位置分布"""
        positions = {
            'has_title': bool(elements.get('titles')),
            'has_center_content': False,
            'has_side_content': False,
            'content_areas': []
        }

        # 分析标题位置（通常在顶部）
        if elements.get('titles'):
            positions['has_title'] = True

        # 分析正文内容位置
        for element_type in ['text_boxes', 'images', 'charts', 'tables']:
            for element in elements.get(element_type, []):
                position = element.get('position', {})
                center_y = position.get('top', 0) + position.get('height', 0) / 2

                # 判断内容区域
                if center_y < 0.4:  # 顶部区域
                    positions['has_center_content'] = True
                elif center_y > 0.6:  # 底部区域
                    positions['has_side_content'] = True
                else:  # 中间区域
                    positions['has_center_content'] = True

        return positions

    def _analyze_placeholder_positions(self, placeholders):
        """分析占位符位置分布"""
        positions = {
            'has_title': False,
            'has_center_content': False,
            'has_side_content': False,
            'placeholder_count': len(placeholders)
        }

        for placeholder in placeholders:
            ph_type = placeholder.get('type')
            position = placeholder.get('position', {})

            if ph_type == 1:  # 标题占位符
                positions['has_title'] = True
            else:
                # 分析内容占位符位置
                center_y = (position.get('top', 0) + position.get('height', 0) / 2) / 1000000  # 归一化

                if center_y < 0.4:  # 顶部内容
                    positions['has_center_content'] = True
                elif center_y > 0.6:  # 底部内容
                    positions['has_side_content'] = True
                else:  # 中间内容
                    positions['has_center_content'] = True

        return positions

    def _calculate_position_similarity(self, element_positions, placeholder_positions):
        """计算位置相似度"""
        score = 0
        total_checks = 0

        # 标题位置匹配
        if element_positions['has_title'] and placeholder_positions['has_title']:
            score += 1
        elif not element_positions['has_title'] and not placeholder_positions['has_title']:
            score += 1
        total_checks += 1

        # 中心内容匹配
        if element_positions['has_center_content'] and placeholder_positions['has_center_content']:
            score += 1
        elif not element_positions['has_center_content'] and not placeholder_positions['has_center_content']:
            score += 1
        total_checks += 1

        # 侧边内容匹配
        if element_positions['has_side_content'] and placeholder_positions['has_side_content']:
            score += 1
        elif not element_positions['has_side_content'] and not placeholder_positions['has_side_content']:
            score += 1
        total_checks += 1

        return score / total_checks if total_checks > 0 else 0.5

    def _score_special_elements(self, slide_analysis, layout):
        """评分特殊元素支持"""
        elements = slide_analysis['elements']
        score = 0.5  # 基础分数

        has_charts = bool(elements.get('charts'))
        has_tables = bool(elements.get('tables'))
        has_images = bool(elements.get('images'))

        layout_name = layout.get('name', '').lower()
        layout_type = layout.get('layout_type', '').lower()
        placeholders = layout.get('placeholders', [])

        # 图表支持评分
        if has_charts:
            if self._layout_supports_charts(layout):
                score = max(score, 0.9)
            else:
                score = max(score, 0.6)

        # 表格支持评分
        if has_tables:
            if self._layout_supports_tables(layout):
                score = max(score, 0.9)
            else:
                score = max(score, 0.6)

        # 图片支持评分
        if has_images:
            if self._layout_supports_images(layout):
                score = max(score, 0.8)
            else:
                score = max(score, 0.5)

        return score

    def _layout_supports_charts(self, layout):
        """检查版式是否支持图表"""
        layout_name = layout.get('name', '').lower()
        layout_type = layout.get('layout_type', '').lower()

        # 检查占位符类型
        for placeholder in layout.get('placeholders', []):
            if placeholder.get('type') in [7, 14]:  # 图表占位符类型
                return True

        # 检查布局名称和类型
        chart_keywords = ['chart', 'graph', 'visual', 'data']
        return any(keyword in layout_name or keyword in layout_type for keyword in chart_keywords)

    def _layout_supports_tables(self, layout):
        """检查版式是否支持表格"""
        # 表格通常可以使用内容占位符
        layout_name = layout.get('name', '').lower()
        layout_type = layout.get('layout_type', '').lower()

        table_keywords = ['table', 'data', 'content']
        return any(keyword in layout_name or keyword in layout_type for keyword in table_keywords)

    def _layout_supports_images(self, layout):
        """检查版式是否支持图片"""
        # 检查图片占位符
        for placeholder in layout.get('placeholders', []):
            if placeholder.get('type') in [8, 13]:  # 图片占位符类型
                return True

        layout_name = layout.get('name', '').lower()
        layout_type = layout.get('layout_type', '').lower()

        image_keywords = ['picture', 'image', 'photo', 'visual']
        return any(keyword in layout_name or keyword in layout_type for keyword in image_keywords)

    def _score_complexity_match(self, slide_analysis, layout):
        """评分布局复杂度匹配"""
        slide_complexity = slide_analysis.get('complexity_score', 0.5)
        layout_complexity = self._calculate_layout_complexity(layout)

        # 计算复杂度差异
        complexity_diff = abs(slide_complexity - layout_complexity)

        # 差异越小得分越高
        return 1.0 - complexity_diff

    def _calculate_layout_complexity(self, layout):
        """计算布局复杂度"""
        placeholders = layout.get('placeholders', [])
        placeholder_count = len(placeholders)

        # 基于占位符数量的简单复杂度计算
        if placeholder_count == 0:
            return 0.1
        elif placeholder_count == 1:
            return 0.3
        elif placeholder_count == 2:
            return 0.5
        elif placeholder_count == 3:
            return 0.7
        else:
            return 0.9

    def _score_semantic_match(self, slide_analysis, layout):
        """评分语义匹配"""
        layout_name = layout.get('name', '').lower()
        layout_type = layout.get('layout_type', '').lower()
        slide_type = slide_analysis.get('content_type', '')

        # 语义关键词映射
        semantic_keywords = {
            'title': ['title', 'header', 'cover'],
            'content': ['content', 'text', 'body'],
            'bullet_list': ['list', 'bullet', 'item'],
            'visual': ['visual', 'picture', 'image', 'chart'],
            'data': ['data', 'table', 'statistic']
        }

        # 查找匹配的关键词
        keywords = semantic_keywords.get(slide_type, [])
        for keyword in keywords:
            if keyword in layout_name or keyword in layout_type:
                return 0.8

        return 0.5  # 中性分数

    def _get_default_layout(self):
        """获取默认版式"""
        layouts = self.template_styles.get('slide_layouts', [])
        if layouts:
            # 返回第一个内容版式或第一个可用版式
            for layout in layouts:
                if layout.get('layout_type') in ['content', 'text']:
                    return layout
            return layouts[0]
        return None

    def _initialize_compatibility_rules(self):
        """初始化兼容性规则"""
        return {
            'strict_matching': False,
            'prefer_simple_layouts': True,
            'allow_placeholder_reuse': True
        }

    def _log_matching_results(self, slide_analysis, scored_layouts, best_layout):
        """记录匹配结果（用于调试）"""
        if not scored_layouts:
            return

        print(f"\n=== 版式匹配结果 ===")
        print(f"幻灯片类型: {slide_analysis.get('content_type', 'unknown')}")
        print(f"元素统计: {self._get_element_summary(slide_analysis['elements'])}")
        print(f"候选版式数量: {len(scored_layouts)}")

        # 显示前3个最佳匹配
        scored_layouts.sort(key=lambda x: x[1], reverse=True)
        for i, (layout, score) in enumerate(scored_layouts[:3]):
            print(f"{i + 1}. {layout.get('name', 'unknown')} - 得分: {score:.3f}")

        if best_layout:
            print(f"选择版式: {best_layout.get('name', 'unknown')}")

    def _get_element_summary(self, elements):
        """获取元素统计摘要"""
        summary = []
        for elem_type, elem_list in elements.items():
            if elem_list:
                summary.append(f"{elem_type}:{len(elem_list)}")
        return ", ".join(summary) if summary else "空幻灯片"