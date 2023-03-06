# -*- coding: UTF-8 -*-
import logging
from .client import Transaction
from . import var

# -------------------------------------
#          histroy增删改查逻辑
# -------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法

def search(code:str='', name:str='', company:str='', author_id:str='', page_index:int=1, page_size:int=10) -> dict:
    ''' 搜索history表中的项目。

    1. 按照code模糊查询history中的所有项目，写入ret['all']；支持按“+”分割传入多个code，查询结果包含code的超集；
    2. 单条记录返回尽可能多的数据，顺序为(id, authorid, authorname, reviewerid, reviewername, start, end, pages, urgent, company, names)

    Args:
        code(str): 项目编号（可选/默认值空）
        name(str): 项目名称（可选/默认值空）
        company(str): 委托单位（可选/默认值空）
        author_id(str): 作者ID（可选/默认值空）
        page_index(int): 分页/当前页（可选/默认值1）
        page_size(int): 分页/页大小（可选/默认值10）

    Returns:
        {'all': [], 'total': int}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'code': code, 'name': name, 'company': company, 'author_id': author_id}))
    assert type(code) == str, 'invalid arg: code'
    assert type(name) == str, 'invalid arg: name'
    assert type(company) == str, 'invalid arg: company'
    assert type(author_id) == str, 'invalid arg: author_id'
    assert type(page_index) == int, 'invalid arg: page_index'
    assert type(page_size) == int, 'invalid arg: page_size'

    ret = {'all': [], 'total': 0}
    with Transaction(var.pool) as cursor:
        inputCodes = set(['%{}%'.format(item) for item in code.split('+')])
        codes_condition = ' AND '.join(['JSON_SEARCH(JSON_KEYS(names), \'one\', %s) IS NOT NULL'] * len(inputCodes)) + ' AND '
        cursor.execute('''
            SELECT count(1) FROM history WHERE {}JSON_SEARCH(names, 'one', %s) IS NOT NULL AND company LIKE %s AND authorid LIKE %s
            '''.format(codes_condition), (
                list(inputCodes) + ['%{}%'.format(name), '%{}%'.format(company), '%{}%'.format(author_id)]
            )
        )
        logger.debug(cursor.statement)
        ret['total'] = cursor.fetchone()[0]
        cursor.execute('''
            SELECT h.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(h.start), UNIX_TIMESTAMP(h.end), h.pages, h.urgent, h.company, h.names
            FROM history h
            LEFT JOIN user u_a ON h.authorid = u_a.id
            LEFT JOIN user u_r ON h.reviewerid = u_r.id 
            WHERE {}JSON_SEARCH(names, 'one', %s) IS NOT NULL AND company LIKE %s AND authorid LIKE %s 
            ORDER BY h.id DESC
            LIMIT %s OFFSET %s
            '''.format(codes_condition), (list(inputCodes) + [
                '%{}%'.format(name), 
                '%{}%'.format(company), 
                '%{}%'.format(author_id),
                page_size,
                page_size * (page_index - 1)
            ])
        )
        logger.debug(cursor.statement)
        ret['all'] = cursor.fetchall()

    logger.debug('return: {}'.format(ret))
    return ret


def fetch(history_id:int) -> tuple:
    ''' 按照history_id查询对应项目的信息

    Args:
        history_id(int): 项目ID

    Returns:
        (id, authorid, authorname, reviewerid, reviewername, start, end, pages, urgent, company, names)

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'history_id': history_id}))
    assert type(history_id) == int, 'invalid arg: history_id'

    with Transaction(var.pool) as cursor:
        cursor.execute('''
            SELECT h.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(h.start), UNIX_TIMESTAMP(h.end), h.pages, h.urgent, h.company, h.names
            FROM history h
            LEFT JOIN user u_a ON h.authorid = u_a.id
            LEFT JOIN user u_r ON h.reviewerid = u_r.id 
            WHERE h.id = %s
            ''', (history_id,)
        )
        logger.debug(cursor.statement)
        row = cursor.fetchone()

    logger.debug('return: {}'.format(row))
    return row


def pop() -> tuple:
    ''' 获取history表中的最新一条记录。

    Returns:
        tuple(id, authorid, authorname, reviewerid, reviewername, start, end, pages, urgent, company, names)
    '''
    logger = logging.getLogger(__name__)

    with Transaction(var.pool) as cursor:
        cursor.execute('''
            SELECT h.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(h.start), UNIX_TIMESTAMP(h.end), h.pages, h.urgent, h.company, h.names
            FROM history h
            LEFT JOIN user u_a ON h.authorid = u_a.id
            LEFT JOIN user u_r ON h.reviewerid = u_r.id 
            ORDER BY h.id DESC
            LIMIT 1
            '''
        )
        logger.debug(cursor.statement)
        row = cursor.fetchone()

    logger.debug('return: {}'.format(row))
    return row


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
