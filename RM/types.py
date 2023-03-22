# -*- coding: UTF-8 -*-
from typing import Literal
from typing import TypedDict


# mysql
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


# mail
class Parsed_Mail(TypedDict):
    operator: Literal['submit', 'finish']
    keyword: str
    timestamp: int
    from_: str
    subject: str
    content: str
    temp_path: str


# notification
class Built_Message(TypedDict):
    subject: str
    content: str


# validator
class Content(TypedDict):
    timestamp: int
    user_id: str
    name: str
    urgent: bool
    excludes: list[str]
    force: str


class Checked_Mail_Content(TypedDict):
    warnings: list[str]
    content: Content


class Attachment(TypedDict):
    pages: int
    company: str
    names: dict[str, str]


class Checked_Mail_Attachment(TypedDict):
    warnings: list[str]
    attachment: Attachment


# wxwork
class GETTOKEN_RESPONSE(TypedDict):
    errcode: int
    errmsg: str
    access_token: str
    expires_in: int


class AGENT_GET_RESPONSE(TypedDict):
    errcode: int
    errmsg: str
    agentid: int
    name: str
    square_logo_url: str
    description: str
    allow_userinfos: dict[str, list[dict[str, str]]]
    allow_partys: dict[str, list[int]]
    allow_tags: dict[str, list[int]]
    close: int
    redirect_domain: str
    report_location_flag: int
    isreportenter: int
    home_url: str
    customized_publish_status: int


class MESSAGE_SEND_RESPONSE(TypedDict):
    errcode: int
    errmsg: str
    invaliduser: str
    invalidparty: str
    invalidtag: str
    unlicenseduser: str
    msgid: str
    response_code: str


class GETUSERINFO_RESPONSE(TypedDict):
    errcode: int
    errmsg: str
    userid: str
    user_ticket: str
    openid: str
    external_userid: str
