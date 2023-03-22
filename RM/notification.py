# -*- coding: UTF-8 -*-
from typing import TypedDict
import logging
import datetime
from . import mysql
from .mysql.types import CurrentRecord, HistoryRecord


class Built_Message(TypedDict):
    subject: str
    content: str


def build_submit_mail(record: CurrentRecord, warnings: list[str]) -> Built_Message:
    ''' 根据传入的参数，生成邮件内容。

    Args:
        record(CurrentRecord): 对象结果记录
        warnings(list[str]): 处理过程中产生的告警信息

    Returns:
        Built_Message
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'record': record, 'warnings': warnings})

    # 邮件内容
    ret: Built_Message = {'subject': '', 'content': ''}
    urgent = '是' if record['urgent'] else '否'
    ret['subject'] = '[报告分配审核] {}'.format('+'.join(record['names']))
    ret['content'] = (
        '项目名称：\r\n'
        '{}\r\n'
        '委托单位：\r\n'
        '  - {}\r\n'
        '编写人：{}\r\n'
        '页数：{}\r\n'
        '加急：{}\r\n'.format(
            '\r\n'.join([f"  - {key}：{value}" for key,
                        value in record['names'].items()]),
            record['company'],
            record['authorname'],
            record['pages'],
            urgent
        )
    )

    logger.debug('return: %s', ret)
    return ret


def build_submit_dingtalk(record: CurrentRecord, warnings: list[str]) -> Built_Message:
    ''' 根据传入的参数，生成钉钉通知内容。

    Args:
        record(CurrentRecord): 对象结果记录
        warnings(list[str]): 处理过程中产生的告警信息

    Returns:
        Built_Message
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'record': record, 'warnings': warnings})

    # 钉钉通知内容
    ret: Built_Message = {'subject': '报告分配审核', 'content': ''}
    urgent = '是' if record['urgent'] else '否'
    user = mysql.t_user.fetch(record['reviewerid'])
    ret['content'] = (
        '**项目编号（分配审核）**\n\n'
        '{}\n\n'
        '**页数**\n\n'
        '- {}\n\n'
        '**加急**\n\n'
        '- {}\n\n'
        '**分配**\n\n'
        '- {} -> @{}\n\n'.format(
            '\n'.join(['- ' + code for code in record['names']]),
            record['pages'],
            urgent,
            record['authorname'],
            user['phone'] if user else record['reviewername'],
        )
    )
    if warnings:
        ret['content'] += (
            '> ###### Warnings:\n\n' +
            '\n'.join(['> ###### - ' + warning for warning in warnings]) + '\n\n'
        )

    logger.debug('return: %s', ret)
    return ret


def build_submit_wxwork(record: CurrentRecord, warnings: list[str]) -> Built_Message:
    ''' 根据传入的参数，生成企业微信通知内容。

    Args:
        record(CurrentRecord): 对象结果记录
        warnings(list[str]): 处理过程中产生的告警信息

    Returns:
        Built_Message
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'record': record, 'warnings': warnings})

    # 企业微信通知内容
    ret: Built_Message = {'subject': '', 'content': ''}
    urgent = '是' if record['urgent'] else '否'
    ret['content'] = (
        '==== 报告分配审核 ====\n\n'
        '项目编号\n'
        '{}\n'
        '页数\n'
        '· {}\n'
        '加急\n'
        '· {}\n'
        '分配\n'
        '· {} -> {}'.format(
            '\n'.join(['· ' + code for code in record['names']]),
            record['pages'],
            urgent,
            record['authorname'],
            record['reviewername'],
        )
    )
    if warnings:
        ret['content'] += (
            '\n\nWarnings:\n' +
            '\n'.join(['· ' + warning for warning in warnings])
        )

    logger.debug('return: %s', ret)
    return ret


def build_finish_mail(record: HistoryRecord, warnings: list[str]) -> Built_Message:
    ''' 根据传入的参数，生成邮件通知内容。

    Args:
        record(HistoryRecord): 对象结果记录
        warnings(list[str]): 处理过程中产生的告警信息

    Returns:
        {'subject': (str), 'content': (str)}
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'record': record, 'warnings': warnings})

    # 邮件内容
    ret: Built_Message = {'subject': '', 'content': ''}
    urgent = '是' if record['urgent'] else '否'
    ret['subject'] = '[报告完成审核] {}'.format('+'.join(record['names']))
    ret['content'] = (
        '项目名称：\r\n'
        '{}\r\n'
        '委托单位：\r\n'
        '  - {}\r\n'
        '编写人：{}\r\n'
        '审核人：{}\r\n'
        '页数：{}\r\n'
        '加急：{}\r\n'
        '提交时间：{}\r\n'
        '完成时间：{}'.format(
            '\r\n'.join(['  - {}：{}'.format(key, value)
                        for key, value in record['names'].items()]),
            record['company'],
            record['authorname'],
            record['reviewername'],
            record['pages'],
            urgent,
            datetime.datetime.fromtimestamp(
                record['start']).strftime("%Y-%m-%d %H:%M"),
            datetime.datetime.fromtimestamp(
                record['end']).strftime("%Y-%m-%d %H:%M")
        )
    )

    logger.debug('return: %s', ret)
    return ret


def build_finish_dingtalk(record: HistoryRecord, warnings: list[str]) -> Built_Message:
    ''' 根据传入的参数，生成钉钉通知内容。

    Args:
        record(HistoryRecord): 对象结果记录
        warnings(list[str]): 处理过程中产生的告警信息

    Returns:
        {'subject': (str), 'content': (str)}
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'record': record, 'warnings': warnings})

    # 钉钉通知内容
    ret: Built_Message = {'subject': '报告完成审核', 'content': ''}
    user = mysql.t_user.fetch(record['authorid'])
    ret['content'] = (
        '**项目编号（完成审核）**\n\n'
        '{}\n\n'
        '**交还**\n\n'
        '- @{} <- {}\n\n'.format(
            '\n'.join(['- ' + code for code in record['names']]),
            user['phone'] if user else record['authorname'],
            record['reviewername']
        )
    )
    if warnings:
        ret['content'] += (
            '> ###### Warnings:\n\n' +
            '\n'.join(['> ###### - ' + warning for warning in warnings]) + '\n\n'
        )

    logger.debug('return: %s', ret)
    return ret


def build_finish_wxwork(record: HistoryRecord, warnings: list[str]) -> Built_Message:
    ''' 根据传入的参数，生成企业微信通知内容。

    Args:
        record(HistoryRecord): 对象结果记录
        warnings(list[str]): 处理过程中产生的告警信息

    Returns:
        Built_Message
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'record': record, 'warnings': warnings})

    # 企业微信通知内容
    ret: Built_Message = {'subject': '', 'content': ''}
    ret['content'] = (
        '==== 报告完成审核 ====\n\n'
        '项目编号\n'
        '{}\n'
        '交还\n'
        '· {} <- {}'.format(
            '\n'.join(['· ' + code for code in record['names']]),
            record['authorname'],
            record['reviewername']
        )
    )
    if warnings:
        ret['content'] += (
            '\n\nWarnings:\n' +
            '\n'.join(['· ' + warning for warning in warnings])
        )

    logger.debug('return: %s', ret)
    return ret


# def build_monthly_projects_mail(user_id: str, names: dict) -> dict:
#     ''' 生成指定用户上个月的项目月报，包含上个月提交审核并完成的所有任务。

#     Args:
#         user_id(str): 用户
#         names(dict): 项目名称列表

#     Returns:
#         {'subject': (str), 'content': (str)}

#     Raises:
#         TypeError: 如果参数类型非法
#     '''
#     logger = logging.getLogger(__name__)
#     if type(user_id) != str:
#         raise TypeError('Not a str: user_id.')
#     if type(names) != dict:
#         raise TypeError('Not a dict: names.')

#     ret: Built_Message = {'subject': '', 'content': ''}
#     analysis_end = datetime.datetime.now()
#     analysis_start = analysis_end - datetime.timedelta(days=30)
#     ret['subject'] = '[项目月报] {}'.format(analysis_start.strftime('%Y-%m'))
#     ret['content'] = (
#         '项目组长：{}\r\n'.format(mysql.t_user.fetch(user_id)[1]) +
#         '在{}至{}之间，你完成的项目共{}个，记得及时将以下项目归档：\r\n\r\n'.format(
#             analysis_start.strftime('%Y-%m-%d'),
#             analysis_end.strftime('%Y-%m-%d'),
#             len(names)
#         ) +
#         '\r\n'.join(['- {}: {}'.format(key, names[key])
#                     for key in names.keys()])
#     )

#     return ret
