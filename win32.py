# -*- coding: UTF-8 -*-
from flask import Flask, request
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename
import os.path
import tempfile
import base64
import win32com.client, pythoncom

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.logger.setLevel('DEBUG')


@app.route('/upload', methods=['POST'])
def upload():
    ret = {'result': 0, 'err': '', 'data': {'name': '', 'page': 0, 'converted': {'name': '', 'content': ''}}}
    try:
        file = request.files['document']
        assert os.path.splitext(file.filename)[1].lower() in ['.doc', '.docx'], 'invalid extension'
        # win32初始化
        pythoncom.CoInitialize()
        word = win32com.client.gencache.EnsureDispatch('Word.Application')
        # 新建临时目录
        with tempfile.TemporaryDirectory() as dirname:
            app.logger.debug('temp directory: {}'.format(dirname))
            ret['data']['name'] = secure_filename(file.filename)
            app.logger.debug('file name: {}'.format(ret['data']['name']))
            temp_file = os.path.join(dirname, ret['data']['name'])
            file.save(temp_file)
            document = word.Documents.Open(FileName=temp_file)
            app.logger.debug('compatibility mode: {}'.format(document.CompatibilityMode))
            # 将word转换为最新文件格式
            if document.CompatibilityMode < 15: # CompatibilityMode=11-14(旧版)
                document.Convert()
                document.Save()
                ret['data']['converted']['name'] = os.path.splitext(ret['data']['name'])[0] + '.docx'
                app.logger.info('converted to latest compatibility mode')
                with open(temp_file, 'rb') as f:
                    ret['data']['converted']['content'] = base64.b64encode(f.read()).decode('utf-8')
            # 读取文档页数
            ret['data']['page'] = document.ComputeStatistics(2) # wdStatisticPages=2
            app.logger.info('page: {}'.format(ret['data']['page']))
            document.Close(SaveChanges=0)
        # 清理
        pythoncom.CoUninitialize()
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
