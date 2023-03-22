# -*- coding: UTF-8 -*-
from typing import Literal
from typing import TypedDict


class UserItem(TypedDict):
    id: str
    name: str
    phone: str
    email: str
    role: Literal[0, 1]
    status: Literal[0, 1, 2]


class QueueItem(UserItem):
    pages_diff: int
    current: int
    skipped: Literal[0, 1]


class BaseRecord(TypedDict):
    authorid: str
    authorname: str
    reviewerid: str
    reviewername: str
    start: int
    pages: int
    urgent: bool
    company: int
    names: dict[str, str]


class CurrentRecord(BaseRecord):
    id: str
    end: None


class HistoryRecord(BaseRecord):
    id: int
    end: int


class Currents(TypedDict):
    current: list[CurrentRecord]
    total: int


class Histories(TypedDict):
    history: list[HistoryRecord]
    total: int
