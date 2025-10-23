"""
通过 PPT 模板分析用户 PPT 中的内容是否符合规范，直接对报告进行调整不符合模板规范的直接修改  PPT 格式。
"""
from apps.pptx.ppt_formatter import PPTFormatter


def do_task():
    try:
        # 1. 初始化处理器
        formatter = PPTFormatter()

        # 2. 提取模板样式
        print("正在提取模板样式...")
        template_styles = formatter.extract_template_styles('company_template.pptx')
        print(f"提取到 {len(template_styles['slide_layouts'])} 个版式")

        # 3. 分析源PPT
        print("正在分析源PPT结构...")
        source_analysis = formatter.analyze_ppt_structure('source_presentation.pptx')
        print(f"分析了 {len(source_analysis)} 张幻灯片")

        # 4. 格式化PPT
        print("正在格式化PPT...")
        formatted_ppt = formatter.format_ppt('source_presentation.pptx', template_styles)

        # 5. 保存结果
        formatted_ppt.save('formatted_presentation.pptx')
        print("格式化完成！结果已保存为 'formatted_presentation.pptx'")

        # 6. 生成报告
        compliance_report = formatter.generate_compliance_report(formatted_ppt)
        print(f"合规报告: {compliance_report}")

    except FileNotFoundError as e:
        print(f"文件未找到: {e}")
        print("请确保 'company_template.pptx' 和 'source_presentation.pptx' 文件存在")
    except Exception as e:
        print(f"处理过程中出现错误: {e}")

if __name__ == '__main__':
    do_task()