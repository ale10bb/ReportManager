# -*- coding: UTF-8 -*-
''' 检查邮件及附件的有效性
'''
from typing import Literal
import logging
import argparse
import re
from . import mysql
from . import document
from .types import *


def check_mail_content(from_: str, subject: str, content: str, timestamp: int) -> Checked_Mail_Content:
    ''' 读取{mail_content}中的内容，获取发件人和指令，处理完毕时返回警告信息及处理结果{Checked_Mail_Content}

    Args:
        from_: 邮件发件人
        subject: 邮件标题
        content: 邮件内容
        timestamp: 邮件时间戳

    Returns:
        Checked_Mail_Content

    Raises:
        ValueError: 如果发件人非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'from_': from_, 'subject': subject, 'content': content
    })
    ret: Checked_Mail_Content = {'warnings': [], 'content': {
        'timestamp': timestamp, 'user_id': '', 'name': '', 'urgent': False, 'excludes': [], 'force': ''
    }}
    # 从from中读取发信人并校验，校验内容为：
    #   发件人邮箱必须位于user表中
    #   如果subject中包含"--sender userid"参数，则在检验userid有效后，将其作为发信人
    # 预期结果：
    #   流程正常完成时，在ret中填入user_id、name
    #   校验失败时，抛出ValueError，包含发件人邮箱
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s',
        '--sender',
        nargs='?',
        const='',
        default='',
        action='store'
    )
    parser.add_argument('others', nargs='*')
    args = parser.parse_args(re.sub(' +', ' ', subject.strip()).split(' '))
    if args.sender:
        user_id: str = args.sender
        logger.info('manual sender: %s', user_id)
        user_record = mysql.t_user.fetch(user_id)
    else:
        result = mysql.t_user.search(email=from_)
        if len(result) == 1:
            user_record = result[0]
        else:
            user_record = None
    if user_record:
        ret['content']['user_id'] = user_record['id']
        ret['content']['name'] = user_record['name']
        logger.info('sender: %s/%s', user_record['id'], user_record['name'])
    else:
        raise ValueError(f"Invalid sender \"{from_}\"")

    # 从content中指令并校验，校验内容为：
    #   是否输入“加急” & 输入内容是否合法
    #   是否输入“组员” & 组员是否具备审核资格
    #   是否输入“指定” & 是否同时设置了“加急” & 指定是否具备审核资格 & 指定是否为发件人或组员
    # 预期结果：
    #   流程正常完成时，在ret中填入urgent、excludes、force。非法指令将被忽略并使用默认值（见下）
    urgent = False
    excludes = []
    force = ''
    # 循环读取content中的所有行，尝试校验指令
    # 注意：如果指令重复，将丢弃上一条结果，将结果重置为默认值并处理新行
    for line in content.splitlines():
        # 有人习惯打冒号、全角逗号、半角逗号，一并替换成合法值
        line = re.sub(' +|：', ' ', line.strip())
        line = re.sub('，|,', '、', line.strip())
        # 替换常见错误输入后，按第一个空格分隔1次，长度不为2的指令行将被忽略
        cmds = line.split(' ', 1)
        if len(cmds) != 2:
            continue
        logger.debug('cmds: %s', cmds)
        if cmds[0] == '加急':
            urgent = False
            if cmds[1] == '是' or cmds[1] == '1':
                urgent = True
                logger.info('urgent: %s', urgent)
            else:
                urgent = False
            continue
        if cmds[0] == '组员':
            excludes = []
            # 检查组员并修改为user_id
            for member in cmds[1].split('、'):
                user = mysql.t_user.fetch(member)
                if user and user['role'] == 1:
                    excludes.append(user['id'])
                else:
                    users = mysql.t_user.search(name=member, only_reviewer=True)
                    if len(users) == 1:
                        excludes.append(users[0]['id'])
            excludes = list(set(excludes))
            logger.info('excludes: %s', excludes)
            continue
        if cmds[0] == '指定':
            # 检查指定并修改为主键
            user = mysql.t_user.fetch(cmds[1])
            if user and user['role'] == 1:
                force = user['id']
            else:
                users = mysql.t_user.search(name=cmds[1], only_reviewer=True)
                if len(users) == 1:
                    force = users[0]['id']
                else:
                    ret['warnings'].append(f"已去除无效指定 \"{cmds[1]}\"")
            logger.info('force: %s', force)
            continue
    # 考虑到指令重复、指令之间有因果关系等情况，仅当读取完所有行之后，再进行总体校验及写入ret
    # “指定”回滚逻辑：
    #   指定了自己或组员
    if force == ret['content']['user_id'] or force in excludes:
        ret['warnings'].append(f"指定\"{force}\"失败: 项目相关人员")
        logger.warning('rallbacked force due to "in excludes"')
        force = ''
    ret['content']['urgent'] = urgent
    ret['content']['excludes'] = excludes
    ret['content']['force'] = force
    logger.debug('return: %s', ret)
    return ret


def check_mail_attachment(work_path: str, operator: Literal['submit', 'finish']) -> Checked_Mail_Attachment:
    ''' 读取存放在{work_path}中的附件，根据操作符获取文档信息。处理完毕后，返回attachment信息

    Args:
        work_path：工作目录（存放附件的目录）
        operator: 操作符（submit/finish）

    Returns:
        Checked_Mail_Attachment

    Raises:
        ValueError: 如果未读取到有效文档
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'work_path': work_path, 'operator': operator})
    ret: Checked_Mail_Attachment = {
        'warnings': [],
        'attachment': {'pages': 0, 'company': '', 'names': {}},
    }

    # 读取工作目录中的所有文档
    # 传入的操作符用于控制读取逻辑
    # 用返回值的names参数作为标记，无names说明读取失败，此时抛出ValueError异常
    if operator == 'submit':
        ret['attachment'] = document.read_document(work_path)
    if operator == 'finish':
        ret['attachment'] = document.read_XT13(work_path)
    if not ret['attachment']['names']:
        raise ValueError('No valid documents')
    logger.debug('return: %s', ret)
    return ret
