# -*- coding: UTF-8 -*-
import logging
import json
from .connector import Connection

# ------------------------------------
#       log_manage表增删改查逻辑
# ------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法
#     插入时立刻进行commit操作

def add(ip:str, user_agent:str, url:str, param:dict, result:dict):
    ''' 向log_manage中插入操作日志。

    Args:
        ip(str): 操作人IP
        user_agent(str): 操作人user_agent
        url(str): 模块路径
        param(dict): 模块参数
        result(dict): 操作结果

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'ip': ip, 'user_agent': user_agent, 'url': url, 'param': param, 'result': result}))
    assert type(ip) == str, 'invalid arg: ip'
    assert type(user_agent) == str, 'invalid arg: user_agent'
    assert type(url) == str, 'invalid arg: url'
    assert type(param) == dict, 'invalid arg: param'
    assert type(result) == dict, 'invalid arg: result'

    with Connection() as (cnx, cursor):
        cursor.execute('''
            INSERT INTO log_manage (ip, user_agent, url, param, result)
            VALUES (INET6_ATON(%s), %s, %s, %s, %s)
            ''', (
                ip,
                user_agent,
                url, 
                json.dumps(param, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False)
            )
        )
        logger.debug(cursor.statement)
        cnx.commit()
