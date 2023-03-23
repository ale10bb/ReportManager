import unittest
import os
from RM import validator
from RM import mysql


class TestDocument(unittest.TestCase):
    def setUp(self):
        from configparser import ConfigParser
        config = ConfigParser()
        config.read(os.path.join('conf', 'RM.conf'), encoding='UTF-8')
        mysql.init(
            user=config.get('mysql', 'user', fallback='rm'),
            password=config.get('mysql', 'pass', fallback='rm'),
            host=config.get('mysql', 'host', fallback='127.0.0.1'),
            database=config.get('mysql', 'db', fallback='rm'),
            port=config.getint('mysql', 'port', fallback=3306),
        )

    def test_content_empty(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_urgent(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': True,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='加急 1',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_urgent2(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': True,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='加急 是',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_urgent_empty(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='加急 ',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_urgent_invalid(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='加急 asdfasdf',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_manual_sender(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user11_1',
                'name': 'r1a1用户1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核] --sender user11_1',
                content='',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_manual_wrong_sender(self):
        with self.assertRaises(ValueError):
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核] --sender user10',
                content='',
                timestamp=1679556257,
            )

    def test_content_force(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': 'user11_2',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='指定 user11_2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_by_name(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': 'user11_2',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='指定 r1a1用户2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_notunique(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': ['已去除无效指定 "1"']
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='指定 1',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_unavailable(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': ['已去除无效指定 "user00"']
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='指定 user00',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_notreviewer(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': ['已去除无效指定 "user01"']
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='指定 user01',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_author(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user11_2',
                'name': 'r1a1用户2',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': ['指定"user11_2"失败: 项目相关人员']
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user11_2@example.com',
                subject='[提交审核]',
                content='指定 user11_2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_member(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user11_2',
                'name': 'r1a1用户2',
                'urgent': False,
                'excludes': ['user11_3'],
                'force': '',
            },
            'warnings': ['指定"user11_3"失败: 项目相关人员']
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user11_2@example.com',
                subject='[提交审核]',
                content='指定 user11_3\r\n组员 user11_3',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_force_wrong_fakeuser(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': ['已去除无效指定 "fake"']
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='指定 fake',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_member(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': ['user11_2'],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='组员 user11_2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_member_repeat(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': ['user11_2'],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='组员 user11_2、user11_2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_member_repeat2(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user01',
                'name': 'r0a1',
                'urgent': False,
                'excludes': ['user11_2'],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user01@example.com',
                subject='[提交审核]',
                content='组员 user11_2、r1a1用户2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_member_author(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user11_2',
                'name': 'r1a1用户2',
                'urgent': False,
                'excludes': ['user11_2'],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user11_2@example.com',
                subject='[提交审核]',
                content='组员 user11_2',
                timestamp=1679556257,
            ),
            expected
        )

    def test_content_member_notreviewer(self):
        expected = {
            'content': {
                'timestamp': 1679556257,
                'user_id': 'user11_2',
                'name': 'r1a1用户2',
                'urgent': False,
                'excludes': [],
                'force': '',
            },
            'warnings': []
        }
        self.assertDictEqual(
            validator.check_mail_content(
                from_='user11_2@example.com',
                subject='[提交审核]',
                content='组员 user01',
                timestamp=1679556257,
            ),
            expected
        )


if __name__ == '__main__':
    unittest.main()
