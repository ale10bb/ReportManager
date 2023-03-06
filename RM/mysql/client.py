# -*- coding: UTF-8 -*-

class Transaction:
    def __init__(self, pool):
        self._pool = pool

    def __enter__(self):
        self._cnx = self._pool.get_connection()
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
