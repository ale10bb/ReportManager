import unittest
import os
from RM import document


class TestDocument(unittest.TestCase):
    def test_read_document_dsys(self):
        expected = {
            'pages': 387,
            'company': '上海市黄浦区城市运行管理中心（上海市黄浦区城市网格化综合管理中心、上海市黄浦区大数据中心）',
            'names': {'SHTEC2021DSYS0685': '黄浦区数据共享交换系统'}
        }
        self.assertDictEqual(
            document.read_document(
                os.path.join(os.getcwd(), 'storage', 'document', 'dsys')),
            expected
        )

    def test_read_document_fun(self):
        expected = {
            'pages': 41,
            'company': '上海市浦东新区档案局',
            'names': {'SHTEC2022FUN0012': '浦东新区数字档案馆系统'}
        }
        self.assertDictEqual(
            document.read_document(
                os.path.join(os.getcwd(), 'storage', 'document', 'fun')),
            expected
        )

    def test_read_document_pro(self):
        expected = {
            'pages': 42,
            'company': '中共上海市委台湾工作办公室',
            'names': {'SHTEC2022PRO0264': '沪台通云平台'}
        }
        self.assertDictEqual(
            document.read_document(
                os.path.join(os.getcwd(), 'storage', 'document', 'pro')),
            expected
        )

    def test_read_document_pst(self):
        expected = {
            'pages': 92,
            'company': '中共上海市委台湾工作办公室',
            'names': {'SHTEC2022PST0184': '沪台通云平台'}
        }
        self.assertDictEqual(
            document.read_document(
                os.path.join(os.getcwd(), 'storage', 'document', 'pst')),
            expected
        )

    def test_read_document_srv(self):
        expected = {
            'pages': 22,
            'company': '上海市退役军人事务局',
            'names': {'SHTEC2022SRV0037': '退役军人及其他优抚对象优待证信息预采集系统'}
        }
        self.assertDictEqual(
            document.read_document(
                os.path.join(os.getcwd(), 'storage', 'document', 'srv')),
            expected
        )

    def test_read_XT13(self):
        expected = {
            'pages': 0,
            'company': '',
            'names': {
                'SHTEC2021DSYS0685': '黄浦区数据共享交换系统',
                'SHTEC2022FUN0012': '浦东新区数字档案馆系统',
                'SHTEC2022PRO0264': '沪台通云平台',
                'SHTEC2022PST0184': '沪台通云平台',
                'SHTEC2022SRV0037': '退役军人及其他优抚对象优待证信息预采集系统',
            }
        }
        self.assertDictEqual(
            document.read_XT13(
                os.path.join(os.getcwd(), 'storage', 'document')),
            expected
        )

    def test_encrypt(self):
        with self.assertNoLogs('', level='WARNING') as cm:
            document.encrypt(os.path.join(
                os.getcwd(), 'storage', 'document', 'test_win32.doc'))


if __name__ == '__main__':
    unittest.main()
