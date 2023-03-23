# -*- coding: UTF-8 -*-
import logging
import json
import redis
import socket


class RedisStream:
    ''' Redis Stream 的封装客户端，实现消息队列管理
    '''
    _r: redis.Redis = None

    def __init__(self, host: str, password: str = ''):
        ''' 初始化 Redis Stream 的配置

        Args:
            * 参数直接传入redis.Redis
        '''
        logger = logging.getLogger(__name__)
        self._r = redis.Redis(
            host=host,
            port=6379,
            db=0,
            password=password,
            decode_responses=True,
        )
        if not self._r.ping():
            raise ValueError('Cannot init redis.')
        logger.info('Redis configration (%s) confirmed.', host)

    def add(self, command: str, kwargs: dict):
        ''' 在Stream中插入一条指令

        Args:
            command: 操作类型
            kwargs: 操作参数
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {'command': command, 'kwargs': kwargs})
        if not isinstance(kwargs, dict):
            kwargs = {}
        self._r.xadd('RM', {'command': command, 'kwargs': json.dumps(kwargs)})
        logger.debug('len: %s', self._r.xlen('RM'))

    def read(self) -> dict:
        ''' 在Stream以阻塞方式读取一条指令
        '''
        logger = logging.getLogger(__name__)
        l = self._r.xreadgroup(
            groupname='RMConsumers',
            consumername=socket.gethostname(),
            streams={'RM': '>'},
            count=1,
            block=0,
            noack=True,
        )
        value = l[0][1][0][1]
        value['kwargs'] = json.loads(value['kwargs'])
        logger.debug('return: %s', value)
        return value

    def trim(self):
        ''' 修剪Stream长度至10
        '''
        logger = logging.getLogger(__name__)
        logger.debug('original len: %s', self._r.xtrim(name='RM', maxlen=10))
