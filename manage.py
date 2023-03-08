# -*- coding: UTF-8 -*-
from flask import Flask, request, g
import ipaddress
import traceback
import json
import datetime
import chinese_calendar

import RM

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

@app.before_first_request
def before_first_request():
    import os
    from configparser import ConfigParser
    config = ConfigParser()
    config.read(os.path.join('conf','RM.conf'), encoding='UTF-8')

    # ---运行模式（debug）---
    app.logger.info('---- Initiating mode ----')
    global debug
    debug = config.getboolean('mode', 'debug', fallback=False)
    app.logger.info('debug: {}'.format(debug))

    # ---logger---
    import logging.config
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
        },
        'loggers': { 
            '': {
                'level': 'DEBUG',
                'propagate': False,
                # 'filters': [],
                'handlers': ['console'],
            },
        },
    }
    logging.config.dictConfig(dict_config)

    # ---mysql---
    RM.mysql.init(
        user=config.get('mysql', 'user', fallback='rm'), 
        password=config.get('mysql', 'pass', fallback='rm'), 
        host=config.get('mysql', 'host', fallback='127.0.0.1'), 
        database=config.get('mysql', 'db', fallback='rm'),
        port=config.getint('mysql', 'port', fallback=3306),
    )

    # ---redis---
    global stream
    stream = RM.RedisStream(
        host=config.get('redis', 'host', fallback='127.0.0.1'), 
        password=config.get('redis', 'pass', fallback='rm'), 
    )

    # ---dingtalk---
    global dingtalk
    chatbot = {
        'webhook': config.get('dingtalk', 'webhook', fallback=''),
        'secret': config.get('dingtalk', 'secret', fallback=''),
    }
    chatbot_debug = {
        'webhook': config.get('dingtalk', 'webhook_debug', fallback=''),
        'secret': config.get('dingtalk', 'secret_debug', fallback='')
    }
    dingtalk = RM.Dingtalk(
        chatbot, 
        chatbot_debug,
        config.get('dingtalk', 'attend', fallback=''),
        config.get('dingtalk', 'interaction', fallback=''),
        config.getboolean('dingtalk', 'enable', fallback=False)
    )

    # ---wxwork---
    global wxwork
    wxwork = RM.WXWork(
        config.get('wxwork', 'corpid', fallback=''),
        config.get('wxwork', 'agentid', fallback=''),
        config.get('wxwork', 'secret', fallback=''),
        config.get('wxwork', 'admin_userid', fallback=''),
        config.getboolean('wxwork', 'enable', fallback=False)
    )


def do_attend():
    ''' 打卡提醒函数的主入口。调用后向主通知群发送打卡提示，包含当前任务、分配队列和交互入口。向企业微信发送任务提醒。
    '''
    # 准备通知所需数据
    currents = RM.mysql.t_current.search(page_size=9999)['all']
    # 24小时没有动作的情况下跳过信息输出
    if not currents and (datetime.datetime.now().timestamp() - RM.mysql.t_history.pop()[6] > 86400):
        app.logger.debug('skipped output')
        return
    app.logger.info('currents: {}'.format(currents))
    queue = RM.mysql.t_user.pop(count=9999, hide_busy=False)
    app.logger.info('queue: {}'.format(queue))
    currents_group_by_user_id = {}
    for user_id in [item[0] for item in queue]:
        currents_group_by_user_id[user_id] = []
    for project in currents:
        currents_group_by_user_id[project[3]].append('+'.join(json.loads(project[10]).keys()))

    # 钉钉当前项目
    lines = []
    for project in currents:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(project[5])
        lines.append('- {}{} -> {} ({})'.format(
            '+'.join(json.loads(project[10]).keys()), 
            '/急' if project[8] else '', 
            project[4], 
            '{}d{}h'.format(delta.days, int(delta.seconds / 3600))
        ))
    part1 = '**当前审核任务**\n\n' + '\n'.join(lines) if lines else '**当前无审核任务**'
    # 钉钉分配队列
    part2 = '**分配队列**\n\n' + '\n'.join([
        '1. {}{}'.format(
            row[1],
            ' (+{})'.format(row[5]) if row[5] else ''
        ) for row in queue
    ])
    dingtalk.send_action_card(part1+'\n\n---\n\n'+part2, to_stdout=debug)

    # 微信个人通知
    for idx, item in enumerate(queue):
        if item[3] == 0:
            status = '空闲'
        elif item[3] == 1:
            status = '不审加急'
        elif item[3] == 2:
            status = '不审报告'
        else:
            status = '未知'
        content = '===== 状态通知 =====\n\n你的状态: {}\n你的分配顺位: {}{}'.format(
            status, 
            idx + 1 if item[6] == 0 else '跳过一篇', 
            ' (+{}页)'.format(item[4]) if item[4] else ''
        )
        if currents_group_by_user_id[item[0]]:
            content += '\n你当前有{}个审核任务:\n'.format(item[5]) + '\n'.join(currents_group_by_user_id[item[0]])
        wxwork.send_text(content, to=[item[0]], to_stdout=debug)


@app.before_request
def before_request():
    g.client_ip = request.headers['X-Forwarded-For'].split(',')[0] if 'X-Forwarded-For' in request.headers else request.remote_addr
    ipaddress.ip_address(g.client_ip)
    g.ret = {'result': 0, 'err': '', 'data': {}}


@app.errorhandler(400)
def handle_BadRequest(err):
    g.ret['result'] = 1
    g.ret['err'] = traceback.format_exc(limit=1)
    return g.ret, 400


@app.errorhandler(AssertionError)
def handle_AssertionError(err):
    g.ret['result'] = 2
    g.ret['err'] = traceback.format_exc(limit=1)
    return g.ret, 400


@app.errorhandler(Exception)
def handle_Exception(err):
    g.ret['result'] = 3
    g.ret['err'] = traceback.format_exc(limit=1)
    return g.ret, 500


@app.after_request
def after_request(response):
    RM.mysql.t_audit.add(
        g.client_ip,
        request.headers.get('User-Agent'),
        request.full_path,
        request.json if request.data else {},
        g.ret
    )
    return response


@app.route('/api/cron', methods=['GET', 'POST'])
def cron():
    cron_type = request.args['type']
    assert cron_type in ['mail', 'attend'], 'no cron route'
    current = datetime.datetime.now()
    if cron_type == 'mail':
        if chinese_calendar.is_workday(current) and current.hour >= 9 and current.hour < 17:
            stream.add(command='receive', kwargs={})
    if cron_type == 'attend':
        if chinese_calendar.is_workday(current):
            do_attend()
            RM.mysql.t_user.reset_status()
            stream.trim()
    return g.ret


@app.route('/api/mail', methods=['POST'])
def mail():
    submit_text = request.json.get('submit', '[提交审核]')
    finish_text = request.json.get('finish', '[完成审核]')
    stream.add(
        command='receive', 
        kwargs={
            'submit': submit_text if len(submit_text) >= 5 else '[提交审核]', 
            'finish': finish_text if len(finish_text) >= 5 else '[完成审核]',
        },
    )
    return g.ret


@app.route('/api/history/resend', methods=['POST'])
def resend_history():
    assert RM.mysql.t_history.fetch(request.json['id']), '缺少必要参数<id>'
    stream.add(
        command='resend', 
        kwargs={
            'id': request.json['id'], 
            'redirect': request.json.get('to', ''),
        },
    )
    return g.ret


@app.route('/api/current/resend', methods=['POST'])
def resend_current():
    assert RM.mysql.t_current.fetch(request.json['id']), '缺少必要参数<id>'
    stream.add(
        command='resend', 
        kwargs={
            'id': request.json['id'], 
            'redirect': request.json.get('to', ''),
        },
    )
    return g.ret


@app.route('/api2/history/search', methods=['POST'])
def search_history():
    g.ret['data']['history'] = []
    kwargs = {}
    for key, value in request.json.items():
        if key in ['code', 'name', 'company']:
            kwargs[key] = value
        elif key == 'author':
            user_ids = RM.mysql.t_user.search(name=request.json['author'])['user'] + RM.mysql.t_user.search(user_id=request.json['author'])['user']
            if len(user_ids) == 1:
                kwargs['author_id'] = user_ids[0][0]
        elif key == 'current':
            kwargs['page_index'] = value
        elif key == 'pageSize':
            kwargs['page_size'] = value
    keys = ['id', 'author_id', 'author_name', 'reviewer_id', 'reviewer_name', 'start', 'end', 'page', 'urgent', 'company', 'names']
    ret = RM.mysql.t_history.search(**kwargs)
    for row in ret['all']:
        g.ret['data']['history'].append(dict(zip(keys, row)))
        g.ret['data']['history'][-1]['names'] = json.loads(g.ret['data']['history'][-1]['names'])
    g.ret['data']['total'] = ret['total']
    return g.ret


@app.route('/api2/current/list', methods=['POST'])
def list_current():
    g.ret['data']['current'] = []
    keys = ['id', 'author_id', 'author_name', 'reviewer_id', 'reviewer_name', 'start', 'end', 'page', 'urgent', 'company', 'names']
    ret = RM.mysql.t_current.search(page_size=9999)
    for row in ret['all']:
        g.ret['data']['current'].append(dict(zip(keys, row)))
        g.ret['data']['current'][-1]['names'] = json.loads(g.ret['data']['current'][-1]['names'])
    g.ret['data']['total'] = ret['total']
    return g.ret


@app.route('/api2/current/edit', methods=['POST'])
def edit_current():
    kwargs = {}
    assert 'id' in request.json, '缺少必要参数<id>'
    if 'reviewerID' in request.json:
        kwargs['reviewerid'] = request.json['reviewerID']
    if 'page' in request.json:
        assert int(request.json['page']) > 0, '无效参数<page>'
        kwargs['pages'] = request.json['page']
    if 'urgent' in request.json:
        assert type(request.json['urgent']) == bool, '无效参数<urgent>'
        kwargs['urgent'] = request.json['urgent']
    RM.mysql.t_current.edit(request.json['id'], **kwargs)
    return g.ret


@app.route('/api2/current/delete', methods=['POST'])
def delete_current():
    assert 'id' in request.json, '缺少必要参数<id>'
    RM.mysql.t_current.delete(request.json['id'], 0, force=True)
    return g.ret


@app.route('/api2/user/list', methods=['POST'])
def list_user():
    g.ret['data']['user'] = []
    assert type(request.json.get('isReviewer', False)) == bool, '无效参数<isReviewer>'
    keys = ['id', 'name', 'role', 'status']
    for row in RM.mysql.t_user.search(only_reviewer=request.json.get('isReviewer', False))['user']:
        g.ret['data']['user'].append(dict(zip(keys, [row[0], row[1], row[3], row[4]])))
    return g.ret


@app.route('/api2/user/search', methods=['POST'])
def search_user():
    g.ret['data']['user'] = []
    keys = ['id', 'name', 'role', 'status']
    for row in RM.mysql.t_user.search(
        user_id=request.json.get('id', ''),
        name=request.json.get('name', ''),
    )['user']:
        g.ret['data']['user'].append(dict(zip(keys, [row[0], row[1], row[3], row[4]])))
    return g.ret


@app.route('/api2/queue/list', methods=['POST'])
def list_queue():
    g.ret['data']['queue'] = []
    keys = ['id', 'name', 'role', 'status', 'pages_diff', 'current', 'skipped']
    for row in RM.mysql.t_user.pop(count=9999, hide_busy=False):
        g.ret['data']['queue'].append(dict(zip(keys, row)))
    return g.ret


@app.route('/api2/user/status', methods=['POST'])
def user_status():
    assert 'id' in request.json, '缺少必要参数<id>'
    assert 'status' in request.json, '缺少必要参数<status>'
    RM.mysql.t_user.set_status(request.json['id'], request.json['status'])
    return g.ret


if __name__ == "__main__":
    from flask_cors import CORS
    CORS(app, resources={r"*": {"origins": "*"}})
    app.run(debug=True)