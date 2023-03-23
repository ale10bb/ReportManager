# -*- coding: UTF-8 -*-
import os
import sys
import logging
import datetime
import zmail
from email.header import Header
from email.utils import formataddr, parseaddr
from . import mysql
from .types import *


class Mail:
    ''' zmail的封装客户端，实现邮件收发
    '''
    _pop3_config = {}
    _smtp_config = {}
    _default_domain = ''
    _default_cc = ''

    def __init__(self, pop3_config: dict | None = None, smtp_config: dict | None = None, default_domain: str = 'example.com', default_cc: str = ''):
        ''' 初始化mail的配置

        Args:
            pop3_config: 需包含'username'、'password'、'host'、'port'、'ssl'、'tls'
            smtp_config: 需包含'username'、'password'、'host'、'port'、'ssl'、'tls'
            default_domain: 白名单邮箱域名
            default_cc: 默认抄送者

        Raises:
            ValueError/TypeError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)

        # pop3，连接失败则抛出异常
        if not pop3_config:
            pop3_config = {}
        if not zmail.server(
            username=pop3_config.setdefault('username', 'rm@example.com'),
            password=pop3_config.setdefault('password', 'rm'),
            pop_host=pop3_config.setdefault('host', 'example.com'),
            pop_port=pop3_config.setdefault('port', 110),
            pop_ssl=pop3_config.setdefault('ssl', False),
            pop_tls=pop3_config.setdefault('tls', False),
        ).pop_able():
            raise ValueError('Failed to login POP3 Server.')
        self._pop3_config = pop3_config
        logger.info('POP3 configration (%s) confirmed.',
                    pop3_config['username'])

        # smtp，连接失败则抛出异常
        if not smtp_config:
            smtp_config = {}
        if not zmail.server(
            username=smtp_config.setdefault('username', 'rm@example.com'),
            password=smtp_config.setdefault('password', 'rm'),
            smtp_host=smtp_config.setdefault('host', 'example.com'),
            smtp_port=smtp_config.setdefault('port', 110),
            smtp_ssl=smtp_config.setdefault('ssl', False),
            smtp_tls=smtp_config.setdefault('tls', False),
        ).smtp_able():
            raise ValueError('Failed to login SMTP Server.')
        self._smtp_config = smtp_config
        logger.info('SMTP configration (%s) confirmed.',
                    smtp_config['username'])

        # 其他邮件设置
        if not isinstance(default_domain, str):
            raise TypeError('invalid arg: default_domain')
        self._default_domain = default_domain
        logger.info('default_domain: %s', self._default_domain)
        if not isinstance(default_cc, str):
            raise TypeError('invalid arg: default_cc')
        self._default_cc = f"{default_cc}@{default_domain}"
        logger.info('default_cc: %s', self._default_cc)

    def receive(self, work_path: str, keywords: dict[str, str]) -> list[Parsed_Mail]:
        ''' 按照{keywords}指定的关键词拉取邮件，并将原始邮件和附件存放在{work_path}

        Args:
            work_path: 临时存放邮件的位置
            keywords: {'submit': (str), 'finish': (str)}；默认为[提交审核]和[完成审核]

        Returns:
            list[Parsed_Mail]

        Raises:
            RuntimeError: 如果POP3服务器连接失败
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'temp_path': work_path, 'keywords': keywords
        })
        pop3_server = zmail.server(
            username=self._pop3_config['username'],
            password=self._pop3_config['password'],
            pop_host=self._pop3_config['host'],
            pop_port=self._pop3_config['port'],
            pop_ssl=self._pop3_config['ssl'],
            pop_tls=self._pop3_config['tls'],
        )
        if not pop3_server.pop_able():
            logger.error('pop3_server unable')
            raise RuntimeError('POP3 server connection failed.')

        ret: list[Parsed_Mail] = []
        for operator in ['submit', 'finish']:
            mails = pop3_server.get_mails(
                subject=keywords[operator],
                sender=self._default_domain,
            )
            logger.debug('%s elements in "%s"', len(mails), keywords[operator])
            # 反向处理邮件，当发生重复时按最后一份处理
            for mail in reversed(mails):
                parsed_mail: Parsed_Mail = {
                    'operator': operator,
                    'keyword': keywords[operator],
                    'timestamp': int(mail['date'].timestamp()),
                    'from_': parseaddr(mail['from'])[1],
                    'subject': mail['subject'],
                    'content': mail['content_text'][0],
                    'temp_path': ''
                }
                parsed_mail['temp_path'] = os.path.join(
                    work_path,
                    '{}_{}_'.format(
                        datetime.datetime.now().timestamp(),
                        parsed_mail['from_'].split('@')[0]
                    )
                )
                os.mkdir(parsed_mail['temp_path'])
                logger.info('saving eml to "%s"', parsed_mail['temp_path'])
                zmail.save(
                    mail,
                    f"{operator}.eml",
                    target_path=parsed_mail['temp_path'],
                    overwrite=True,
                )
                os.mkdir(os.path.join(
                    parsed_mail['temp_path'], 'attachments'))
                zmail.save_attachment(
                    mail,
                    target_path=os.path.join(
                        parsed_mail['temp_path'], 'attachments'),
                    overwrite=True,
                )
                ret.append(parsed_mail)
                pop3_server.delete(mail['id'])
                logger.debug('deleted %s', mail['id'])

        logger.debug('return: %s', ret)
        return ret

    def read(self, temp_path: str) -> Parsed_Mail | None:
        ''' 在{temp_path}中读取eml文件

        Args:
            temp_path: 临时存放邮件的位置

        Returns:
            Parsed_Mail | None
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {'temp_path': temp_path})
        if os.path.exists(os.path.join(temp_path, 'submit.eml')):
            operator = 'submit'
            mail = zmail.read(os.path.join(temp_path, 'submit.eml'))
        elif os.path.exists(os.path.join(temp_path, 'finish.eml')):
            operator = 'finish'
            mail = zmail.read(os.path.join(temp_path, 'finish.eml'))
        else:
            return None
        parsed_mail: Parsed_Mail = {
            'operator': operator,
            'keyword': '',
            'timestamp': int(mail['date'].timestamp()),
            'from_': parseaddr(mail['from'])[1],
            'subject': mail['subject'],
            'content': mail['content_text'][0],
            'temp_path': temp_path,
        }
        if not os.path.exists(os.path.join(temp_path, 'attachments')):
            os.mkdir(os.path.join(temp_path, 'attachments'))
        zmail.save_attachment(
            mail,
            target_path=os.path.join(temp_path, 'attachments'),
            overwrite=True,
        )

        logger.debug('return: %s', parsed_mail)
        return parsed_mail

    def send(self, recipient: str, subject: str, content: str, attachments: list[str] | None = None, needs_cc: bool = False, to_stdout: bool = False):
        ''' 发送邮件

        Args:
            recipient: 对象邮箱
            subject: 邮件主题
            content: 邮件内容
            attachments: 附件文件路径
            needs_cc: 是否抄送管理员
            to_stdout: 是否将邮件重定向到stdout
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'recipient': recipient,
            'subject': subject,
            'content': content,
            'attachments': attachments,
            'needs_cc': needs_cc,
            'to_stdout': to_stdout,
        })

        if not attachments:
            attachments = []
        for attachment in attachments:
            logger.debug('size of "{}": {:.2}MB'.format(
                os.path.basename(attachment), os.path.getsize(attachment) / 1048576))

        mail = {
            'subject': subject,
            'from': formataddr((Header('审核管理机器人', 'utf-8').encode(), self._smtp_config['username'])),
            'content_text': content,
            'attachments': attachments
        }
        if to_stdout:
            logger.warning('redirect to stdout and return')
            return

        try:
            smtp_server = zmail.server(
                username=self._smtp_config['username'],
                password=self._smtp_config['password'],
                smtp_host=self._smtp_config['host'],
                smtp_port=self._smtp_config['port'],
                smtp_ssl=self._smtp_config['ssl'],
                smtp_tls=self._smtp_config['tls'],
            )
            if self._default_cc and needs_cc:
                smtp_server.send_mail([recipient], mail, cc=self._default_cc)
            else:
                smtp_server.send_mail([recipient], mail)
        except:
            logger.error('send_mail error', exc_info=True)
        finally:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            mysql.t_log.add_message(
                'mail',
                recipient,
                subject,
                content,
                str(exc_value) if exc_type else '',
            )
