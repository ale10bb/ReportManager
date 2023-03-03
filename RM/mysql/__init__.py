''' MySQL的封装客户端，实现连接池管理及表操作
'''
from . import t_audit, t_current, t_history, t_log, t_user

def init(**kwargs):
    ''' 初始化mysql的配置

    Args:
        * 参数直接传入mysql.connector
    '''
    from .client import Transaction
    from . import var
    var.transaction = Transaction(**kwargs)
