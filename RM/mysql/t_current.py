# -*- coding: UTF-8 -*-
''' current表增删改查逻辑
'''
import logging
import json
import hashlib
from .client import Transaction, Selection
from . import t_user
from ..types import *


def search(page_index: int = 1, page_size: int = 10, **kwargs) -> Currents:
    ''' 搜索current表中的项目。

    1. 传入code时，按条件模糊查询；支持按“+”分割传入多个code，如"123+345"
    2. 传入authorid/reviewerid时，按条件精准查询

    Args:
        page_index(int): 分页/当前页（可选/默认值1）
        page_size(int): 分页/页大小（可选/默认值10）
        kwargs -> code(str): 项目编号
        kwargs -> authorid(str): 撰写人id（精确查询）
        kwargs -> reviewerid(str): 审核人id（精确查询）

    Returns:
        {"current": list[CurrentRecord], 'total': int}
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'page_index': page_index,
        'page_size': page_size,
        'kwargs': kwargs,
    })

    ret: Currents = {'current': [], 'total': 0}
    with Selection() as cursor:
        params = []
        condition = ''
        for key, value in kwargs.items():
            if key == 'code':
                codes = list(set([f'%{item}%' for item in value.split('+')]))
                params.extend(codes)
                condition += ''.join(
                    [' AND JSON_SEARCH(JSON_KEYS(names), \'one\', %s) IS NOT NULL'] * len(codes))
            if key in ['authorid', 'reviewerid']:
                params.append(value)
                condition += f' AND {key} = %s'
        logger.debug('params: %s', params)
        logger.debug('condition: %s', condition)
        sql = f"SELECT count(1) as count FROM current WHERE 1=1{condition}"
        cursor.execute(sql, params)
        ret['total'] = int(cursor.fetchone()[0])
        sql = f'''
            SELECT c.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(c.start), null, c.pages, c.urgent, c.company, c.names
            FROM current c
            LEFT JOIN user u_a ON c.authorid = u_a.id
            LEFT JOIN user u_r ON c.reviewerid = u_r.id 
            WHERE 1=1{condition}
            LIMIT %s OFFSET %s
        '''
        cursor.execute(sql, params + [page_size, page_size * (page_index - 1)])
        keys = ['id', 'authorid', 'authorname', 'reviewerid', 'reviewername',
                'start', 'end', 'pages', 'urgent', 'company', 'names']
        for row in cursor.fetchall():
            d = CurrentRecord(zip(keys, row))
            d['names'] = json.loads(d['names'])
            d['urgent'] = bool(d['urgent'])
            ret['current'].append(d)
    logger.debug('return: %s', ret)
    return ret


def fetch(current_id: str) -> CurrentRecord | None:
    ''' 按照current_id查询对应项目的信息

    Args:
        current_id(str): (SHA256)项目ID

    Returns:
        CurrentRecord | None
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'current_id': current_id})

    ret: CurrentRecord | None = None
    with Selection() as cursor:
        cursor.execute('''
            SELECT c.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(c.start), null, c.pages, c.urgent, c.company, c.names
            FROM current c
            LEFT JOIN user u_a ON c.authorid = u_a.id
            LEFT JOIN user u_r ON c.reviewerid = u_r.id 
            WHERE c.id = %s
            ''', (current_id,)
        )
        row = cursor.fetchone()
        if row:
            keys = ['id', 'authorid', 'authorname', 'reviewerid', 'reviewername',
                    'start', 'end', 'pages', 'urgent', 'company', 'names']
            ret = CurrentRecord(zip(keys, row))
            ret['names'] = json.loads(ret['names'])
            ret['urgent'] = bool(ret['urgent'])
    logger.debug('return: %s', ret)
    return ret


def fetch_by_name(names: dict[str, str]) -> CurrentRecord | None:
    ''' 按照names查询对应项目的信息

    Args:
        names: {"code": "name", ...}: 项目名称

    Returns:
        CurrentRecord | None
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'names': names})
    return fetch(gen_id(names))


def add(names: dict[str, str], company: str, pages: int, urgent: bool, authorid: str, reviewerid: str, submit_timestamp: int):
    ''' 向current表中添加项目（所有参数均必填）。

    Args:
        names: {"code": "name", ...}
        company: 委托单位
        pages: 页数
        urgent: 是否加急
        authorid: 撰写人ID
        reviewerid: 审核人ID
        submit_timestamp: 提交时间戳
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'names': names,
        'company': company,
        'pages': pages,
        'urgent': urgent,
        'authorid': authorid,
        'reviewerid': reviewerid,
        'submit_timestamp': submit_timestamp,
    })
    current_id = gen_id(names)
    logger.debug('current_id: %s', current_id)

    with Transaction() as cursor:
        cursor.execute('''
            INSERT INTO current (id, names, company, pages, urgent, authorid, reviewerid, start)
            VALUES (%s, %s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s))
            ''', (current_id, json.dumps(names), company, pages, urgent, authorid, reviewerid, submit_timestamp)
        )


def edit(current_id: str, **kwargs):
    ''' 修改current表中的指定项目。

    根据传入的kwargs，修改{current_id}的信息，支持参数包括：
    1、审核人(reviewerid)
    2、页数(pages)
    3、加急状态(urgent)

    Args:
        current_id(str): (SHA256)项目ID
        reviewerid(str): 审核人ID
        pages(int): 页数
        urgent(bool): 是否加急

    Raises:
        ValueError: 如果current_id无效
        ValueError: 如果reviewerid无效
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'current_id': current_id,
        'kwargs': kwargs
    })
    record = fetch(current_id)
    if not record:
        raise ValueError('invalid arg: current_id')

    # 加急报告设置页数的系数
    weighted_pages = int(record['pages'] * 1.5) \
        if record['urgent'] else record['pages']
    with Transaction() as cursor:
        for key, value in kwargs.items():
            if key == 'reviewerid':
                # 修改审核人
                logger.debug('reviewerid: %s -> %s',
                             record['reviewerid'], value)
                if value and \
                        (not t_user.__contains__(value) or value == record['authorid']):
                    raise ValueError('invalid arg: reviewerid')
                cursor.execute(
                    "UPDATE current SET reviewerid = %s WHERE id = %s",
                    (value, record['id']),
                )
                cursor.executemany(
                    "UPDATE user SET pages = pages + %s WHERE id = %s", [
                        (weighted_pages, value),
                        (-weighted_pages, record['reviewerid']),
                    ],
                )
            if key == 'pages':
                # 修改页数
                logger.debug('pages: %s -> %s', record['pages'], value)
                cursor.execute(
                    "UPDATE current SET pages = %s WHERE id = %s",
                    (value, record['id']),
                )
                weighted_pages_new = int(value * 1.5) \
                    if record['urgent'] else value
                cursor.execute(
                    "UPDATE user SET pages = pages + %s WHERE id = %s", (
                        -weighted_pages + weighted_pages_new,
                        record['reviewerid'],
                    ),
                )
            if key == 'urgent':
                # 修改加急状态
                logger.debug('urgent: %s -> %s', record['urgent'], value)
                cursor.execute(
                    "UPDATE current SET urgent = %s WHERE id = %s",
                    (value, record['id']),
                )
                weighted_pages_new = int(record['pages'] * 1.5) \
                    if value else record['pages']
                cursor.execute(
                    "UPDATE user SET pages = pages + %s WHERE id = %s", (
                        -weighted_pages + weighted_pages_new,
                        record['reviewerid'],
                    ),
                )


def finish(current_id: str, finish_timestamp: int):
    ''' 从current表中删除项目（完成审核）

    Args:
        current_id(str): (SHA256)项目ID
        finish_timestamp: 完成时间戳

    Raises:
        ValueError: 如果current_id无效
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'current_id': current_id,
        'finish_timestamp': finish_timestamp,
    })
    record = fetch(current_id)
    if not record:
        raise ValueError('invalid arg: current_id')

    with Transaction() as cursor:
        # 删除current记录
        cursor.execute(
            "DELETE FROM current WHERE id = %s", (record['id'],)
        )
        # 正常删除（完成审核）时，把记录写入history
        cursor.execute('''
            INSERT INTO history (names, company, pages, urgent, authorid, reviewerid, start, end)
            VALUES (%s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s), FROM_UNIXTIME(%s))
            ''', (
            json.dumps(record['names']),
            record['company'],
            record['pages'],
            record['urgent'],
            record['authorid'],
            record['reviewerid'],
            record['start'],
            finish_timestamp,
        )
        )


def finish_by_name(names: dict[str, str], finish_timestamp: int):
    ''' 从current表中删除项目（完成审核）

    Args:
        names: {"code": "name", ...}: 项目名称
        finish_timestamp: 完成时间戳
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'names': names,
        'finish_timestamp': finish_timestamp
    })
    finish(gen_id(names), finish_timestamp)


def delete(current_id: str):
    ''' 从current表中删除项目（强制删除）

    Args:
        current_id(str): (SHA256)项目ID

    Raises:
        ValueError: 如果current_id无效
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {'current_id': current_id})
    record = fetch(current_id)
    if not record:
        raise ValueError('invalid arg: current_id')

    with Transaction() as cursor:
        # 删除current记录
        cursor.execute(
            "DELETE FROM current WHERE id = %s", (record['id'],)
        )
        # 回滚user中的页数
        weighted_pages = int(record['pages'] * 1.5) \
            if record['urgent'] else record['pages']
        cursor.execute(
            "UPDATE user SET pages = pages - %s WHERE id = %s",
            (weighted_pages, record['reviewerid']),
        )


def gen_id(names: dict[str, str]) -> str:
    ''' 根据names生成唯一id
    '''
    return hashlib.sha256('+'.join(sorted(names)).encode('utf-8')).hexdigest()
