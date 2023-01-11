# -*- coding: UTF-8 -*-
import logging
import json
import hashlib
from .connector import Connection
from . import t_user

# -------------------------------------
#         current表增删改查逻辑
# -------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法
#     不进行commit操作

def search(code:str='', user_id:str='') -> dict:
    ''' 搜索current表中的项目。

    1. 按照code模糊查询current中的所有项目，写入ret['all']；支持按“+”分割传入多个code，查询结果包含code的超集；
    2. 传入user_id时，根据(1)的条件，额外检索current的authorid和reviewerid列，分别写入ret['submit']、ret['review']；
    3. 单条记录返回尽可能多的数据，顺序为(id, authorid, authorname, reviewerid, reviewername, start, end, pages, urgent, company, names)

    Args:
        code(str): 项目编号（可选/默认值空）
        user_id(str): 用户ID（精确查询）（可选/默认值空）

    Returns:
        {"all": [], "submit": [], "review": []}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'code': code, 'user_id': user_id}))
    assert type(code) == str, 'invalid arg: code'
    assert type(user_id) == str, 'invalid arg: user_id'

    ret = {'all': [], 'submit': [], 'review': []}
    with Connection() as (cnx, cursor):
        inputCodes = set(['%{}%'.format(item) for item in code.split('+')])
        codes_condition = ' AND '.join(['JSON_SEARCH(JSON_KEYS(names), \'one\', %s) IS NOT NULL'] * len(inputCodes))
        cursor.execute('''
            SELECT c.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(c.start), null, c.pages, c.urgent, c.company, c.names
            FROM current c
            LEFT JOIN user u_a ON c.authorid = u_a.id
            LEFT JOIN user u_r ON c.reviewerid = u_r.id 
            WHERE {}
            '''.format(codes_condition), (list(inputCodes))
        )
        logger.debug(cursor.statement)
        cnx.commit()
        ret['all'] = cursor.fetchall()
        logger.debug('result: {}'.format(ret['all']))
        # 检查user_id是否在内容字段中
        ret['submit'] = [row for row in ret['all'] if row[1] == user_id]
        ret['review'] = [row for row in ret['all'] if row[3] == user_id]

    logger.debug('return: {}'.format(ret))
    return ret


def fetch(current_id:str) -> tuple:
    ''' 按照current_id查询对应项目的信息

    Args:
        current_id(str): (SHA256)项目ID

    Returns:
        (id, authorid, authorname, reviewerid, reviewername, start, end, pages, urgent, company, names)

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'current_id': current_id}))
    assert type(current_id) == str, 'invalid arg: current_id'

    with Connection() as (cnx, cursor):
        cursor.execute('''
            SELECT c.id, u_a.id, u_a.name, u_r.id, u_r.name, UNIX_TIMESTAMP(c.start), null, c.pages, c.urgent, c.company, c.names
            FROM current c
            LEFT JOIN user u_a ON c.authorid = u_a.id
            LEFT JOIN user u_r ON c.reviewerid = u_r.id 
            WHERE c.id = %s
            ''', (current_id,)
        )
        logger.debug(cursor.statement)
        cnx.commit()
        row = cursor.fetchone()

    logger.debug('return: {}'.format(row))
    return row


def add(names:dict, company:str, pages:int, urgent:bool, author_id:str, submit_timestamp:int) -> str:
    ''' 向current表中添加项目（所有参数均必填）。

    Args:
        names: {"code": "name", ...}
        company: 委托单位
        pages: 页数
        urgent: 是否加急
        author_id: 作者ID
        submit_timestamp: 提交时间戳

    Returns:
        str: (SHA256)项目ID

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({
        'names': names, 
        'company': company, 
        'pages': pages, 
        'urgent': urgent, 
        'author_id': author_id, 
        'submit_timestamp': submit_timestamp,
    }))
    assert type(names) == dict, 'invalid arg: names'
    assert type(company) == str, 'invalid arg: company'
    assert type(pages) == int, 'invalid arg: pages'
    assert type(urgent) == bool, 'invalid arg: urgent'
    assert type(author_id) == str, 'invalid arg: author_id'
    assert type(submit_timestamp) == int, 'invalid arg: submit_timestamp'
    
    # 传入names包中，code按升序排序后，按加号合并
    codes = list(names.keys())
    codes.sort()
    code = '+'.join(codes)
    assert not __contains__(code), 'duplicate code: {}'.format(code)

    # 使用SHA-256算法生成唯一主键
    current_id = hashlib.sha256(code.encode('utf-8')).hexdigest()
    logger.debug('current_id: {}'.format(current_id))

    with Connection() as (cnx, cursor):
        cursor.execute('''
            INSERT INTO current (id, names, company, pages, urgent, authorid, start)
            VALUES (%s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s))
            ''', (current_id, json.dumps(names), company, pages, urgent, author_id, submit_timestamp)
        )
        logger.debug(cursor.statement)
        cnx.commit()

    logger.debug('return: {}'.format(current_id))
    return current_id


def edit(current_id:str, **kwargs):
    ''' 修改current表中的指定项目。
    
    根据传入的kwargs，修改{current_id}的信息，支持参数包括：
    1、审核人(reviewerid)；注意，此处无法校验目标是否为组员；
    2、页数(pages)；
    3、加急状态(urgent)；

    Args:
        current_id(str): (SHA256)项目ID
        reviewerid(str): 审核人ID
        pages(int): 页数
        urgent(bool): 是否加急

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'current_id': current_id, 'kwargs': kwargs}))
    ret = fetch(current_id)
    assert ret, 'invalid arg: current_id'

    # 加急报告设置页数的系数
    modified_pages_search = int(ret[7] * 1.5) if ret[8] else ret[7]
    with Connection() as (cnx, cursor):
        if 'reviewerid' in kwargs.keys():
            # 修改审核人
            logger.debug('reviewerid: {} -> {}'.format(ret[3], kwargs['reviewerid']))
            if kwargs['reviewerid']:
                assert t_user.__contains__(kwargs['reviewerid'], only_reviewer=True), 'invalid user'
                assert kwargs['reviewerid'] != ret[1], 'cannot modify'
                cursor.execute('''
                    UPDATE user 
                    SET pages = pages + %s
                    WHERE id = %s
                    ''', (modified_pages_search, kwargs['reviewerid'])
                )
                logger.debug(cursor.statement)
                cursor.execute('''
                    UPDATE current 
                    SET reviewerid = %s
                    WHERE id = %s
                    ''', (kwargs['reviewerid'], ret[0])
                )
                logger.debug(cursor.statement)
            else:
                # 将审核人设置为空
                cursor.execute('''
                    UPDATE current 
                    SET reviewerid = ''
                    WHERE id = %s
                    ''', (ret[0],)
                )
                logger.debug(cursor.statement)
            if ret[3]:
                # 如果已有审核人，减去其pages
                cursor.execute('''
                    UPDATE user 
                    SET pages = pages + %s
                    WHERE id = %s
                    ''', (-modified_pages_search, ret[3])
                )
                logger.debug(cursor.statement)
            cnx.commit()
        if 'pages' in kwargs.keys():
            # 修改页数
            logger.debug('pages: {} -> {}'.format(ret[7], kwargs['pages']))
            # 如果已有审核人，修改其pages
            if ret[3]:
                modified_pages_kwargs = int(kwargs['pages'] * 1.5) if ret[8] else kwargs['pages']
                cursor.execute('''
                    UPDATE user 
                    SET pages = pages + %s
                    WHERE id = %s
                    ''', (-modified_pages_search+modified_pages_kwargs, ret[3])
                )
                logger.debug(cursor.statement)
            cursor.execute('''
                UPDATE current 
                SET pages = %s
                WHERE id = %s
                ''', (kwargs['pages'], ret[0])
            )
            logger.debug(cursor.statement)
            cnx.commit()
        if 'urgent' in kwargs.keys():
            # 修改加急状态
            logger.debug('urgent: {} -> {}'.format(ret[8], kwargs['urgent']))
            # 如果已有审核人，修改其pages
            if ret[3]:
                if 'pages' in kwargs.keys():
                    modified_pages_kwargs = int(kwargs['pages'] * 1.5) if kwargs['urgent'] else kwargs['pages']
                else:
                    modified_pages_kwargs = int(ret[7] * 1.5) if kwargs['urgent'] else ret[7]
                cursor.execute('''
                    UPDATE user 
                    SET pages = pages + %s
                    WHERE id = %s
                    ''', (-modified_pages_search+modified_pages_kwargs, ret[3])
                )
                logger.debug(cursor.statement)
            cursor.execute('''
                UPDATE current 
                SET urgent = %s
                WHERE id = %s
                ''', (kwargs['urgent'], ret[0])
            )
            logger.debug(cursor.statement)
            cnx.commit()


def delete(current_id:str, finish_timestamp:int, force:bool=False):
    ''' 从current表中删除项目。

    可进行正常删除或强制删除操作。
    1、正常删除（完成审核）：项目存档至history；
    2、强制删除：回滚user的current和pages

    Args:
        current_id(str): (SHA256)项目ID
        finish_timestamp: 完成时间戳
        force: 是否为强制删除

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'current_id': current_id, 'finish_timestamp': finish_timestamp, 'force': force}))
    ret = fetch(current_id)
    assert ret, 'invalid arg: current_id'
    assert type(finish_timestamp) == int, 'invalid arg: finish_timestamp'

    with Connection() as (cnx, cursor):
        # 删除current记录
        cursor.execute(
            "DELETE FROM current WHERE id = %s", (ret[0],)
        )
        logger.debug(cursor.statement)
        if force:
            # 强制删除时，回滚user中的页数
            cursor.execute('''
                UPDATE user 
                SET pages = pages + %s
                WHERE id = %s
                ''', (-int(ret[7] * 1.5) if ret[8] else -ret[7], ret[3])
            )
            logger.debug(cursor.statement)
        else:
            # 正常删除（完成审核）时，把记录写入history
            cursor.execute('''
                INSERT INTO history (names, company, pages, urgent, authorid, reviewerid, start, end)
                VALUES (%s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s), FROM_UNIXTIME(%s))
                ''', (ret[10], ret[9], ret[7], ret[8], ret[1], ret[3], ret[5], finish_timestamp)
            )
            logger.debug(cursor.statement)
        cnx.commit()


def __contains__(code:str) -> bool:
    ''' 检查current表中是否存在code

    Args:
        code(str): 项目编号

    Returns:
        bool: code存在返回True，否则返回False
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'code': code}))

    ret = search(code)
    logger.debug('return: {}'.format(bool(ret['all'])))
    return bool(ret['all'])


def unique(code:str) -> bool:
    ''' 检查current表中是否存在唯一的code

    Args:
        code(str): 项目编号

    Returns:
        bool: code唯一返回True，否则返回False
    '''
    logger = logging.getLogger(__name__)
    logger.debug('param: {}'.format({'code': code}))

    ret = search(code)
    logger.debug('return: {}'.format(len(ret['all']) == 1))
    return len(ret['all']) == 1
