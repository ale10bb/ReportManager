# -*- coding: UTF-8 -*-
''' 审核管理机器人
'''
import os
import logging, logging.config
from configparser import ConfigParser
import requests
from . import mysql, mail, archive, dingtalk, wxwork
from . import var
from .handler import do_attend, do_mail, do_resend
from .handler import main_queue

config = ConfigParser()
config.read(os.path.join('conf','RM.conf'), encoding='UTF-8')

# ---外部存储---
var.storage = config.get('path', 'storage', fallback=os.path.join(os.getcwd(), 'storage'))
## 自动创建目录结构
for check_dir in [os.path.join(var.storage, child_dir) for child_dir in ['temp', 'archive']]:
    if os.path.isdir(check_dir):
        continue
    os.mkdir(check_dir)

# ---日志文件---
dict_config = {
    'version': 1,
    'formatters': {
        'main': {
            'format': '%(asctime)s - %(levelname)s - %(name)s/%(funcName)s:%(lineno)d -> %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
            # 'style': '%',
            # 'validate': True,
        },
    },
    # 'filters': {},
    'handlers': {
        'console': {
            'class' : 'logging.StreamHandler',
            'formatter': 'main',
            'level': 'DEBUG',
            # 'filters': '',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class' : 'logging.handlers.RotatingFileHandler',
            'formatter': 'main',
            'level': config.get('log', 'level', fallback='INFO').upper(),
            # 'filters': '',
            'filename': os.path.join(var.storage, os.path.basename(config.get('log', 'dest', fallback=''))),
            'maxBytes': 204800,
            'backupCount': 5,
        },
    },
    'loggers': { 
        'RM': {
            'level': 'DEBUG',
            'propagate': False,
            # 'filters': [],
            'handlers': ['console', 'file'],
        },
    },
}
logging.config.dictConfig(dict_config)

logger = logging.getLogger(__name__)
logger.info('storage: {}'.format(var.storage))
logger.info('logging to "{}" ({})'.format(
    dict_config['handlers']['file']['filename'], 
    dict_config['handlers']['file']['level'],
))

# ---运行模式（debug）---
logger.info('---- Initiating mode ----')
# debug默认false
var.debug = config.getboolean('mode', 'debug', fallback=False)
logger.info('debug: {}'.format(var.debug))

# ---mysql---
logger.info('---- Initiating mysql client ----')
mysql.init(
    user=config.get('mysql', 'user', fallback='rm'), 
    password=config.get('mysql', 'pass', fallback='rm'), 
    host=config.get('mysql', 'host', fallback='127.0.0.1'), 
    database=config.get('mysql', 'db', fallback='rm'),
    port=config.getint('mysql', 'port', fallback=3306)
)

# ---mail---
logger.info('---- Initiating mail clients ----')
pop3_config = {
    'username': config.get('pop3', 'user', fallback='rm@example.com'), 
    'password': config.get('pop3', 'pass', fallback='rm'), 
    'host': config.get('pop3', 'host', fallback='example.com'), 
    'port': config.getint('pop3', 'port', fallback=110),
    'ssl': config.getboolean('pop3', 'ssl', fallback=False),
    'tls': config.getboolean('pop3', 'tls', fallback=False),
}
smtp_config = {
    'username': config.get('smtp', 'user', fallback='rm@example.com'), 
    'password': config.get('smtp', 'pass', fallback='rm'), 
    'host': config.get('smtp', 'host', fallback='example.com'), 
    'port': config.getint('smtp', 'port', fallback=25),
    'ssl': config.getboolean('smtp', 'ssl', fallback=False),
    'tls': config.getboolean('smtp', 'tls', fallback=False),
}
mail_config = {
    'default_domain': config.get('mail', 'domain', fallback='example.com'),
    'default_cc': config.get('mail', 'manager', fallback=''),
    'max_attachments_size': config.getint('smtp', 'max_size', fallback=25),
    'large_attachment_handler': config.get('dedicate', 'large_attachment', fallback='')
}
mail.init(pop3_config, smtp_config, mail_config)

# ---archive---
logger.info('---- Initiating archive client ----')
bin_path = {
    'winrar': config.get('archive', 'winrar_bin', fallback='C:\\Program Files\\WinRAR\\WinRAR.exe'),
    'rar': config.get('archive', 'rar_bin', fallback='rar'),
    'unrar': config.get('archive', 'unrar_bin', fallback='unrar'),
    'unar': config.get('archive', 'unar_bin', fallback='unar')
}
archive.init(bin_path, config.get('archive', 'pass', fallback=''))

# ---dingtalk---
logger.info('---- Initiating dingtalk client ----')
chatbot = {
    'webhook': config.get('dingtalk', 'webhook', fallback=''),
    'secret': config.get('dingtalk', 'secret', fallback=''),
}
chatbot_debug = {
    'webhook': config.get('dingtalk', 'webhook_debug', fallback=''),
    'secret': config.get('dingtalk', 'secret_debug', fallback='')
}
dingtalk.init(
    chatbot, 
    chatbot_debug,
    config.get('dingtalk', 'attend', fallback=''),
    config.get('dingtalk', 'interaction', fallback=''),
    config.getboolean('dingtalk', 'enable', fallback=False)
)

# ---wework---
logger.info('---- Initiating wework client ----')
wxwork.init(
    config.get('wework', 'corpid', fallback=''),
    config.get('wework', 'agentid', fallback=''),
    config.get('wework', 'secret', fallback=''),
    config.get('wework', 'admin_userid', fallback=''),
    config.getboolean('wework', 'enable', fallback=False)
)

# ---win32---
logger.info('---- Initiating dedicate_win32 ----')
dedicate_win32_to_test = config.get('dedicate', 'win32', fallback='')
if dedicate_win32_to_test:
    try:
        with open(os.path.join('res', 'test_win32.doc'),'rb') as f:
            files = {'document': f}
            r = requests.post(dedicate_win32_to_test, files=files, timeout=60).json()
        assert not r['result'], r['err']
        assert r['data']['page'] == 1
        assert r['data']['converted']['name'] == 'test_win32.docx'
        logger.info('dedicate_win32: {}'.format(dedicate_win32_to_test))
        var.dedicate_win32 = dedicate_win32_to_test
    except:
        logger.warning('invalid dedicate_win32', exc_info=True)
        var.dedicate_win32 = ''
