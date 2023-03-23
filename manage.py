# -*- coding: UTF-8 -*-
from functools import wraps

from flask import Flask, request, g, abort
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended import JWTManager

import os
import ipaddress
import datetime
import chinese_calendar

from RM import mysql
from RM.dingtalk import Dingtalk
from RM.redis import RedisStream
from RM.wxwork import WXWork


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
    config.read(os.path.join('conf', 'RM.conf'), encoding='UTF-8')

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
                'class': 'logging.StreamHandler',
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
    mysql.init(
        user=config.get('mysql', 'user', fallback='rm'),
        password=config.get('mysql', 'pass', fallback='rm'),
        host=config.get('mysql', 'host', fallback='127.0.0.1'),
        database=config.get('mysql', 'db', fallback='rm'),
        port=config.getint('mysql', 'port', fallback=3306),
    )

    # ---redis---
    global stream
    stream = RedisStream(
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
    dingtalk = Dingtalk(
        chatbot,
        chatbot_debug,
        config.get('dingtalk', 'attend', fallback=''),
        config.get('dingtalk', 'interaction', fallback=''),
    )

    # ---wxwork---
    global wxwork
    wxwork = WXWork(
        config.get('wxwork', 'corpid', fallback=''),
        config.getint('wxwork', 'agentid', fallback=0),
        config.get('wxwork', 'secret', fallback=''),
        config.get('wxwork', 'admin_userid', fallback=''),
    )


def do_attend():
    ''' 任务提醒入口，功能包括：
    
    1. 向主通知群发送打卡提示，包含当前任务、分配队列和交互入口
    2. 向企业微信发送任务提醒
    '''
    # 准备通知所需数据
    currents = mysql.t_current.search(page_size=9999)['current']
    # 24小时没有动作的情况下跳过信息输出
    if not currents and (datetime.datetime.now().timestamp() - mysql.t_history.pop()['end'] > 86400):
        app.logger.info('skipped output')
        return
    queue = mysql.t_user.pop(count=9999, hide_busy=False)
    currents_group_by_user_id = {user['id']: [] for user in queue}
    for record in currents:
        currents_group_by_user_id[record['authorid']].append(
            '+'.join(record['names']))
    app.logger.debug('currents: %s', currents_group_by_user_id)

    # 钉钉当前项目
    lines = []
    for record in currents:
        delta = datetime.datetime.now(
        ) - datetime.datetime.fromtimestamp(record['start'])
        lines.append('- {}{} -> {} ({})'.format(
            '+'.join(record['names']),
            '/急' if record['urgent'] else '',
            record['reviewername'],
            f'{delta.days}d{int(delta.seconds / 3600)}h',
        ))
    part1 = '**当前审核任务**\n\n' + '\n'.join(lines) if lines else '**当前无审核任务**'
    # 钉钉分配队列
    part2 = '**分配队列**\n\n' + '\n'.join([
        '1. {}{}'.format(
            user['name'],
            f" (+{user['pages_diff']})" if user['pages_diff'] else ''
        ) for user in queue
    ])
    dingtalk.send_action_card(part1+'\n\n---\n\n'+part2, to_stdout=debug)

    # 微信个人通知
    for idx, user in enumerate(queue):
        if user['status'] == 0:
            status = '空闲'
        elif user['status'] == 1:
            status = '不审加急'
        elif user['status'] == 2:
            status = '不审报告'
        else:
            status = '未知'
        content = '===== 状态通知 =====\n\n你的状态: {}\n你的分配顺位: {}{}'.format(
            status,
            idx + 1 if user['skipped'] == 0 else '跳过一篇',
            f" (+{user['pages_diff']}页)" if user['pages_diff'] else ''
        )
        if currents_group_by_user_id[user['id']]:
            content += f"\n你当前有{user['current']}个审核任务:\n" + \
                '\n'.join(currents_group_by_user_id[user['id']])
        wxwork.send_text(content, to=[user['id']], to_stdout=debug)


@app.before_request
def before_request():
    app.logger.debug('path: %s', request.path)
    g.client_ip = request.headers['X-Forwarded-For'].split(',')[0] \
        if 'X-Forwarded-For' in request.headers else request.remote_addr
    try:
        ipaddress.ip_address(g.client_ip)
    except ValueError as err:
        abort(400, err)
    g.ret = {'result': 0, 'err': '', 'data': {}}


@app.errorhandler(400)
def handle_BadRequest(err):
    app.logger.info('BadRequest: %s', err.description)
    g.ret['result'] = 400
    g.ret['err'] = err.description
    return g.ret, 400


@app.errorhandler(KeyError)
def handle_KeyError(err):
    app.logger.info('KeyError: %s', err)
    g.ret['result'] = 400
    g.ret['err'] = f"Inappropriate key: {err}"
    return g.ret, 400


@app.errorhandler(Exception)
def handle_Exception(err):
    app.logger.info('Exception: %s', err)
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
            mysql.t_log.add_manage(
                g.client_ip,
                g.user_id,
                request.headers.get('User-Agent', ''),
                request.path,
                param
            )
            return fn(*args, **kwargs)
        return decorator
    return wrapper


@app.route('/api/auth', methods=['POST'])
def auth():
    code = request.json.get('code', '')
    user_id = wxwork.get_userid(code)
    if mysql.t_user.__contains__(user_id):
        app.logger.info('grant access to "%s"', user_id)
        g.ret['data']['token'] = create_access_token(identity=user_id)
        return g.ret
    else:
        g.ret['result'] = 401
        g.ret['err'] = 'invalid user'
        return g.ret


@app.route('/utils/genToken')
def genToken():
    user_info = mysql.t_user.fetch(request.args['user_id'])
    if user_info:
        return create_access_token(identity=user_info['id'], expires_delta=datetime.timedelta(days=1))
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
                mysql.t_user.reset_status()
                stream.trim()
        case _:
            abort(400, 'Inappropriate argument: type')
    return g.ret


@app.route('/api/mail', methods=['POST'])
@jwt_required()
def mail():
    submit_text = request.json.get('submit', '[提交审核]')
    if not isinstance(submit_text, str):
        abort(400, 'Inappropriate argument: submit')
    finish_text = request.json.get('finish', '[完成审核]')
    if not isinstance(finish_text, str):
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
    if not isinstance(request.json['id'], int):
        abort(400, 'Inappropriate argument: id')
    if not isinstance(request.json.setdefault('to', ''), str):
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
    if not isinstance(request.json['id'], str):
        abort(400, 'Inappropriate argument: id')
    if not isinstance(request.json.setdefault('to', ''), str):
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
            if not isinstance(value, str):
                abort(400, f'Inappropriate argument: {key}')
            kwargs[key] = value
        elif key == 'author':
            if not isinstance(value, str):
                abort(400, 'Inappropriate argument: author')
            user = mysql.t_user.fetch(value)
            if user:
                kwargs['authorid'] = user['id']
            else:
                users = mysql.t_user.search(name=value)
                if len(users) == 1:
                    kwargs['authorid'] = users[0]['id']
        elif key == 'current':
            if not isinstance(value, int):
                abort(400, 'Inappropriate argument: current')
            kwargs['page_index'] = value
        elif key == 'pageSize':
            if not isinstance(value, int):
                abort(400, 'Inappropriate argument: pageSize')
            kwargs['page_size'] = value
    g.ret['data'] = mysql.t_history.search(**kwargs)
    return g.ret


@app.route('/api/current/list', methods=['POST'])
@jwt_required()
def list_current():
    g.ret['data'] = {'current': [], 'total': 0}
    ret = mysql.t_current.search(
        page_size=9999,
        authorid=g.user_id,
    )
    g.ret['data']['current'].extend(ret['current'])
    g.ret['data']['total'] += ret['total']
    ret = mysql.t_current.search(
        page_size=9999,
        reviewerid=g.user_id,
    )
    g.ret['data']['current'].extend(ret['current'])
    g.ret['data']['total'] += ret['total']
    return g.ret


@app.route('/api/current/edit', methods=['POST'])
@jwt_required()
def edit_current():
    kwargs = {}
    if not isinstance(request.json['id'], str):
        abort(400, 'Inappropriate argument: id')
    for key, value in request.json.items():
        if key == 'reviewerID':
            if not isinstance(value, str):
                abort(400, 'Inappropriate argument: reviewerID')
            kwargs['reviewerid'] = value
        elif key == 'page':
            if not isinstance(value, int) or value <= 0:
                abort(400, 'Inappropriate argument: page')
            kwargs['pages'] = value
        elif key == 'urgent':
            if not isinstance(value, bool):
                abort(400, 'Inappropriate argument: urgent')
            kwargs['urgent'] = value
    mysql.t_current.edit(request.json['id'], **kwargs)
    return g.ret


@app.route('/api/current/delete', methods=['POST'])
@jwt_required()
def delete_current():
    if not isinstance(request.json['id'], str):
        abort(400, 'Inappropriate argument: id')
    mysql.t_current.delete(request.json['id'])
    return g.ret


@app.route('/api/user/list', methods=['POST'])
@jwt_required()
def list_user():
    kwargs = {}
    if request.json.get('isReviewer') == True:
        kwargs['only_reviewer'] = True
    g.ret['data']['user'] = mysql.t_user.search(**kwargs)
    for item in g.ret['data']['user']:
        del item['phone']
        del item['email']
        if item['role'] == 0:
            del item['status']
    return g.ret


@app.route('/api/user/search', methods=['POST'])
@jwt_required()
def search_user():
    kwargs = {}
    for key, value in request.json.items():
        if key in ['id', 'name']:
            if not isinstance(value, str):
                abort(400, f'Inappropriate argument: {key}')
            kwargs[key] = value
    g.ret['data']['user'] = mysql.t_user.search(**kwargs)
    for item in g.ret['data']['user']:
        del item['phone']
        del item['email']
        if item['role'] == 0:
            del item['status']
    return g.ret


@app.route('/api/queue/list', methods=['POST'])
@jwt_required()
def list_queue():
    g.ret['data']['queue'] = mysql.t_user.pop(count=9999, hide_busy=False)
    return g.ret


@app.route('/api/user/info', methods=['POST'])
@jwt_required()
def user_info():
    for idx, item in enumerate(mysql.t_user.pop(count=9999, hide_busy=False)):
        if item['id'] == g.user_id:
            g.ret['data']['user'] = item
            del g.ret['data']['user']['phone']
            del g.ret['data']['user']['email']
            g.ret['data']['user']['priority'] = idx + 1
            break
    else:
        ret = mysql.t_user.fetch(user_id=g.user_id)
        if ret:
            g.ret['data']['user'] = ret
            del g.ret['data']['user']['phone']
            del g.ret['data']['user']['email']
    return g.ret


@app.route('/api/user/status', methods=['POST'])
@jwt_required()
def user_status():
    if not request.json['status'] in [0, 1, 2]:
        abort(400, 'Inappropriate argument: status')
    mysql.t_user.set_status(g.user_id, request.json['status'])
    return g.ret


if __name__ == "__main__":
    from flask_cors import CORS
    CORS(app, resources={r"*": {"origins": "*"}})
    app.run(debug=True)
