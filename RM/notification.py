# -*- coding: UTF-8 -*-
import logging
import datetime
import json
from . import mysql

def build_submit_mail(record:tuple, warnings:list) -> dict:
    ''' 根据传入的参数，生成邮件内容。

    Args:
        record(tuple): 处理完毕后的target结果记录
        warnings(list): 处理过程中产生的告警信息

    Returns:
        {'subject': (str), 'content': (str)}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'record': record, 'warnings': warnings}))
    assert type(record) == tuple and len(record) == 11, 'invalid arg: record'
    assert type(warnings) == list, 'invalid arg: warnings'

    # 邮件内容
    ret = {'subject': '', 'content': ''}
    urgent = '是' if record[8] else '否'
    codes = json.loads(record[10])
    ret['subject'] = '[报告分配审核] {}'.format('+'.join(codes.keys()))
    ret['content'] = (
        '项目名称：\r\n'
        '{}\r\n' 
        '委托单位：\r\n'
        '  - {}\r\n'
        '编写人：{}\r\n'
        '页数：{}\r\n'
        '加急：{}\r\n'.format(
            '\r\n'.join(['  - {}：{}'.format(key, codes[key]) for key in codes]), 
            record[9], 
            record[2], 
            record[7], 
            urgent
        )
    )

    logger.debug('return: {}'.format(ret))
    return ret


def build_submit_dingtalk(record:tuple, warnings:list) -> dict:
    ''' 根据传入的参数，生成钉钉通知内容。

    Args:
        record(tuple): 处理完毕后的target结果记录
        warnings(list): 处理过程中产生的告警信息

    Returns:
        {'subject': (str), 'content': (str)}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'record': record, 'warnings': warnings}))
    assert type(record) == tuple and len(record) == 11, 'invalid arg: record'
    assert type(warnings) == list, 'invalid arg: warnings'

    # 钉钉通知内容
    ret = {'subject': '报告分配审核', 'content': ''}
    urgent = '是' if record[8] else '否'
    ret['content'] = (
        '**项目编号（分配审核）**\n\n'
        '{}\n\n'
        '**页数**\n\n'
        '- {}\n\n'
        '**加急**\n\n'
        '- {}\n\n'
        '**分配**\n\n'
        '- {} -> @{}\n\n'.format(
            '\n'.join(['- ' + code for code in json.loads(record[10]).keys()]), 
            record[7],
            urgent, 
            record[2], 
            mysql.t_user.fetch(record[3])[2]
        )
    )
    logger.debug('build result: {}'.format(ret))
    if warnings:
        ret['content'] += (
            '> ###### Warnings:\n\n' + '\n'.join(['> ###### - ' + warning for warning in warnings]) + '\n\n'
        )

    logger.debug('return: {}'.format(ret))
    return ret


def build_submit_wxwork(record:tuple, warnings:list) -> dict:
    ''' 根据传入的参数，生成企业微信通知内容。

    Args:
        record(tuple): 处理完毕后的target结果记录
        warnings(list): 处理过程中产生的告警信息

    Returns:
        {'subject': '', 'content': (str)}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'record': record, 'warnings': warnings}))
    assert type(record) == tuple and len(record) == 11, 'invalid arg: record'
    assert type(warnings) == list, 'invalid arg: warnings'

    # 企业微信通知内容
    ret = {'subject': '', 'content': ''}
    urgent = '是' if record[8] else '否'
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
            '\n'.join(['· ' + code for code in json.loads(record[10]).keys()]), 
            record[7],
            urgent, 
            record[2], 
            record[4]
        )
    )
    if warnings:
        ret['content'] += (
            '\n\nWarnings:\n' + '\n'.join(['· ' + warning for warning in warnings])
        )

    logger.debug('return: {}'.format(ret))
    return ret


def build_finish_mail(record:tuple, warnings:list) -> dict:
    ''' 根据传入的参数，生成邮件通知内容。

    Args:
        record(tuple): 处理完毕后的target结果记录
        warnings(list): 处理过程中产生的告警信息

    Returns:
        {'subject': (str), 'content': (str)}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'record': record, 'warnings': warnings}))
    assert type(record) == tuple and len(record) == 11, 'invalid arg: record'
    assert type(warnings) == list, 'invalid arg: warnings'
    
    # 邮件内容
    ret = {'subject': '', 'content': ''}
    urgent = '是' if record[8] else '否'
    codes = json.loads(record[10])
    ret['subject'] = '[报告完成审核] {}'.format('+'.join(codes.keys()))
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
            '\r\n'.join(['  - {}：{}'.format(key, codes[key]) for key in codes]), 
            record[9], 
            record[2], 
            record[4], 
            record[7], 
            urgent, 
            datetime.datetime.fromtimestamp(record[5]).strftime("%Y-%m-%d %H:%M"),
            datetime.datetime.fromtimestamp(record[6]).strftime("%Y-%m-%d %H:%M")
        )
    )

    logger.debug('return: {}'.format(ret))
    return ret


def build_finish_dingtalk(record:tuple, warnings:list) -> dict:
    ''' 根据传入的参数，生成钉钉通知内容。

    Args:
        record(tuple): 处理完毕后的target结果记录
        warnings(list): 处理过程中产生的告警信息

    Returns:
        {'subject': (str), 'content': (str)}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'record': record, 'warnings': warnings}))
    assert type(record) == tuple and len(record) == 11, 'invalid arg: record'
    assert type(warnings) == list, 'invalid arg: warnings'
    
    # 钉钉通知内容
    ret = {'subject': '报告完成审核', 'content': ''}
    ret['content'] = (
        '**项目编号（完成审核）**\n\n'
        '{}\n\n'
        '**交还**\n\n'
        '- @{} <- {}\n\n'.format(
            '\n'.join(['- ' + code for code in json.loads(record[10]).keys()]), 
            mysql.t_user.fetch(record[1])[2],
            record[4]
        )
    )
    if warnings:
        ret['content'] += (
            '> ###### Warnings:\n\n' + '\n'.join(['> ###### - ' + warning for warning in warnings]) + '\n\n'
        )

    logger.debug('return: {}'.format(ret))
    return ret


def build_finish_wxwork(record:tuple, warnings:list) -> dict:
    ''' 根据传入的参数，生成企业微信通知内容。

    Args:
        record(tuple): 处理完毕后的target结果记录
        warnings(list): 处理过程中产生的告警信息

    Returns:
        {'subject': '', 'content': (str)}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'record': record, 'warnings': warnings}))
    assert type(record) == tuple and len(record) == 11, 'invalid arg: record'
    assert type(warnings) == list, 'invalid arg: warnings'

    # 企业微信通知内容
    ret = {'subject': '', 'content': ''}
    ret['content'] = (
        '==== 报告完成审核 ====\n\n'
        '项目编号\n'
        '{}\n'
        '交还\n'
        '· {} <- {}'.format(
            '\n'.join(['· ' + code for code in json.loads(record[10]).keys()]), 
            record[2], 
            record[4]
        )
    )
    if warnings:
        ret['content'] += (
            '\n\nWarnings:\n' + '\n'.join(['· ' + warning for warning in warnings])
        )

    logger.debug('return: {}'.format(ret))
    return ret


def build_monthly_projects_mail(user_id:str, names:dict) -> dict:
    ''' 生成指定用户上个月的项目月报，包含上个月提交审核并完成的所有任务。

    Args:
        user_id(str): 用户
        names(dict): 项目名称列表

    Returns:
        {'subject': (str), 'content': (str)}

    Raises:
        TypeError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    if type(user_id) != str:
        raise TypeError('Not a str: user_id.')
    if type(names) != dict:
        raise TypeError('Not a dict: names.')

    ret = {'subject': '', 'content': ''}
    analysis_end = datetime.datetime.now()
    analysis_start = analysis_end - datetime.timedelta(days=30)
    ret['subject'] = '[项目月报] {}'.format(analysis_start.strftime('%Y-%m'))
    ret['content'] = (
        '项目组长：{}\r\n'.format(mysql.t_user.fetch(user_id)[1]) + 
        '在{}至{}之间，你完成的项目共{}个，记得及时将以下项目归档：\r\n\r\n'.format(
            analysis_start.strftime('%Y-%m-%d'), 
            analysis_end.strftime('%Y-%m-%d'), 
            len(names)
        ) + 
        '\r\n'.join(['- {}: {}'.format(key, names[key]) for key in names.keys()])
    )

    return ret
