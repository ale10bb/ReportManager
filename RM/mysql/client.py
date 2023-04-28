# -*- coding: UTF-8 -*-
from mysql.connector.cursor import MySQLCursor
from mysql.connector.pooling import MySQLConnectionPool
from . import var


class Transaction:
    def __init__(self):
        if not var.pool:
            var.pool = MySQLConnectionPool(pool_name='RM', **var.kwargs)
        self._cnx = var.pool.get_connection()

    def __enter__(self):
        self._cursor: MySQLCursor = self._cnx.cursor()
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


class Selection:
    def __init__(self):
        if not var.pool:
            var.pool = MySQLConnectionPool(pool_name='RM', **var.kwargs)
        self._cnx = var.pool.get_connection()

    def __enter__(self):
        self._cursor: MySQLCursor = self._cnx.cursor()
        return self._cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cnx.rollback()
        self._cursor.close()
        self._cnx.close()
        return not bool(exc_type)
