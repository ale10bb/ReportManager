# -*- coding: UTF-8 -*-
import os
import logging
import datetime
import zmail
from email.header import Header
from email.utils import formataddr, parseaddr
import requests
from . import var

def init(pop3_config:dict={}, smtp_config:dict={}, mail_config:dict={}):
    ''' 初始化mail的配置

    Args:
        pop3_config(dict): 需包含'username'、'password'、'host'、'port'、'ssl'、'tls'
        smtp_config(dict): 需包含'username'、'password'、'host'、'port'、'ssl'、'tls'
        mail_config(dict): 需包含'default_domain'、'default_cc'、'max_attachments_size'、'large_attachment_handler'

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
    var.pop3_config = pop3_config
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
    var.smtp_config = smtp_config
    logger.info('SMTP configration ({}) confirmed.'.format(smtp_config['username']))

    # 其他邮件设置
    assert type(mail_config.setdefault('default_domain', 'example.com')) == str, 'invalid arg: mail_config.default_domain'
    logger.info('default_domain: {}'.format(mail_config['default_domain']))
    assert type(mail_config.setdefault('default_cc', 'example.com')) == str, 'invalid arg: mail_config.default_cc'
    logger.info('default_cc: {}'.format(mail_config['default_cc']))
    assert type(mail_config.setdefault('max_attachments_size', 25)) == int, 'invalid arg: mail_config.max_attachments_size'
    logger.info('max_attachments_size: {}'.format(mail_config['max_attachments_size']))
    if mail_config.setdefault('large_attachment_handler', ''):
        try:
            with open(os.path.join('res', 'test_win32.doc'),'rb') as f:
                files = {'attachment': f}
                r = requests.post(mail_config['large_attachment_handler'], files=files, timeout=60).json()
            assert not r['result'], r['err']
            assert len(r['data']) == 1
            assert r['data'][0]['name'] == 'test_win32.doc'
            assert requests.head(r['data'][0]['url']).status_code == 200
            logger.info('large_attachment_handler: {}'.format(mail_config['large_attachment_handler']))
        except:
            logger.warning('invalid arg: mail_config.large_attachment_handler', exc_info=True)
            mail_config['large_attachment_handler'] = ''
    var.mail_config = mail_config


def receive(temp_path:str, keywords:dict=None, eml_path:str='') -> list:
    ''' 按照{keywords}指定的关键词拉取邮件，并将原始邮件和附件存放在{temp_path}。传入{eml_path}时，不通过POP3拉取邮件，而是读取本地eml文件。

    Args:
        temp_path(str): 临时存放邮件的位置；
        keywords: {'submit': (str), 'finish': (str)}；默认为[提交审核]和[完成审核]；
        eml_path(str): 本地eml文件的路径

    Returns:
        [{xxx}(check_results), ...]

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'temp_path': temp_path, 'keywords': keywords, 'eml_path': eml_path}))
    assert os.path.isdir(temp_path), 'invalid arg: temp_path'
    if not keywords:
        keywords = {'submit': '[提交审核]', 'finish': '[完成审核]'}
    assert (type(keywords.setdefault('submit', '[提交审核]')) == str and 
        type(keywords.setdefault('finish', '[完成审核]')) == str
    ), 'invalid arg: keywords'
    if eml_path:
        assert os.path.isfile(eml_path), 'invalid arg: eml_path'

    if not eml_path:
        pop3_server = zmail.server(
            username=var.pop3_config['username'], 
            password=var.pop3_config['password'], 
            pop_host=var.pop3_config['host'], 
            pop_port=var.pop3_config['port'],
            pop_ssl=var.pop3_config['ssl'],
            pop_tls=var.pop3_config['tls'],
        )
        logger.debug('pop_able: {}'.format(pop3_server.pop_able()))

    ret = []
    for operator in ['submit', 'finish']:
        if eml_path:
            eml = zmail.read(eml_path)
            if keywords[operator] in eml['subject']:
                mails = [eml]
            else:
                mails = []
        else:
            mails = pop3_server.get_mails(subject=keywords[operator])
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
            if not eml_path:
                pop3_server.delete(mail['id'])
                logger.debug('deleted {}'.format(mail['id']))

    logger.debug('return: {}'.format(ret))
    return ret


def send(user_id:str, subject:str, content:str='', attachment:str='', needs_cc:bool=False, to_stdout=False):
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
        'from': formataddr((Header('审核管理机器人', 'utf-8').encode(), var.smtp_config['username'])), 
        'content_text': content, 
        'attachments': [attachment]
    }
    logger.debug('mail: {}'.format(mail))

    if to_stdout:
        logger.warning('redirect to stdout and return')
        return

    smtp_server = zmail.server(
        username=var.smtp_config['username'], 
        password=var.smtp_config['password'], 
        smtp_host=var.smtp_config['host'], 
        smtp_port=var.smtp_config['port'],
        smtp_ssl=var.smtp_config['ssl'],
        smtp_tls=var.smtp_config['tls'],
    )
    logger.debug('smtp_able: {}'.format(smtp_server.smtp_able()))

    size = os.path.getsize(attachment)
    logger.debug('size of "{}": {:.2}MB'.format(os.path.basename(attachment), size / 1048576))
    if size > var.mail_config['max_attachments_size'] * 1048576:
        try:
            assert var.mail_config['large_attachment_handler'], 'large_attachment_handler not set.'
            with open(attachment,'rb') as f:
                files = {'attachment': f}
                r = requests.post(var.mail_config['large_attachment_handler'], files=files, timeout=600).json()
                assert not r['result'], r['err']
                mail['content_text'] += (
                    '\r\n==== 警告 ====\r\n'
                    '附件过大无法发送，已在线暂存，有效期{}天。下载地址：\r\n{}'.format(r['data']['expire'], r['data']['url'])
                )
                logger.info('large_attachment_url: {}'.format(r['data']['url']))
        except:
            mail['content_text'] += (
                '\r\n==== 警告 ====\r\n'
                '附件过大无法发送，请联系管理员处理。'
            )
            mail['attachments'] = []
            logger.error('large_attachment_handler error', exc_info=True)

    if var.mail_config['default_cc'] and needs_cc:
        smtp_server.send_mail('{}@{}'.format(user_id, var.mail_config['default_domain']), mail, cc='{}@{}'.format(var.mail_config['default_cc'], var.mail_config['default_domain']))
    else:
        smtp_server.send_mail('{}@{}'.format(user_id, var.mail_config['default_domain']), mail)


def valid_domain(address:str) -> bool:
    ''' 检查邮件地址的域名是否为default_domain。

    Args:
        address(str): 邮件原始from地址

    Returns:
        bool

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'address': address}))
    assert type(address) == str, 'invalid arg: address'

    return parseaddr(address)[1].split('@')[1] == var.mail_config['default_domain']
