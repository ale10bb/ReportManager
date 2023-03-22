# -*- coding: UTF-8 -*-
import logging
import json
from dingtalkchatbot.chatbot import DingtalkChatbot, ActionCard, CardItem
from . import mysql


class Dingtalk:
    ''' Dingtalk的封装客户端，实现发送markdown消息和发送actioncard消息的功能。
    '''
    _chatbot: DingtalkChatbot | None = None
    _chatbot_debug: DingtalkChatbot | None = None
    _attend_url = ''
    _interaction_url = ''

    def __init__(self, chatbot: dict | None = None, chatbot_debug: dict | None = None, attend_url: str = '', interaction_url: str = ''):
        ''' 初始化dingtalk的配置

        Args:
            chatbot(dict): 需包含'webhook'、'secret'
            chatbot_debug(dict): 需包含'webhook'、'secret'
            attend_url(str): 打卡跳转地址
            interaction_url(str): 管理系统跳转地址

        Raises:
            TypeError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)
        if not chatbot:
            chatbot = {}
        if not isinstance(chatbot.setdefault('webhook', ''), str):
            raise TypeError('invalid arg: chatbot.webhook')
        if not isinstance(chatbot.setdefault('secret', ''), str):
            raise TypeError('invalid arg: chatbot.secret')
        if chatbot['webhook'] and chatbot['secret']:
            self._chatbot = DingtalkChatbot(
                webhook=chatbot['webhook'], secret=chatbot['secret'])
            logger.info('Chatbot set.')
        if not chatbot_debug:
            chatbot_debug = {}
        if not isinstance(chatbot_debug.setdefault('webhook', ''), str):
            raise TypeError('invalid arg: chatbot_debug.webhook')
        if not isinstance(chatbot_debug.setdefault('secret', ''), str):
            raise TypeError('invalid arg: chatbot_debug.secret')
        if chatbot_debug['webhook'] and chatbot_debug['secret']:
            self._chatbot_debug = DingtalkChatbot(
                webhook=chatbot_debug['webhook'], secret=chatbot_debug['secret'])
            logger.info('Chatbot_debug set.')
        if not isinstance(attend_url, str):
            raise TypeError('invalid arg: attend_url')
        if attend_url:
            self._attend_url = attend_url
            logger.info('attend_url: %s', attend_url)
        if not isinstance(interaction_url, str):
            raise TypeError('invalid arg: interaction_url')
        if interaction_url:
            self._interaction_url = interaction_url
            logger.info('interaction_url: %s', interaction_url)

    def send_markdown(self, title: str, content: str, phone: str = '', to_debug: bool = False, to_stdout: bool = False):
        ''' 发送markdown，指定phone时尝试@该号码。

        Args:
            title(str): 通知标题
            content(str): 通知内容
            phone(str): 需要@的号码（可选/默认值空）
            to_debug(bool): 发送至主通知群还是调试通知群（可选/默认值False->发送至主通知群）
            to_stdout(bool): 是否将通知重定向到stdout（可选/默认值False）
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'title': title,
            'content': content,
            'phone': phone,
            'to_debug': to_debug,
            'to_stdout': to_stdout
        })

        # 启用调试模式(to_stdout)后，消息将被重定向到stdout
        # 未初始化对应chatbot时，强制打开重定向功能
        if to_debug:
            if not self._chatbot_debug:
                logger.warning('redirect to stdout')
                return
            chatbot = self._chatbot_debug
        else:
            if not self._chatbot:
                logger.warning('redirect to stdout')
                return
            chatbot = self._chatbot
        r = {}
        try:
            if phone:
                r = chatbot.send_markdown(
                    title=title + '@' + phone,
                    text=content,
                    at_mobiles=[phone],
                    is_auto_at=False,
                )
            else:
                r = chatbot.send_markdown(title=title, text=content)
            logger.debug('send_markdown result: %s', r)
            if r['errcode']:
                logger.error('send_markdown error: %s', r['errmsg'])
        except:
            logger.error('send_markdown error', exc_info=True)
        finally:
            mysql.t_log.add_message(
                'dingtalk',
                'to_debug' if to_debug else 'to_main',
                title,
                content,
                json.dumps(r),
            )

    def send_action_card(self, content: str, to_debug: bool = False, to_stdout: bool = False):
        ''' 发送（打卡用）action_card。

        Args:
            content(str): 通知内容
            to_debug(bool): 发送至主通知群还是调试通知群（可选/默认值False->发送至主通知群）
            to_stdout(bool): 是否将通知重定向到stdout（可选/默认值False）
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'content': content, 'to_debug': to_debug, 'to_stdout': to_stdout
        })

        # 如果未初始化两个按钮地址，则禁用对应按钮
        # action_card要求必须有按钮，如果两个按钮都未启用，则fallback到markdown
        buttons = []
        if self._attend_url:
            buttons.append(CardItem(title='打卡', url=self._attend_url))
        if self._interaction_url:
            buttons.append(CardItem(title='打机器人', url=self._interaction_url))
        logger.debug('buttons: %s', buttons)
        # 启用调试模式(to_stdout)后，消息将被重定向到stdout
        # 未初始化对应chatbot时，强制打开重定向功能
        if to_debug:
            if not self._chatbot_debug:
                logger.warning('redirect to stdout')
                return
            chatbot = self._chatbot_debug
        else:
            if not self._chatbot:
                logger.warning('redirect to stdout')
                return
            chatbot = self._chatbot
        r = {}
        try:
            if buttons:
                r = chatbot.send_action_card(
                    ActionCard(
                        title='任务状态',
                        text=content,
                        btns=buttons,
                        btn_orientation=1,
                        hide_avatar=1,
                    )
                )
            else:
                r = chatbot.send_markdown(title='任务状态', text=content)
            logger.debug('send_action_card result: %s', r)
            if r['errcode']:
                logger.error('send_action_card error: %s', r['errmsg'])
        except:
            logger.error('send_action_card error', exc_info=True)
        finally:
            mysql.t_log.add_message(
                'dingtalk',
                'to_debug' if to_debug else 'to_main',
                '任务状态',
                content,
                json.dumps(r),
            )
