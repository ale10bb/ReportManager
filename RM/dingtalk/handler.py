# -*- coding: UTF-8 -*-
import logging
from dingtalkchatbot.chatbot import DingtalkChatbot, ActionCard, CardItem
from . import var

def init(chatbot:dict={}, chatbot_debug:dict={}, attend_url:str='', interaction_url:str='', enabled:bool = False):
    ''' 初始化dingtalk的配置

    Args:
        chatbot(dict): 需包含'webhook'、'secret'
        chatbot_debug(dict): 需包含'webhook'、'secret'
        attend_url(str): 打卡跳转地址
        interaction_url(str): 管理系统跳转地址
        enabled(bool): 功能开关

    Raises:
        AssertionError: 如果参数无效
    '''
    logger = logging.getLogger(__name__)

    if not enabled:
        logger.warning('dingtalk disabled.')
        return
    var.enabled = enabled
    assert type(chatbot.setdefault('webhook', '')) == str, 'invalid arg: chatbot.webhook'
    assert type(chatbot.setdefault('secret', '')) == str, 'invalid arg: chatbot.secret'
    if chatbot['webhook'] and chatbot['secret']:
        var.chatbot = DingtalkChatbot(webhook=chatbot['webhook'], secret=chatbot['secret'])
        logger.info('Chatbot set.')
    assert type(chatbot_debug.setdefault('webhook', '')) == str, 'invalid arg: chatbot_debug.webhook'
    assert type(chatbot_debug.setdefault('secret', '')) == str, 'invalid arg: chatbot_debug.secret'
    if chatbot_debug['webhook'] and chatbot_debug['secret']:
        var.chatbot_debug = DingtalkChatbot(webhook=chatbot_debug['webhook'], secret=chatbot_debug['secret'])
        logger.info('Chatbot_debug set.')
    assert type(attend_url) == str, 'invalid arg: attend_url'
    if attend_url:
        var.attend_url = attend_url
        logger.info('attend_url: {}'.format(attend_url))
    assert type(interaction_url) == str, 'invalid arg: interaction_url'
    if interaction_url:
        var.interaction_url = interaction_url
        logger.info('interaction_url: {}'.format(interaction_url))


def send_markdown(title:str, content:str, phone:str='', to_debug:bool=False, to_stdout:bool=False):
    ''' 发送markdown，指定phone时尝试@该号码。

    Args:
        title(str): 通知标题
        content(str): 通知内容
        phone(str): 需要@的号码（可选/默认值空）
        to_debug(bool): 发送至主通知群还是调试通知群（可选/默认值False->发送至主通知群）
        to_stdout(bool): 是否将通知重定向到stdout（可选/默认值False）

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'title': title, 'content': content, 'phone': phone, 'to_debug': to_debug, 'to_stdout': to_stdout}))
    assert type(title) == str, 'invalid arg: title'
    assert type(content) == str, 'invalid arg: content'
    assert type(phone) == str, 'invalid arg: phone'

    # 启用调试模式(to_stdout)后，消息将被重定向到stdout
    # 未初始化对应chatbot时，强制打开重定向功能
    # dingtalk未启用时，强制打开重定向功能
    if not var.enabled or (to_debug and not var.chatbot_debug) or (not to_debug and not var.chatbot):
        to_stdout = True
    if to_stdout:
        logger.warning('redirect to stdout and return')
        return

    if to_debug:
        r = var.chatbot_debug.send_markdown(title=title, text=content)
    else:
        if phone:
            logger.debug('at_mobiles: True')
            r = var.chatbot.send_markdown(
                title=title + '@' + phone, 
                text=content, 
                at_mobiles=[phone], 
                is_auto_at=False
            )
        else:
            # 不指定at时直接发送
            r = var.chatbot.send_markdown(title=title, text=content)
    logger.debug(r)


def send_action_card(content:str, to_debug:bool=False, to_stdout:bool=False):
    ''' 发送（打卡用）action_card。

    Args:
        content(str): 通知内容
        to_debug(bool): 发送至主通知群还是调试通知群（可选/默认值False->发送至主通知群）
        to_stdout(bool): 是否将通知重定向到stdout（可选/默认值False）

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'content': content, 'to_debug': to_debug, 'to_stdout': to_stdout}))
    assert type(content) == str, 'invalid arg: content'

    # 启用调试模式(to_stdout)后，消息将被重定向到stdout
    # 未初始化对应chatbot时，强制打开重定向功能
    # dingtalk未启用时，强制打开重定向功能
    if not var.enabled or (to_debug and not var.chatbot_debug) or (not to_debug and not var.chatbot):
        to_stdout = True
    if to_stdout:
        logger.warning('redirect to stdout and return')
        return

    # 如果未初始化两个按钮地址，则禁用对应按钮
    buttons = []
    if var.attend_url:
        buttons.append(CardItem(title="打卡", url=var.attend_url))
    if var.interaction_url:
        buttons.append(CardItem(title="打机器人", url=var.interaction_url))
    logger.debug('buttons: {}'.format(buttons))
    
    # action_card要求必须有按钮，如果两个按钮都未启用，则fallback到markdown
    if to_debug:
        if buttons:
            r = var.chatbot_debug.send_action_card(
                ActionCard(
                    title='任务状态', 
                    text=content,
                    btns=buttons,
                    btn_orientation=1,
                    hide_avatar=1
                )
            )
        else:
            r = var.chatbot_debug.send_markdown(
                title='任务状态', 
                text=content
            )
    else:
        if buttons:
            r = var.chatbot.send_action_card(
                ActionCard(
                    title='任务状态', 
                    text=content,
                    btns=buttons,
                    btn_orientation=1,
                    hide_avatar=1
                )
            )
        else:
            r = var.chatbot.send_markdown(
                title='任务状态', 
                text=content
            )
    logger.debug(r)
