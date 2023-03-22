''' MySQL的封装客户端，实现连接池管理及表操作
'''
import logging
from mysql.connector.pooling import MySQLConnectionPool
from mysql.connector.cursor import MySQLCursorBuffered
from . import t_current, t_history, t_log, t_user
from . import var


def init(**kwargs):
    logger = logging.getLogger(__name__)
    var.pool = MySQLConnectionPool(pool_name='RM', **kwargs)
    test_cnx = var.pool.get_connection()
    test_cursor: MySQLCursorBuffered = test_cnx.cursor(buffered=True)
    test_cursor.execute('''
        SELECT id, name, phone, email, role, pages, available, status, status_since
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
    logger.info(
        'MySQL configration (%s@%s) confirmed.', test_cnx.user, test_cnx.server_host)
    test_cnx.close()
