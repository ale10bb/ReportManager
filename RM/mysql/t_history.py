# -*- coding: UTF-8 -*-
''' histroy表增删改查逻辑
'''
import logging
import json
from .client import Selection
from ..types import *


def search(page_index: int = 1, page_size: int = 10, **kwargs) -> Histories:
    ''' 根据传入的kwargs，搜索history表中的项目，支持参数包括：

    1. code(str): 按项目编号模糊查询；支持按“+”分割传入多个code，如"123+345"
    2. authorid(str)/reviewerid(str): 按撰写人id或审核人id精准查询
    3. name(str)/company(str): 按项目名称或委托单位模糊查询

    Args:
        page_index: 分页/当前页
        page_size: 分页/页大小

    Returns:
        {'history': list[HistoryRecord], 'total': int}
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: %s', {
        'page_index': page_index,
        'page_size': page_size,
        'kwargs': kwargs,
    })

    ret: Histories = {'history': [], 'total': 0}
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
            if key == 'name':
                params.append(f'%{value}%')
                condition += ' AND JSON_SEARCH(names, \'one\', %s) IS NOT NULL'
            if key == 'company':
                params.append(f'%{value}%')
                condition += ' AND company LIKE %s'
        logger.debug('params: %s', params)
        logger.debug('condition: %s', condition)
        sql = f"SELECT count(1) as count FROM history WHERE 1=1{condition}"
        cursor.execute(sql, params)
        ret['total'] = int(cursor.fetchone()[0])
        sql = f'''
            SELECT h.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(h.start), UNIX_TIMESTAMP(h.end), h.pages, h.urgent, h.company, h.names
            FROM history h
            LEFT JOIN user u_a ON h.authorid = u_a.id
            LEFT JOIN user u_r ON h.reviewerid = u_r.id 
            WHERE 1=1{condition}
            ORDER BY h.id DESC
            LIMIT %s OFFSET %s
        '''
        cursor.execute(sql, params + [page_size, page_size * (page_index - 1)])
        keys = ['id', 'authorid', 'authorname', 'reviewerid', 'reviewername',
                'start', 'end', 'pages', 'urgent', 'company', 'names']
        for row in cursor.fetchall():
            logger.debug('row: %s', row)
            d = HistoryRecord(zip(keys, row))
            d['names'] = json.loads(d['names'])
            d['urgent'] = bool(d['urgent'])
            ret['history'].append(d)
    logger.debug('return: %s', ret)
    return ret


def fetch(history_id: int) -> HistoryRecord | None:
    ''' 按照history_id查询对应项目的信息

    Args:
        history_id: 项目ID

    Returns:
        HistoryRecord | None
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}', {'history_id': history_id})

    ret: HistoryRecord | None = None
    with Selection() as cursor:
        cursor.execute('''
            SELECT h.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(h.start), UNIX_TIMESTAMP(h.end), h.pages, h.urgent, h.company, h.names
            FROM history h
            LEFT JOIN user u_a ON h.authorid = u_a.id
            LEFT JOIN user u_r ON h.reviewerid = u_r.id 
            WHERE h.id = %s
            ''', (history_id,)
        )
        row = cursor.fetchone()
        if row:
            logger.debug('row: %s', row)
            keys = ['id', 'authorid', 'authorname', 'reviewerid', 'reviewername',
                    'start', 'end', 'pages', 'urgent', 'company', 'names']
            ret = HistoryRecord(zip(keys, row))
            ret['names'] = json.loads(ret['names'])
            ret['urgent'] = bool(ret['urgent'])
    logger.debug('return: %s', ret)
    return ret


def pop() -> HistoryRecord | None:
    ''' 获取history表中的最新一条记录

    Returns:
        HistoryRecord | None
    '''
    logger = logging.getLogger(__name__)

    ret: HistoryRecord | None = None
    with Selection() as cursor:
        cursor.execute('''
            SELECT h.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(h.start), UNIX_TIMESTAMP(h.end), h.pages, h.urgent, h.company, h.names
            FROM history h
            LEFT JOIN user u_a ON h.authorid = u_a.id
            LEFT JOIN user u_r ON h.reviewerid = u_r.id 
            ORDER BY h.id DESC
            LIMIT 1
            ''')
        row = cursor.fetchone()
        if row:
            logger.debug('row: %s', row)
            keys = ['id', 'authorid', 'authorname', 'reviewerid', 'reviewername',
                    'start', 'end', 'pages', 'urgent', 'company', 'names']
            ret = HistoryRecord(zip(keys, row))
            ret['names'] = json.loads(ret['names'])
            ret['urgent'] = bool(ret['urgent'])
    logger.debug('return: %s', ret)
    return ret


# def analysis_procedure_1() -> list:
#     ''' 分析用存储过程1，查询一个月内完成审核的项目编号及项目名称。

#     Returns:
#         [{"authorid": "xxx", "names": {xxx}]
#     '''
#     logger = logging.getLogger(__name__)

#     # 初始化ret结构
#     ret = []

#     with Transaction(var.pool) as cursor:
#         cursor.execute('''
#             SELECT authorid, CAST(
#                 concat('{', GROUP_CONCAT(SUBSTRING_INDEX(SUBSTR(names,2), '}', 1)), '}')
#             AS JSON) merged_names
#             FROM history
#             WHERE TIMESTAMPDIFF(MONTH, `end`, CURRENT_TIMESTAMP()) < 1
#             GROUP BY authorid
#             '''
#         )
#         logger.debug(cursor.statement)
#         for row in cursor.fetchall():
#             ret.append({'authorid': row[0], 'names': json.loads(row[1])})

#     return ret
