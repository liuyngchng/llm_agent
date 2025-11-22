from unittest import TestCase

from apps.docx.app import process_doc


class Test(TestCase):
    def test_fill_docx_with_template(self):
        process_doc(1, '产品发布登记报告', '零售系统运维知识库AI助手测试报告', '', 1, '/home/rd/Downloads/template.docx', 1)



if __name__ == '__main__':
    test = Test()
    test.test_fill_docx_with_template()