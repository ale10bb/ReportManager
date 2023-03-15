# -*- coding: UTF-8 -*-
from typing import Dict, TypedDict
import logging
import requests


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
    allow_userinfos: Dict[str, list[Dict[str, str]]]
    allow_partys: Dict[str, list[int]]
    allow_tags: Dict[str, list[int]]
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


class WXWork:
    ''' WXWork的封装客户端，实现发送text消息的功能。
    '''
    _enabled: bool = False
    _corpid: str = ''
    _agentid: int = 0
    _secret: str = ''
    _access_token: str = ''
    _admin_userid: str = ''

    def __init__(self, corpid: str, agentid: int, secret: str, admin_userid: str = '', enabled: bool = False):
        ''' 初始化wxwork的配置

        Args:
            corpid(str): 企业ID
            agentid(int): 应用ID
            secret(str): 应用secret
            admin_userid(str): 单独通知的管理员
            enabled(bool): 功能开关

        Raises:
            ValueError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)

        if not enabled:
            logger.warning('disable wxwork')
            return
        else:
            self._enabled = True

        session = requests.session()
        url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corpid}&corpsecret={secret}'
        r1: GETTOKEN_RESPONSE = session.get(url).json()
        logger.debug('gettoken response: %s', r1)
        if r1['errcode']:
            raise ValueError('Cannot init wxwork: {}.'.format(r1['errmsg']))
        self._access_token = r1['access_token']
        url = f'https://qyapi.weixin.qq.com/cgi-bin/agent/get?access_token={self._access_token}&agentid={agentid}'
        r2: AGENT_GET_RESPONSE = session.get(url).json()
        logger.debug('agent/get response: %s', r2)
        if r2['errcode']:
            raise ValueError('Cannot init wxwork: {}.'.format(r2['errmsg']))
        logger.info('agent_name: %s', r2['name'])
        self._corpid = corpid
        self._agentid = agentid
        self._secret = secret
        if admin_userid:
            self._admin_userid = admin_userid
            logger.info('admin_userid: %s', admin_userid)

    def refresh_access_token(self):
        ''' 检测access_token是否过期，并自动刷新。

        Raises:
            RuntimeError: 如果三次尝试后仍无法获取有效token
        '''
        logger = logging.getLogger(__name__)

        session = requests.session()
        url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self._corpid}&corpsecret={self._secret}'
        for _ in range(3):
            r: GETTOKEN_RESPONSE = session.get(url).json()
            logger.debug('gettoken response: %s', r)
            if r['errcode']:
                continue
            self._access_token = r['access_token']
            return
        else:
            logger.error('gettoken failed')
            raise RuntimeError('Cannot refresh access token.')

    def send_text(self, content: str, to: list[str], to_debug: bool = False, to_stdout: bool = False):
        ''' 向列表中的用户发送text。参见https://developer.work.weixin.qq.com/document/path/90236#%E6%96%87%E6%9C%AC%E6%B6%88%E6%81%AF

        Args:
            content(str): 通知内容
            to(list): 发送对象的userid列表
            to_debug(bool): 是否将通知强制发送至管理员（可选/默认值False->发送至to指定的对象）
            to_stdout(bool): 是否将通知重定向到stdout（可选/默认值False）

        Raises:
            ValueError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'content': content, 'to': to, 'to_debug': to_debug, 'to_stdout': to_stdout
        })

        # 启用调试模式(to_stdout)后，消息将被重定向到stdout
        # WxWork未启用时，强制打开重定向功能
        if not self._enabled or to_stdout:
            logger.warning('redirect to stdout and return')
            return

        self.refresh_access_token()
        url = f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self._access_token}'
        r: MESSAGE_SEND_RESPONSE = requests.post(url, json={
            'touser': [self._admin_userid] if to_debug else '|'.join(to),
            'msgtype': 'text',
            'agentid': self._agentid,
            'text': {'content': content}
        }).json()
        logger.debug('message/send response: %s', r)
        if r['errcode']:
            raise ValueError('Cannot send text: {}.'.format(r['errmsg']))

    def get_redirect(self, host: str):
        ''' 获取OAuth跳转链接。参见https://developer.work.weixin.qq.com/document/path/91022

        Args:
            host(str): 跳转的host（默认HTTPS）
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {host: host})

        redirect_uri = f'https%3A%2F%2F{host}%2Fauth'
        url = f'https://open.weixin.qq.com/connect/oauth2/authorize?appid={self._corpid}&' \
              f'redirect_uri={redirect_uri}&response_type=code&scope=snsapi_base&' \
              f'agentid={self._agentid}#wechat_redirect'
        logger.debug('url: %s', url)
        return url

    def get_userid(self, code: str) -> str:
        ''' 根据code获取成员信息。参见https://developer.work.weixin.qq.com/document/path/91023

        Args:
            code(str): 跳转携带的code

        Raises:
            RuntimeError: 如果请求OAuth失败
        '''
        logger = logging.getLogger(__name__)

        self.refresh_access_token()
        url = f'https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo?access_token={self._access_token}&code={code}'
        r: GETUSERINFO_RESPONSE = requests.get(url).json()
        logger.debug('auth/getuserinfo response: %s', r)
        if r['errcode']:
            logger.error('auth/getuserinfo error: %s', r['errmsg'])
            raise RuntimeError('Cannot get user info.')
        if 'userid' not in r:
            logger.warning('invalid user: %s', r['openid'])
            return ''
        return r['userid']
