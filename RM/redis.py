# -*- coding: UTF-8 -*-
from typing import Literal
import logging
import redis
import socket


class RedisStream:
    """Redis Stream 的封装客户端，实现消息队列管理"""

    _r: redis.Redis = None

    def __init__(self, host: str, password: str = ""):
        """初始化 Redis Stream 的配置，新建相应键

        Args:
            * 参数直接传入redis.Redis
        """
        logger = logging.getLogger(__name__)
        self._r = redis.Redis(
            host=host,
            port=6379,
            db=0,
            password=password,
            decode_responses=True,
        )
        if not self._r.ping():
            raise ValueError("Cannot init redis.")
        logger.info("Redis configration (%s) confirmed.", host)
        for key in ["receive", "read", "resend"]:
            try:
                groups = self._r.xinfo_groups(name=key)
                for group in groups:
                    if group["name"] == "worker":
                        break
                else:
                    raise ValueError("no group: worker")
            except:
                self._r.xgroup_create(
                    name=key,
                    groupname="worker",
                    id="$",
                    mkstream=True,
                )

    def add(
        self,
        source: str,
        name: Literal["receive", "read", "resend"],
        fields: dict = None,
    ) -> str:
        """在Stream中插入一条指令

        Args:
            source: 指令来源（用户、定时任务等）
            name: 键名
            fields: 参数

        Returns:
            entry id
        """
        logger = logging.getLogger(__name__)
        logger.debug("args: %s", {"name": name, "fields": fields})
        if not isinstance(fields, dict):
            fields = {}
        fields["source"] = source
        entry_id = self._r.xadd(name, fields)
        logger.debug("entry_id: %s", entry_id)
        return entry_id

    def read(self) -> list:
        """在Stream以阻塞方式读取指令"""
        logger = logging.getLogger(__name__)
        entries = self._r.xreadgroup(
            groupname="worker",
            consumername=socket.gethostname(),
            streams={"receive": ">", "read": ">", "resend": ">"},
            count=1,
            block=0,
        )
        # > XREADGROUP GROUP mygroup myconsumer STREAMS mystream >
        # 1) 1) "mystream"
        #    2) 1) 1) "1-0"
        #          2) 1) "myfield"
        #             2) "mydata"
        logger.debug("entries: %s", entries)
        return entries

    def ack(self, name: Literal["receive", "read", "resend"], ids: list[str]) -> int:
        """从PEL中去除消息

        Args:
            name: 键名
            ids: 消息ID

        Returns:
            成功去除的消息数量
        """
        logger = logging.getLogger(__name__)
        count = self._r.xack(name, "worker", ids)
        logger.debug("count: %s", count)
        return count

    def trim(self):
        """修剪Stream长度至10"""
        logger = logging.getLogger(__name__)
        logger.debug(
            "receive original len: %s", self._r.xtrim(name="receive", maxlen=10)
        )
        logger.debug("read original len: %s", self._r.xtrim(name="read", maxlen=10))
        logger.debug("resend original len: %s", self._r.xtrim(name="resend", maxlen=10))
