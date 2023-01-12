# -*- coding: UTF-8 -*-
from flask import Flask, request, g
import ipaddress
import traceback
import datetime
import chinese_calendar
import json
import RM
from multiprocessing import Process

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
# ---主消息队列---
p = Process(target=RM.main_queue, args=(RM.var.q,))
p.start()


@app.before_request
def before_request():
    g.client_ip = request.headers['X-Forwarded-For'].split(',')[0] if 'X-Forwarded-For' in request.headers else request.remote_addr
    ipaddress.ip_address(g.client_ip)
    g.ret = {'result': 0, 'err': '', 'data': {}}
    global p
    if not p.is_alive():
        p = Process(target=RM.main_queue, args=(RM.var.q,))
        p.start()


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
            RM.var.q.put({'command': 'mail', 'kwargs': {}})
    if cron_type == 'attend':
        if chinese_calendar.is_workday(current):
            RM.var.q.put({'command': 'attend', 'kwargs': {}})
    return g.ret


@app.route('/api/mail', methods=['POST'])
def mail():
    submit_text = request.json.get('submit', '[提交审核]')
    finish_text = request.json.get('finish', '[完成审核]')
    RM.var.q.put({
        'command': 'mail', 
        'kwargs': {
            'submit': submit_text if len(submit_text) >= 5 else '[提交审核]', 
            'finish': finish_text if len(finish_text) >= 5 else '[完成审核]',
        },
    })
    return g.ret


@app.route('/api/attend', methods=['POST'])
def attend():
    RM.var.q.put({'command': 'attend', 'kwargs': {}})
    return g.ret


@app.route('/api/history/resend', methods=['POST'])
def resend_history():
    assert 'id' in request.json, '缺少必要参数<id>'
    assert 'to' in request.json, '缺少必要参数<to>'
    RM.var.q.put({
        'command': 'resend', 
        'kwargs': {
            'target': RM.mysql.t_history.fetch(request.json['id']), 
            'to': request.json['to']
        },
    })
    return g.ret


@app.route('/api/current/resend', methods=['POST'])
def resend_current():
    assert 'id' in request.json, '缺少必要参数<id>'
    assert 'to' in request.json, '缺少必要参数<to>'
    RM.var.q.put({
        'command': 'resend', 
        'kwargs': {
            'target': RM.mysql.t_current.fetch(request.json['id']), 
            'to': request.json['to']
        },
    })
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
