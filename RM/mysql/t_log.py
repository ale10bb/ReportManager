# -*- coding: UTF-8 -*-
import logging
import json
from .connector import Connection

# ------------------------------------
#        log_mail表增删改查逻辑
# ------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法
#     插入时立刻进行commit操作

def add(check_results:dict, err:str=''):
    ''' 向log_mail中插入操作日志。

    Args:
        check_results(dict): check的结果包
        err(str): 错误信息（可选/默认值空）

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'check_results': check_results, 'err': err}))
    assert type(check_results) == dict, 'invalid arg: check_results'
    assert type(err) == str, 'invalid arg: err'

    with Connection() as (cnx, cursor):
        cursor.execute('''
            INSERT INTO log_mail (operator, keyword, error, warnings, mail, content, attachment, target, notification, work_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                check_results.get('operator', '<null>'),
                check_results.get('keyword', '<null>'),
                err, 
                json.dumps(check_results.get('warnings', []), ensure_ascii=False),
                json.dumps(check_results.get('mail', {})),
                json.dumps(check_results.get('content', {})),
                json.dumps(check_results.get('attachment', {})),
                json.dumps(check_results.get('target', [])),
                json.dumps(check_results.get('notification', {})),
                check_results.get('work_path', '<null>')
            )
        )
        logger.debug(cursor.statement)
        cnx.commit()
