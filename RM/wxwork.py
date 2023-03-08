# -*- coding: UTF-8 -*-
import logging
import requests

class WXWork:
    ''' WeWork的封装客户端，实现发送text消息的功能。
    '''
    _enabled = False
    _corpid = ''
    _agentid = 0
    _secret = ''
    _access_token = ''
    _admin_userid = ''

    def __init__(self, corpid:str, agentid:int, secret:str, admin_userid:str='', enabled:bool = False):
        ''' 初始化wxwork的配置

        Args:
            corpid(str): 企业ID
            agentid(str): 应用ID
            secret(str): 应用secret
            admin_userid(str): 单独通知的管理员
            enabled(bool): 功能开关

        Raises:
            AssertionError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)

        if not enabled:
            logger.warning('wxwork disabled.')
            return
        else:
            self._enabled = True

        session = requests.session()
        r = session.get('https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={}&corpsecret={}'.format(corpid, secret)).json()
        assert not r['errcode'], r['errmsg']
        self._access_token = r['access_token']
        r = session.get('https://qyapi.weixin.qq.com/cgi-bin/agent/get?access_token={}&agentid={}'.format(self._access_token, agentid)).json()
        assert not r['errcode'], r['errmsg']
        logger.info('agent_name: {}'.format(r['name']))
        self._corpid = corpid
        self._agentid = agentid
        self._secret = secret
        if admin_userid:
            self._admin_userid = admin_userid
            logger.info('admin_userid: {}'.format(admin_userid))

    def refresh_access_token(self):
        ''' 检测access_token是否过期，并自动刷新。

        Raises:
            TimeoutError: 如果三次尝试后仍无法获取有效token
        '''
        logger = logging.getLogger(__name__)
        session = requests.session()
        r = session.get('https://qyapi.weixin.qq.com/cgi-bin/agent/get?access_token={}&agentid={}'.format(self._access_token, self._agentid)).json()
        if r['errcode']:
            logger.debug(r)
            for _ in range(3):
                r = session.get('https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={}&corpsecret={}'.format(self._corpid, self._secret)).json()
                if not r['errcode']:
                    self._access_token = r['access_token']
                    logger.debug(r)
                    return
            logger.error('Cannot refresh token')
            raise TimeoutError

    def send_text(self, content:str, to:list=[], to_debug:bool=False, to_stdout:bool=False):
        ''' 向列表中的用户发送text。参见https://developer.work.weixin.qq.com/document/path/90236#%E6%96%87%E6%9C%AC%E6%B6%88%E6%81%AF

        Args:
            content(str): 通知内容
            to(list): 发送对象的userid列表
            to_debug(bool): 是否将通知强制发送至管理员（可选/默认值False->发送至to指定的对象）
            to_stdout(bool): 是否将通知重定向到stdout（可选/默认值False）

        Raises:
            AssertionError: 如果参数类型非法
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: {}'.format({'content': content, 'to': to, 'to_debug': to_debug, 'to_stdout': to_stdout}))
        assert type(content) == str, 'invalid arg: content'
        if not to:
            to = []
        assert type(to) == list, 'invalid arg: to'

        # 启用调试模式(to_stdout)后，消息将被重定向到stdout
        # WxWork未启用时，强制打开重定向功能
        if not self._enabled or to_stdout:
            logger.warning('redirect to stdout and return')
            return
        if to_debug:
            to = [self._admin_userid]

        self.refresh_access_token()
        r = requests.post(
            'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={}'.format(self._access_token),
            json={
                'touser':'|'.join(to),
                'msgtype':'text',
                'agentid': self._agentid,
                'text': {'content': content}
            }
        ).json()
        logger.debug(r)

    def get_redirect(self):
        ''' 获取OAuth跳转链接。参见https://developer.work.weixin.qq.com/document/path/91022

        '''
        return 'https://open.weixin.qq.com/connect/oauth2/authorize?appid={}&redirect_uri={}&response_type=code&scope=snsapi_base&agentid={}#wechat_redirect'.format(
            self._corpid,
            'https%3A%2F%2Frm.chenql.cn%2Fapi%2Fauth',
            self._agentid,
        )

    def get_userid(self, code:str) -> str:
        ''' 根据code获取成员信息。参见https://developer.work.weixin.qq.com/document/path/91023

        Args:
            code(str): 跳转携带的code

        Raises:
            AssertionError: 如果参数类型非法
        '''
        logger = logging.getLogger(__name__)
        self.refresh_access_token()
        r = requests.get('https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo?access_token{}=&code={}'.format(
            self._access_token,
            code,
        )).json()
        logger.debug(r)
        if r['errcode']:
            logger.warning('getuserinfo error: {}'.format(r['errmsg']))
        return r.setdefault('userid', '')
