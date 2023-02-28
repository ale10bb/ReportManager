# -*- coding: UTF-8 -*-
from flask import Flask, request, g
import traceback
from werkzeug.utils import secure_filename
import os.path
import tempfile
import win32com.client, pythoncom
import re

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.logger.setLevel('DEBUG')


@app.before_request
def before_request():
    g.ret = {
        'result': 0, 
        'err': '', 
        'data': {
            'filename': request.files['document'].filename, 
            'page': 0, 
            'code': '', 
            'name': '', 
            'company': '',
        },
    }
    app.logger.debug('file name: {}'.format(g.ret['data']['filename']))
    assert os.path.splitext(g.ret['data']['filename'])[1].lower() in ['.doc', '.docx'], 'invalid extension'
    # win32初始化
    pythoncom.CoInitialize()


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
    # 清理
    pythoncom.CoUninitialize()
    return response


@app.route('/upload', methods=['POST'])
def upload():
    word = win32com.client.gencache.EnsureDispatch('Word.Application')
    # 新建临时目录
    with tempfile.TemporaryDirectory() as dirname:
        app.logger.debug('temp directory: {}'.format(dirname))
        temp_file = os.path.join(dirname, secure_filename(request.files['document'].filename))
        request.files['document'].save(temp_file)
        document = word.Documents.Open(FileName=temp_file)

        # 读取文档页数
        g.ret['data']['page'] = document.ComputeStatistics(2) # wdStatisticPages=2
        app.logger.info('page: {}'.format(g.ret['data']['page']))

        # 读项目编号
        ## 印象中所有项目编号都能在前几行读到
        pattern = re.compile('SHTEC20[0-9]{2}(PRO|PST|DSYS|SOF|SRV|PER|FUN)[0-9]{4}([-_][0-9]+){0,1}')
        for i in range(5):
            re_result = re.search(pattern, document.Paragraphs(i+1).Range.Text)
            if re_result:
                code = re_result.group()
                app.logger.info('code: {}'.format(code))
                break
        else:
            raise ValueError('ignored document')
        g.ret['data']['code'] = code

        # 附件和复核意见单的逻辑已去除
        
        # 读取系统名称和委托单位
        name = ''
        company = ''
        if 'DSYS' in code:
            app.logger.debug('reading DSYS')
            # 系统名称在封面页的表格外面
            for i in range(30):
                paragraph = document.Paragraphs(i+1).Range.Text.strip()
                if '等级测评报告' in paragraph:
                    name = paragraph[:-6]
                    break
            # 从表格中读取委托单位
            company = document.Tables(1).Cell(1, 2).Range.Text
        elif 'PRO' in code or 'PST' in code or 'PER' in code:
            app.logger.debug('reading PRO/PST/PER')
            # 直接从第一个表格中读取
            name = document.Tables(1).Cell(1, 2).Range.Text
            company = document.Tables(1).Cell(2, 2).Range.Text
        elif 'SOF' in code or 'FUN' in code:
            app.logger.debug('reading SOF/FUN')
            # 遍历第一页的行读取
            for i in range(30):
                paragraph = document.Paragraphs(i+1).Range.Text.strip()
                if '名称' in paragraph:
                    name = re.sub('^.*名称(:|：)', '', paragraph)
                if '委托单位' in paragraph:
                    company = re.sub('^.*单位(:|：)', '', paragraph)
                if name and company:
                    break
        ## 其他报告，自求多福
        else:
            app.logger.debug('reading others')
            name = '<unknown>'
            # 先尝试读表格
            for i in range(document.Tables(1).Rows.Count):
                if '名称' in document.Tables(1).Cell(i+1, 1).Range.Text:
                    name = document.Tables(1).Cell(i+1, 2).Range.Text
                if '委托单位' in document.Tables(1).Cell(i+1, 1).Range.Text:
                    company = document.Tables(1).Cell(i+1, 2).Range.Text
            # 再尝试读行
            for i in range(30):
                paragraph = document.Paragraphs(i+1).Range.Text.strip()
                if '名称' in paragraph:
                    name = re.sub('^.*名称(:|：)', '', paragraph)
                if '委托单位' in paragraph:
                    company = re.sub('^.*单位(:|：)', '', paragraph)
                if name and company:
                    break

        # 尝试去除可能存在的换行符
        g.ret['data']['name'] = re.sub('(\r|\n|\x07| *)', '', name)
        g.ret['data']['company'] = re.sub('(\r|\n|\x07| *)', '', company)
        app.logger.info('name: {}'.format(g.ret['data']['name']))
        app.logger.info('company: {}'.format(g.ret['data']['company']))

        document.Close(SaveChanges=0)

    return g.ret
