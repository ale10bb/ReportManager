# -*- coding: UTF-8 -*-
import logging
import json
from .client import Transaction
from . import var

# ------------------------------------
#       log_manage表增删改查逻辑
# ------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法
#     插入时立刻进行commit操作

def add(ip:str, user:str|None, user_agent:str, url:str, param:dict):
    ''' 向log_manage中插入操作日志。

    Args:
        ip(str): 操作人IP
        user(str|None): 操作人
        user_agent(str): UA
        url(str): 模块路径
        param(dict): 模块参数

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'ip': ip, 'user': user, 'user_agent': user_agent, 'url': url, 'param': param}))
    assert type(ip) == str, 'invalid arg: ip'
    if not user:
        user = ''
    assert type(user) == str, 'invalid arg: user'
    assert type(user_agent) == str, 'invalid arg: user_agent'
    assert type(url) == str, 'invalid arg: url'
    assert type(param) == dict, 'invalid arg: param'

    with Transaction(var.pool) as cursor:
        cursor.execute('''
            INSERT INTO log_manage (ip, user, user_agent, url, param)
            VALUES (INET6_ATON(%s), %s, %s, %s, %s)
            ''', (ip, user, user_agent, url, json.dumps(param, ensure_ascii=False))
        )
        logger.debug(cursor.statement)
