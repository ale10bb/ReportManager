# -*- coding: UTF-8 -*-
''' log*表增删改查逻辑
'''
from typing import Literal
import logging
import json
from .client import Transaction
from ..types import *


def add_mail(warnings: list[str], err: str | None, parsed_mail: Parsed_Mail, content: Content, attachment: Attachment):
    ''' 向log_mail中插入操作日志

    Args:
        warnings: 告警信息
        err: 错误信息
        parsed_mail: 校验结果
        content: 校验结果
        attachment: 校验结果
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'warnings': warnings,
        'err': err,
        'parsed_mail': parsed_mail,
        'content': content,
        'attachment': attachment,
    })

    with Transaction() as cursor:
        cursor.execute('''
            INSERT INTO log_mail (operator, keyword, error, warnings, mail, content, attachment)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
            parsed_mail['operator'],
            parsed_mail['keyword'],
            err,
            json.dumps(warnings, ensure_ascii=False),
            json.dumps(parsed_mail, ensure_ascii=False),
            json.dumps(content, ensure_ascii=False),
            json.dumps(attachment, ensure_ascii=False),
        )
        )


def add_manage(ip: str, user: str | None, user_agent: str, url: str, param: dict):
    ''' 向log_manage中插入操作日志

    Args:
        ip: 操作人IP
        user: 操作人
        user_agent: UA
        url: 模块路径
        param: 模块参数
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'ip': ip,
        'user': user,
        'user_agent': user_agent,
        'url': url,
        'param': param
    })

    with Transaction() as cursor:
        cursor.execute('''
            INSERT INTO log_manage (ip, user, user_agent, url, param)
            VALUES (INET6_ATON(%s), %s, %s, %s, %s)
            ''', (ip, user, user_agent, url, json.dumps(param, ensure_ascii=False))
        )


def add_message(sender: Literal['mail', 'wxwork', 'dingtalk'], receiver: str, subject: str, content: str, result: str):
    ''' 向log_message中插入操作日志

    Args:
        sender: 消息源（类型）
        receiver: 发送对象
        subject: 消息标题
        content: 消息内容
        result: 发送结果
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'sender': sender,
        'receiver': receiver,
        'subject': subject,
        'content': content,
        'result': result,
    })

    with Transaction() as cursor:
        cursor.execute('''
            INSERT INTO log_message (sender, receiver, subject, content, result)
            VALUES (%s, %s, %s, %s, %s)
            ''', (sender, receiver, subject, content, result)
        )
