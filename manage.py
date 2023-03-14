# -*- coding: UTF-8 -*-
from functools import wraps

from flask import Flask, request, g, abort
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended import JWTManager

import os
import ipaddress
import json
import datetime
import chinese_calendar

import RM

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JWT_SECRET_KEY'] = os.urandom(12)
app.config['JWT_ERROR_MESSAGE_KEY'] = 'err'
jwt = JWTManager(app)

@app.before_first_request
def before_first_request():
    import os
    from configparser import ConfigParser
    config = ConfigParser()
    config.read(os.path.join('conf','RM.conf'), encoding='UTF-8')

    # ---运行模式（debug）---
    global debug
    debug = config.getboolean('mode', 'debug', fallback=False)

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
    app.logger.debug('path: {}'.format(request.path))
    g.client_ip = request.headers['X-Forwarded-For'].split(',')[0] if 'X-Forwarded-For' in request.headers else request.remote_addr
    try:
        ipaddress.ip_address(g.client_ip)
    except ValueError as err:
        abort(400, err)
    g.ret = {'result': 0, 'err': '', 'data': {}}


@app.errorhandler(400)
def handle_BadRequest(err):
    g.ret['result'] = 400
    g.ret['err'] = err.description
    return g.ret, 400


@app.errorhandler(KeyError)
def handle_BadRequest(err):
    g.ret['result'] = 400
    g.ret['err'] = 'Inappropriate key: {}'.format(err)
    return g.ret, 400


@app.errorhandler(Exception)
def handle_Exception(err):
    g.ret['result'] = 3
    g.ret['err'] = str(err)
    return g.ret, 500


def jwt_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request(optional=app.config['DEBUG'])
            g.user_id = get_jwt_identity()
            param = {}
            try:
                param.update(request.args)
                param.update(request.json)
            except:
                pass
            RM.mysql.t_audit.add(g.client_ip, g.user_id, request.headers.get('User-Agent', ''), request.path, param)
            return fn(*args, **kwargs)
        return decorator
    return wrapper


@app.route('/api/auth', methods=['POST'])
def auth():
    code = request.json.get('code', '')
    user_id = wxwork.get_userid(code)
    if RM.mysql.t_user.__contains__(user_id):
        app.logger.info('grant access to {}'.format(user_id))
        g.ret['data']['token'] = create_access_token(identity=user_id)
        return g.ret
    else:
        g.ret['result'] = 401
        g.ret['err'] = 'invalid user'
        return g.ret
    

@app.route('/utils/genToken')
def genToken():
    user_info = RM.mysql.t_user.fetch(request.args['user_id'])
    if user_info:
        return create_access_token(identity=user_info[0], expires_delta=datetime.timedelta(days=1))
    else:
        return ''


@app.route('/api/redirect', methods=['POST'])
def get_redirect_url():
    g.ret['data']['url'] = wxwork.get_redirect(host=request.host)
    return g.ret


@app.route('/api/cron', methods=['GET', 'POST'])
def cron():
    current = datetime.datetime.now()
    match request.args['type']:
        case 'mail':
            if chinese_calendar.is_workday(current) and current.hour >= 9 and current.hour < 17:
                stream.add(command='receive', kwargs={})
        case 'attend':
            if chinese_calendar.is_workday(current):
                do_attend()
                RM.mysql.t_user.reset_status()
                stream.trim()
        case _:
            abort(400, 'Inappropriate argument: type')
    return g.ret


@app.route('/api/mail', methods=['POST'])
@jwt_required()
def mail():
    submit_text = request.json.get('submit', '[提交审核]')
    if type(submit_text) != str:
        abort(400, 'Inappropriate argument: submit')
    finish_text = request.json.get('finish', '[完成审核]')
    if type(submit_text) != str:
        abort(400, 'Inappropriate argument: finish')
    stream.add(
        command='receive', 
        kwargs={
            'submit': submit_text if len(submit_text) >= 5 else '[提交审核]', 
            'finish': finish_text if len(finish_text) >= 5 else '[完成审核]',
        },
    )
    return g.ret


@app.route('/api/history/resend', methods=['POST'])
@jwt_required()
def resend_history():
    if type(request.json['id']) != int:
        abort(400, 'Inappropriate argument: id')
    if type(request.json.setdefault('to', '')) != str:
        abort(400, 'Inappropriate argument: to')
    stream.add(
        command='resend', 
        kwargs={
            'id': request.json['id'], 
            'redirect': request.json['to'],
        },
    )
    return g.ret


@app.route('/api/current/resend', methods=['POST'])
@jwt_required()
def resend_current():
    if type(request.json['id']) != str:
        abort(400, 'Inappropriate argument: id')
    if type(request.json.setdefault('to', '')) != str:
        abort(400, 'Inappropriate argument: to')
    stream.add(
        command='resend', 
        kwargs={
            'id': request.json['id'], 
            'redirect': request.json['to'],
        },
    )
    return g.ret


@app.route('/api/history/search', methods=['POST'])
@jwt_required()
def search_history():
    g.ret['data']['history'] = []
    kwargs = {}
    for key, value in request.json.items():
        if key in ['code', 'name', 'company']:
            if type(value) != str:
                abort(400, 'Inappropriate argument: {}'.format(key))
            kwargs[key] = value
        elif key == 'author':
            if type(value) != str:
                abort(400, 'Inappropriate argument: author')
            user_ids = RM.mysql.t_user.search(name=value) + RM.mysql.t_user.search(user_id=value)
            if len(user_ids) == 1:
                kwargs['author_id'] = user_ids[0][0]
        elif key == 'current':
            if type(value) != int:
                abort(400, 'Inappropriate argument: current')
            kwargs['page_index'] = value
        elif key == 'pageSize':
            if type(value) != int:
                abort(400, 'Inappropriate argument: pageSize')
            kwargs['page_size'] = value
    keys = ['id', 'author_id', 'author_name', 'reviewer_id', 'reviewer_name', 'start', 'end', 'page', 'urgent', 'company', 'names']
    ret = RM.mysql.t_history.search(**kwargs)
    for row in ret['all']:
        g.ret['data']['history'].append(dict(zip(keys, row)))
        g.ret['data']['history'][-1]['names'] = json.loads(g.ret['data']['history'][-1]['names'])
    g.ret['data']['total'] = ret['total']
    return g.ret


@app.route('/api/current/list', methods=['POST'])
@jwt_required()
def list_current():
    g.ret['data']['current'] = []
    keys = ['id', 'author_id', 'author_name', 'reviewer_id', 'reviewer_name', 'start', 'end', 'page', 'urgent', 'company', 'names']
    ret = RM.mysql.t_current.search(user_id=g.user_id, page_size=9999)
    for row in ret['submit']:
        g.ret['data']['current'].append(dict(zip(keys, row)))
        g.ret['data']['current'][-1]['names'] = json.loads(g.ret['data']['current'][-1]['names'])
    for row in ret['review']:
        g.ret['data']['current'].append(dict(zip(keys, row)))
        g.ret['data']['current'][-1]['names'] = json.loads(g.ret['data']['current'][-1]['names'])
    g.ret['data']['total'] = len(ret['submit']) + len(ret['review'])
    return g.ret


@app.route('/api/current/edit', methods=['POST'])
@jwt_required()
def edit_current():
    kwargs = {}
    if type(request.json['id']) != str:
        abort(400, 'Inappropriate argument: id')
    for key, value in request.json.items():
        if key == 'reviewerID':
            if type(value) != str:
                abort(400, 'Inappropriate argument: reviewerID')
            kwargs['reviewerid'] = value
        elif key == 'page':
            if type(value) != int or value <= 0:
                abort(400, 'Inappropriate argument: page')
            kwargs['pages'] = value
        elif key == 'urgent':
            if type(value) != bool:
                abort(400, 'Inappropriate argument: urgent')
            kwargs['urgent'] = value
    RM.mysql.t_current.edit(request.json['id'], **kwargs)
    return g.ret


@app.route('/api/current/delete', methods=['POST'])
@jwt_required()
def delete_current():
    if type(request.json['id']) != str:
        abort(400, 'Inappropriate argument: id')
    RM.mysql.t_current.delete(request.json['id'], 0, force=True)
    return g.ret


@app.route('/api/user/list', methods=['POST'])
@jwt_required()
def list_user():
    g.ret['data']['user'] = []
    if type(request.json.setdefault('isReviewer', False)) != bool:
        abort(400, 'Inappropriate argument: isReviewer')
    keys = ['id', 'name', 'role', 'status']
    for row in RM.mysql.t_user.search(only_reviewer=request.json['isReviewer']):
        g.ret['data']['user'].append(dict(zip(keys, [row[0], row[1], row[4], row[5]])))
    return g.ret


@app.route('/api/user/search', methods=['POST'])
@jwt_required()
def search_user():
    if type(request.json.setdefault('id', '')) != str:
        abort(400, 'Inappropriate argument: id')
    if type(request.json.setdefault('name', '')) != str:
        abort(400, 'Inappropriate argument: name')
    g.ret['data']['user'] = []
    keys = ['id', 'name', 'role', 'status']
    for row in RM.mysql.t_user.search(user_id=request.json['id'], name=request.json['name']):
        g.ret['data']['user'].append(dict(zip(keys, [row[0], row[1], row[4], row[5]])))
    return g.ret


@app.route('/api/queue/list', methods=['POST'])
@jwt_required()
def list_queue():
    g.ret['data']['queue'] = []
    keys = ['id', 'name', 'role', 'status', 'pages_diff', 'current', 'skipped']
    for row in RM.mysql.t_user.pop(count=9999, hide_busy=False):
        g.ret['data']['queue'].append(dict(zip(keys, row)))
    return g.ret


@app.route('/api/user/info', methods=['POST'])
@jwt_required()
def user_info():
    keys = ['id', 'name', 'role', 'status', 'pages_diff', 'current', 'skipped', 'priority']
    for idx, row in enumerate(RM.mysql.t_user.pop(count=9999, hide_busy=False)):
        if row[0] == g.user_id:
            g.ret['data']['user'] = dict(zip(keys, list(row) + [idx + 1]))
            break
    else:
        keys = ['id', 'name', 'role']
        row = RM.mysql.t_user.fetch(user_id=g.user_id)
        g.ret['data']['user'] = (dict(zip(keys, [row[0], row[1], row[4]])))
    return g.ret


@app.route('/api/user/status', methods=['POST'])
@jwt_required()
def user_status():
    if type(request.json['status']) != int:
        abort(400, 'Inappropriate argument: status')
    RM.mysql.t_user.set_status(g.user_id, request.json['status'])
    return g.ret


if __name__ == "__main__":
    from flask_cors import CORS
    CORS(app, resources={r"*": {"origins": "*"}})
    app.run(debug=True)
