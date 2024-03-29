# -*- coding: UTF-8 -*-
''' user表增删改查逻辑（仅提供修改pages的接口）

注：此处不增删user表，要增删的话，目前直接修改数据库
'''
from typing import Literal
import logging
from .client import Transaction, Selection
from ..types import *


def search(**kwargs) -> list[UserItem]:
    ''' 根据传入的kwargs，搜索user表内容，支持参数包括：

    1. id(str): 按用户id精准查询
    2. name(str)/phone(str)/email(str): 按姓名、手机、邮箱模糊查询
    3. only_reviewer(bool): 仅查询审核人(role=1)

    Returns:
        list[UserItem]
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'kwargs': kwargs})

    ret: list[UserItem] = []
    with Selection() as cursor:
        params = []
        condition = ''
        for key, value in kwargs.items():
            if key == 'id':
                params.append(value)
                condition += f' AND {key} = %s'
            elif key in ['name', 'phone', 'email']:
                params.append(f'%{value}%')
                condition += f' AND {key} LIKE %s'
            elif key == 'only_reviewer':
                condition += ' AND role = 1'
        logger.debug('params: %s', params)
        logger.debug('condition: %s', condition)
        sql = f"SELECT id, name, phone, email, role, status FROM user WHERE available = 1{condition}"
        cursor.execute(sql, params)
        keys = ['id', 'name', 'phone', 'email', 'role', 'status']
        for row in cursor.fetchall():
            logger.debug('row: %s', row)
            ret.append(UserItem(zip(keys, row)))
    logger.debug('return: %s', ret)
    return ret


def fetch(user_id: str) -> UserItem | None:
    ''' 按照user_id获取user表内容

    Args:
        user_id: 用户ID

    Returns:
        UserItem | None
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'user_id': user_id})

    ret: UserItem | None = None
    with Selection() as cursor:
        sql = '''
            SELECT id, name, phone, email, role, status
            FROM user
            WHERE available = 1 AND id = %s
        '''
        cursor.execute(sql, (user_id,))
        row = cursor.fetchone()
        if row:
            logger.debug('row: %s', row)
            keys = ['id', 'name', 'phone', 'email', 'role', 'status']
            ret = UserItem(zip(keys, row))
    logger.debug('return: %s', ret)
    return ret


def __contains__(user_id: str) -> bool:
    ''' 检查user表中是否存在{user_id}

    Args:
        user_id: 用户ID

    Returns:
        bool: {user_id}存在返回True，否则返回False
    '''
    return bool(fetch(user_id))


def pop(count: int = 1, excludes: list[str] | None = None, urgent: bool = False, hide_busy: bool = True) -> list[QueueItem]:
    ''' 根据条件获取下{count}个审核人

    Args:
        count: 需要获取的审核人数量
        excludes: 排除的审核人ID
        urgent: 是否降权status=1的审核人
        hide_busy: 是否隐藏status=2的审核人

    Returns:
        list[QueueItem]：长度为{count}的列表，在UserItem之上增加priority、pages_diff、current、skipped键
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'count': count, 'excludes': excludes, 'urgent': urgent, 'hide_busy': hide_busy
    })
    if not excludes:
        excludes = []

    ret: list[QueueItem] = []
    with Selection() as cursor:
        # 选择审核人，按工作量（当前报告、当前页数）排序
        # 前一个完成审核的人赋予skipped参数，默认降权到最后一个
        cursor.execute('''
            SELECT id, name, phone, email, role, status, (
                    pages - (SELECT MIN(pages) AS min_pages FROM user WHERE user.available = 1 AND user.role = 1)
                ) AS pages_diff, IFNULL(current, 0) AS current, IF(
                    id = (
                        SELECT latest_history.reviewerid
                        FROM (SELECT reviewerid, end FROM history ORDER BY id DESC LIMIT 1) AS latest_history
                        WHERE NOT EXISTS (SELECT 1 FROM current WHERE current.start > latest_history.end AND current.reviewerid != '')
                    ), 1, 0
                ) AS skipped
            FROM user LEFT JOIN (
                    SELECT reviewerid, COUNT(1) AS current
                    FROM current
                    GROUP BY reviewerid 
                ) AS temp_count ON user.id = temp_count.reviewerid
            WHERE available = 1 AND role = 1
            ORDER BY skipped, current, pages_diff
        ''')
        keys = ['id', 'name', 'phone', 'email', 'role',
                'status', 'pages_diff', 'current', 'skipped']
        for row in cursor.fetchall():
            logger.debug('row: %s', row)
            ret.append(QueueItem(zip(keys, row)))

    ret = [item for item in ret if item['id'] not in excludes]
    if urgent:
        # 提升status=0(空闲)的审核人优先级
        ret = \
            [item for item in ret if item['status'] == 0] + \
            [item for item in ret if item['status'] != 0]
    if hide_busy:
        # 仅筛选列表中status=0和status=1的审核人
        ret = [item for item in ret if item['status'] != 2]
    for idx, queue_item in enumerate(ret, start=1):
        queue_item['priority'] = idx

    logger.debug('return: %s', ret[0:count])
    return ret[0:count]


def set_status(user_id: str, status: Literal[0, 1, 2]):
    ''' 设置忙碌状态status

    Args:
        user_id: 用户ID
        status: 状态
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'user_id': user_id, 'status': status})

    with Transaction() as cursor:
        sql = '''
            UPDATE user
            SET status = %s, status_since = NOW() 
            WHERE id = %s
        '''
        cursor.execute(sql, (status, user_id))


def reset_status(days: int = 7):
    ''' 重置超时(超过{days})的忙碌状态status

    Args:
        days: 超时时间
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'days': days})

    with Transaction() as cursor:
        sql = '''
            UPDATE user
            SET status = 0, status_since = NOW() 
            WHERE status != 0 AND DATEDIFF(NOW(), status_since) >= %s
        '''
        cursor.execute(sql, (days,))
