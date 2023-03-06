''' MySQL的封装客户端，实现连接池管理及表操作
'''
from . import t_audit, t_current, t_history, t_log, t_user

def init(**kwargs):
    import logging
    import mysql.connector.pooling
    from . import var
    logger = logging.getLogger(__name__)
    var.pool = mysql.connector.pooling.MySQLConnectionPool(pool_name = 'RM', pool_size = 3, **kwargs)
    test_cnx = var.pool.get_connection()
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
