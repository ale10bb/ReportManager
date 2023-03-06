# -*- coding: UTF-8 -*-
import os
import logging
import datetime
import zmail
from email.header import Header
from email.utils import formataddr
import requests

class Mail:
    ''' zmail的封装客户端，实现邮件收发
    '''
    _pop3_config = {}
    _smtp_config = {}
    _mail_config = {}

    def __init__(self, pop3_config:dict={}, smtp_config:dict={}, mail_config:dict={}):
        ''' 初始化mail的配置

        Args:
            pop3_config(dict): 需包含'username'、'password'、'host'、'port'、'ssl'、'tls'
            smtp_config(dict): 需包含'username'、'password'、'host'、'port'、'ssl'、'tls'
            mail_config(dict): 需包含'default_domain'、'default_cc'

        Raises:
            AssertionError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)

        ## pop3，连接失败则抛出异常
        assert zmail.server(
            username=pop3_config.setdefault('username', 'rm@example.com'), 
            password=pop3_config.setdefault('password', 'rm'), 
            pop_host=pop3_config.setdefault('host', 'example.com'), 
            pop_port=pop3_config.setdefault('port', 110),
            pop_ssl=pop3_config.setdefault('ssl', False),
            pop_tls=pop3_config.setdefault('tls', False),
        ).pop_able(), 'Failed to login POP3 Server.'
        self._pop3_config = pop3_config
        logger.info('POP3 configration ({}) confirmed.'.format(pop3_config['username']))

        # smtp，连接失败则抛出异常
        assert zmail.server(
            username=smtp_config.setdefault('username', 'rm@example.com'),
            password=smtp_config.setdefault('password', 'rm'),  
            smtp_host=smtp_config.setdefault('host', 'example.com'), 
            smtp_port=smtp_config.setdefault('port', 110),
            smtp_ssl=smtp_config.setdefault('ssl', False),
            smtp_tls=smtp_config.setdefault('tls', False),
        ).smtp_able(), 'Failed to login SMTP Server.'
        self._smtp_config = smtp_config
        logger.info('SMTP configration ({}) confirmed.'.format(smtp_config['username']))

        # 其他邮件设置
        assert type(mail_config.setdefault('default_domain', 'example.com')) == str, 'invalid arg: mail_config.default_domain'
        logger.info('default_domain: {}'.format(mail_config['default_domain']))
        assert type(mail_config.setdefault('default_cc', 'example.com')) == str, 'invalid arg: mail_config.default_cc'
        logger.info('default_cc: {}'.format(mail_config['default_cc']))
        self._mail_config = mail_config

    def receive(self, temp_path:str, keywords:dict={}) -> list:
        ''' 按照{keywords}指定的关键词拉取邮件，并将原始邮件和附件存放在{temp_path}

        Args:
            temp_path(str): 临时存放邮件的位置；
            keywords: {'submit': (str), 'finish': (str)}；默认为[提交审核]和[完成审核]；

        Returns:
            [{xxx}(check_results), ...]

        Raises:
            AssertionError: 如果参数类型非法
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: {}'.format({'temp_path': temp_path, 'keywords': keywords}))
        assert os.path.isdir(temp_path), 'invalid arg: temp_path'
        if not keywords:
            keywords = {'submit': '[提交审核]', 'finish': '[完成审核]'}
        assert (type(keywords.setdefault('submit', '[提交审核]')) == str and 
            type(keywords.setdefault('finish', '[完成审核]')) == str
        ), 'invalid arg: keywords'

        pop3_server = zmail.server(
            username=self._pop3_config['username'], 
            password=self._pop3_config['password'], 
            pop_host=self._pop3_config['host'], 
            pop_port=self._pop3_config['port'],
            pop_ssl=self._pop3_config['ssl'],
            pop_tls=self._pop3_config['tls'],
        )
        logger.debug('pop_able: {}'.format(pop3_server.pop_able()))

        ret = []
        for operator in ['submit', 'finish']:
            mails = pop3_server.get_mails(subject=keywords[operator], sender=self._mail_config['default_domain'])
            logger.debug('{} elements in "{}"'.format(len(mails), keywords[operator]))
            # 反向处理邮件，当发生重复时按最后一份处理
            for mail in reversed(mails):
                check_results = {
                    'operator': operator, 
                    'keyword': keywords[operator],
                    'mail': {
                        'timestamp': int(mail['date'].timestamp()),
                        'from': mail['from'], 
                        'subject': mail['subject'], 
                        'content': mail['content_text'], 
                        'attachments': [a[0] for a in mail['attachments']]
                    },
                    'warnings': []
                }
                logger.debug('mail: {}'.format(check_results['mail']))
                check_results['work_path'] = os.path.join(temp_path, '{}_{}'.format(int(datetime.datetime.now().timestamp() * 1000), operator))
                os.mkdir(check_results['work_path'])
                logger.info('saving eml to "{}"'.format(check_results['work_path']))
                zmail.save(mail, 'raw.eml', target_path=check_results['work_path'], overwrite=True)
                os.mkdir(os.path.join(check_results['work_path'], 'attachments'))
                zmail.save_attachment(mail, target_path=os.path.join(check_results['work_path'], 'attachments'), overwrite=True)
                ret.append(check_results)
                pop3_server.delete(mail['id'])
                logger.debug('deleted {}'.format(mail['id']))

        logger.debug('return: {}'.format(ret))
        return ret

    def read(self, temp_path:str, key:str, eml_path:str) -> dict:
        ''' 读取本地eml文件，并将原始邮件和附件存放在{temp_path}

        Args:
            temp_path(str): 临时存放邮件的位置；
            key(str): 'submit' or 'finish'
            eml_path(str): 本地eml文件的路径

        Returns:
            {xxx}(check_results)

        Raises:
            AssertionError: 如果参数类型非法
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: {}'.format({'temp_path': temp_path, 'key': key, 'eml_path': eml_path}))
        assert os.path.isdir(temp_path), 'invalid arg: temp_path'
        assert key in ['submit', 'finish'], 'invalid arg: key'
        assert os.path.isfile(eml_path), 'invalid arg: eml_path'
        mail = zmail.read(eml_path)
        check_results = {
            'operator': key, 
            'keyword': '',
            'mail': {
                'timestamp': int(mail['date'].timestamp()),
                'from': mail['from'], 
                'subject': mail['subject'], 
                'content': mail['content_text'], 
                'attachments': [a[0] for a in mail['attachments']]
            },
            'warnings': []
        }
        logger.debug('mail: {}'.format(check_results['mail']))
        check_results['work_path'] = os.path.join(temp_path, '{}_{}'.format(int(datetime.datetime.now().timestamp() * 1000), key))
        os.mkdir(check_results['work_path'])
        logger.info('saving eml to "{}"'.format(check_results['work_path']))
        zmail.save(mail, 'raw.eml', target_path=check_results['work_path'], overwrite=True)
        os.mkdir(os.path.join(check_results['work_path'], 'attachments'))
        zmail.save_attachment(mail, target_path=os.path.join(check_results['work_path'], 'attachments'), overwrite=True)

        logger.debug('return: {}'.format(check_results))
        return check_results

    def send(self, user_id:str, subject:str, content:str='', attachment:str='', needs_cc:bool=False, to_stdout=False):
        ''' 向{user_id}发送邮件。

        Args:
            user_id(str): 用户ID
            subject(str): 邮件主题
            content(str): 邮件内容
            attachment(str): 附件文件路径（绝对路径）（可选/默认值[]）
            needs_cc(bool): 是否抄送管理员（可选/默认值False）
            to_stdout(bool): 是否将邮件重定向到stdout（可选/默认值False）

        Raises:
            AssertionError: 如果参数类型非法
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: {}'.format({
            'user_id': user_id, 
            'subject': subject, 
            'content': content, 
            'attachment': attachment, 
            'needs_cc': needs_cc,
            'to_stdout': to_stdout,
        }))
        assert type(user_id) == str, 'invalid arg: user_id'
        assert type(subject) == str, 'invalid arg: subject'
        assert type(content) == str, 'invalid arg: content'
        if attachment:
            assert os.path.exists(attachment), 'invalid arg: attachment'

        mail = {
            'subject': subject, 
            'from': formataddr((Header('审核管理机器人', 'utf-8').encode(), self._smtp_config['username'])), 
            'content_text': content, 
            'attachments': [attachment]
        }
        logger.debug('mail: {}'.format(mail))

        if to_stdout:
            logger.warning('redirect to stdout and return')
            return

        smtp_server = zmail.server(
            username=self._smtp_config['username'], 
            password=self._smtp_config['password'], 
            smtp_host=self._smtp_config['host'], 
            smtp_port=self._smtp_config['port'],
            smtp_ssl=self._smtp_config['ssl'],
            smtp_tls=self._smtp_config['tls'],
        )
        logger.debug('smtp_able: {}'.format(smtp_server.smtp_able()))

        size = os.path.getsize(attachment)
        logger.debug('size of "{}": {:.2}MB'.format(os.path.basename(attachment), size / 1048576))

        if self._mail_config['default_cc'] and needs_cc:
            smtp_server.send_mail('{}@{}'.format(user_id, self._mail_config['default_domain']), mail, cc='{}@{}'.format(self._mail_config['default_cc'], self._mail_config['default_domain']))
        else:
            smtp_server.send_mail('{}@{}'.format(user_id, self._mail_config['default_domain']), mail)
