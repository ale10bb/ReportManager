# -*- coding: UTF-8 -*-
from flask import Flask, request
from werkzeug.exceptions import BadRequest
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


def get_client_ip(request):
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.remote_addr


@app.route('/api/cron', methods=['GET', 'POST'])
def cron():
    global p
    if not p.is_alive():
        p = Process(target=RM.main_queue, args=(RM.var.q,))
        p.start()
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        cron_type = request.args['type']
        assert cron_type in ['mail', 'attend'], 'no cron route'
        current = datetime.datetime.now()
        if cron_type == 'mail':
            if chinese_calendar.is_workday(current) and current.hour >= 9 and current.hour < 17:
                RM.var.q.put({'command': 'mail', 'kwargs': {}})
        if cron_type == 'attend':
            if chinese_calendar.is_workday(current):
                RM.var.q.put({'command': 'attend', 'kwargs': {}})
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        return ret, status_code


@app.route('/api/mail', methods=['POST'])
def mail():
    global p
    if not p.is_alive():
        p = Process(target=RM.main_queue, args=(RM.var.q,))
        p.start()
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        request_body = {}
        request_body.update(request.json)
        submit_text = request_body.get('submit', '[提交审核]')
        finish_text = request_body.get('finish', '[完成审核]')
        if len(submit_text) < 5:
            submit_text = '[提交审核]'
        if len(finish_text) < 5:
            finish_text = '[完成审核]'
        RM.var.q.put({'command': 'mail', 'kwargs': {'submit': submit_text, 'finish': finish_text}})
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api/attend', methods=['POST'])
def attend():
    global p
    if not p.is_alive():
        p = Process(target=RM.main_queue, args=(RM.var.q,))
        p.start()
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        request_body = {}
        request_body.update(request.json)
        RM.var.q.put({'command': 'attend', 'kwargs': {}})
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api/history/resend', methods=['POST'])
def resend_history():
    global p
    if not p.is_alive():
        p = Process(target=RM.main_queue, args=(RM.var.q,))
        p.start()
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        request_body = {}
        request_body.update(request.json)
        assert 'id' in request_body, '缺少必要参数<id>'
        assert 'to' in request_body, '缺少必要参数<to>'
        RM.var.q.put({
            'command': 'resend', 
            'kwargs': {
                'target': RM.mysql.t_history.fetch(request_body['id']), 
                'to': request_body['to']
            },
        })
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api/current/resend', methods=['POST'])
def resend_current():
    global p
    if not p.is_alive():
        p = Process(target=RM.main_queue, args=(RM.var.q,))
        p.start()
    ret = {'result': 0, 'err': '', 'data': {}}

    try:
        request_body = {}
        request_body.update(request.json)
        assert 'id' in request_body, '缺少必要参数<id>'
        assert 'to' in request_body, '缺少必要参数<to>'
        RM.var.q.put({
            'command': 'resend', 
            'kwargs': {
                'target': RM.mysql.t_current.fetch(request_body['id']), 
                'to': request_body['to']
            },
        })
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/history/search', methods=['POST'])
def search_history():
    ret = {'result': 0, 'err': '', 'data': {'history': []}}
    try:
        request_body = {}
        request_body.update(request.json)
        kwargs = {}
        if 'code' in request_body:
            kwargs['code'] = request_body['code']
        if 'name' in request_body:
            kwargs['name'] = request_body['name']
        if 'company' in request_body:
            kwargs['company'] = request_body['company']
        if 'author' in request_body:
            user_ids = RM.mysql.t_user.search(name=request_body['author'])['user'] + RM.mysql.t_user.search(user_id=request_body['author'])['user']
            if len(user_ids) == 1:
                kwargs['author_id'] = user_ids[0][0]
        keys = ['id', 'author_id', 'author_name', 'reviewer_id', 'reviewer_name', 'start', 'end', 'page', 'urgent', 'company', 'names']
        for row in RM.mysql.t_history.search(**kwargs)['all']:
            ret['data']['history'].append(dict(zip(keys, row)))
            ret['data']['history'][-1]['names'] = json.loads(ret['data']['history'][-1]['names'])
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/current/list', methods=['POST'])
def list_current():
    ret = {'result': 0, 'err': '', 'data': {'current': []}}
    try:
        request_body = {}
        request_body.update(request.json)
        keys = ['id', 'author_id', 'author_name', 'reviewer_id', 'reviewer_name', 'start', 'end', 'page', 'urgent', 'company', 'names']
        for row in RM.mysql.t_current.search()['all']:
            ret['data']['current'].append(dict(zip(keys, row)))
            ret['data']['current'][-1]['names'] = json.loads(ret['data']['current'][-1]['names'])
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/current/edit', methods=['POST'])
def edit_current():
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        request_body = {}
        request_body.update(request.json)
        kwargs = {}
        assert 'id' in request_body, '缺少必要参数<id>'
        if 'reviewerID' in request_body:
            kwargs['reviewerid'] = request_body['reviewerID']
        if 'page' in request_body:
            assert int(request_body['page']) > 0, '无效参数<page>'
            kwargs['pages'] = request_body['page']
        if 'urgent' in request_body:
            assert type(request_body['urgent']) == bool, '无效参数<urgent>'
            kwargs['urgent'] = request_body['urgent']
        RM.mysql.t_current.edit(request_body['id'], **kwargs)
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/current/delete', methods=['POST'])
def delete_current():
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        request_body = {}
        request_body.update(request.json)
        assert 'id' in request_body, '缺少必要参数<id>'
        RM.mysql.t_current.delete(request_body['id'], 0, force=True)
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/user/list', methods=['POST'])
def list_user():
    ret = {'result': 0, 'err': '', 'data': {'user': []}}
    try:
        request_body = {}
        request_body.update(request.json)
        assert type(request_body.get('isReviewer', False)) == bool, '无效参数<isReviewer>'
        keys = ['id', 'name', 'phone', 'role', 'status']
        for row in RM.mysql.t_user.search(only_reviewer=request_body.get('isReviewer', False))['user']:
            ret['data']['user'].append(dict(zip(keys, row)))
            ret['data']['user'][-1]['phone'] = ''
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/user/search', methods=['POST'])
def search_user():
    ret = {'result': 0, 'err': '', 'data': {'user': []}}
    try:
        request_body = {}
        request_body.update(request.json)
        keys = ['id', 'name', 'phone', 'role', 'status']
        for row in RM.mysql.t_user.search(
            user_id=request_body.get('id', ''),
            name=request_body.get('name', ''),
        )['user']:
            ret['data']['user'].append(dict(zip(keys, row)))
            ret['data']['user'][-1]['phone'] = ''
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/queue/list', methods=['POST'])
def list_queue():
    ret = {'result': 0, 'err': '', 'data': {'normal': [], 'urgent': [], 'exclude': []}}
    try:
        request_body = {}
        request_body.update(request.json)
        keys = ['id', 'name', 'phone', 'role', 'status', 'pages_diff', 'current']
        for row in RM.mysql.t_user.pop(count=9999, urgent=False, hide_busy=False):
            ret['data']['normal'].append(dict(zip(keys, row)))
            ret['data']['normal'][-1]['phone'] = ''
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code


@app.route('/api2/user/status', methods=['POST'])
def user_status():
    ret = {'result': 0, 'err': '', 'data': {}}
    try:
        request_body = {}
        request_body.update(request.json)
        assert 'id' in request_body, '缺少必要参数<id>'
        assert 'status' in request_body, '缺少必要参数<status>'
        RM.mysql.t_user.set_status(request_body['id'], request_body['status'])
        status_code = 200
    except BadRequest as err:
        ret['result'] = 1
        ret['err'] = '{}'.format(err)
        status_code = 400
    except (AssertionError,) as err:
        ret['result'] = 2
        ret['err'] = '{}'.format(err)
        status_code = 500
    except Exception as err:
        ret['result'] = 3
        ret['err'] = '{}'.format(err)
        status_code = 500
    finally:
        RM.mysql.t_audit.add(
            get_client_ip(request),
            request.headers.get('User-Agent'),
            request.path,
            request_body,
            ret
        )
        return ret, status_code
