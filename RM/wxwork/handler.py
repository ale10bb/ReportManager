# -*- coding: UTF-8 -*-
import logging
import requests
from . import var

def init(corpid:str, agentid:int, secret:str, admin_userid:str='', enabled:bool = False):
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
    var.enabled = enabled
    session = requests.session()
    r = session.get('https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={}&corpsecret={}'.format(corpid, secret)).json()
    assert not r['errcode'], r['errmsg']
    var.access_token = r['access_token']
    r = session.get('https://qyapi.weixin.qq.com/cgi-bin/agent/get?access_token={}&agentid={}'.format(var.access_token, agentid)).json()
    assert not r['errcode'], r['errmsg']
    logger.info('agent_name: {}'.format(r['name']))
    var.corpid = corpid
    var.agentid = agentid
    var.secret = secret
    if admin_userid:
        var.admin_userid = admin_userid
        logger.info('admin_userid: {}'.format(admin_userid))


def refresh_access_token():
    ''' 检测access_token是否过期，并自动刷新。

    Raises:
        TimeoutError: 如果三次尝试后仍无法获取有效token
    '''
    logger = logging.getLogger(__name__)
    session = requests.session()
    r = session.get('https://qyapi.weixin.qq.com/cgi-bin/agent/get?access_token={}&agentid={}'.format(var.access_token, var.agentid)).json()
    if r['errcode']:
        logger.debug(r)
        for _ in range(3):
            r = session.get('https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={}&corpsecret={}'.format(var.corpid, var.secret)).json()
            if not r['errcode']:
                var.access_token = r['access_token']
                logger.debug(r)
                return
        logger.error('Cannot refresh token')
        raise TimeoutError


def send_text(content:str, to:list=None, to_debug:bool=False, to_stdout:bool=False):
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
    if not var.enabled or to_stdout:
        logger.warning('redirect to stdout and return')
        return
    if to_debug:
        to = [var.admin_userid]

    refresh_access_token()
    r = requests.post(
        'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={}'.format(var.access_token),
        json={
            'touser':'|'.join(to),
            'msgtype':'text',
            'agentid': var.agentid,
            'text': {'content': content}
        }
    ).json()
    logger.debug(r)
