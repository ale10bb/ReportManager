# -*- coding: UTF-8 -*-
import logging
import mysql.connector
from dbutils.pooled_db import PooledDB
from . import var

def init(*args, **kwargs):
    ''' 初始化mysql的配置

    Args:
        * 参数直接传入mysql.connector
    '''
    logger = logging.getLogger(__name__)
    test_cnx = mysql.connector.connect(*args, **kwargs)
    test_cursor = test_cnx.cursor(buffered=True)
    test_cursor.execute('''
        SELECT id, name, phone, role, pages, available, status, status_since
        FROM user 
        LIMIT 1
    ''')
    test_cursor.execute('''
        SELECT id, names, company, pages, urgent, authorid, reviewerid, start 
        FROM current 
        LIMIT 1
    ''')
    test_cursor.execute('''
        SELECT id, names, company, pages, urgent, authorid, reviewerid, start, end 
        FROM history 
        LIMIT 1
    ''')
    test_cursor.execute('''
        SELECT id, time, operator, keyword, error, warnings, 
               mail, content, attachment, target, notification, work_path 
        FROM log_mail 
        LIMIT 1
    ''')
    test_cnx.commit()
    test_cursor.close()
    test_cnx.close()
    var.connector_args = args
    var.connector_kwargs = kwargs
    logger.info('MySQL configration ({}@{}) confirmed.'.format(test_cnx.user, test_cnx.server_host))


def connect():
    logger = logging.getLogger(__name__)
    assert var.connector_args or var.connector_kwargs, 'No initiation.'
    var.pool = PooledDB(mysql.connector, *var.connector_args, **var.connector_kwargs)
    logger.debug('Connected to MySQL.')


def disconnect():
    logger = logging.getLogger(__name__)
    var.pool = None
    logger.debug('Disconnected from MySQL.')


class Connection(object):
    def __init__(self):
        if not var.pool:
            connect()
 
    def __enter__(self):
        self._cnx = var.pool.connection()
        self._cursor = self._cnx.cursor(buffered=True)
        return self._cnx, self._cursor
 
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cnx.rollback()
        self._cursor.close()
        self._cnx.close()
        return False
