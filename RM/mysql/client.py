# -*- coding: UTF-8 -*-
import logging
import mysql.connector

class Transaction(mysql.connector.pooling.MySQLConnectionPool):
    def __init__(self, **kwargs):
        logger = logging.getLogger(__name__)
        super().__init__(pool_name = 'RM', pool_size = 3, **kwargs)
        test_cnx = super().get_connection()
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
        test_cursor.close()
        logger.info('MySQL configration ({}@{}) confirmed.'.format(test_cnx.user, test_cnx.server_host))
        test_cnx.close()

    def __enter__(self):
        self._cnx = super().get_connection()
        self._cursor = self._cnx.cursor(buffered=True)
        return self._cursor
 
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self._cnx.commit()
            self._cursor.close()
            self._cnx.close()
            return True
        if isinstance(exc_type, RuntimeError) and exc_val == 'rollback':
            self._cnx.rollback()
            self._cursor.close()
            self._cnx.close()
            return True
        else:
            self._cnx.rollback()
            self._cursor.close()
            self._cnx.close()
            return False
