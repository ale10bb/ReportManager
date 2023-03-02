# -*- coding: UTF-8 -*-
import os
import logging
import argparse
import re
from email.utils import parseaddr
from walkdir import filtered_walk, file_paths
import sys
if sys.platform == 'win32':
    import win32com.client
from . import archive, mail, mysql

# --------------------------------------------
#           检查邮件及附件的处理逻辑
# --------------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法

def check_mail_content(mail_content:dict) -> dict:
    ''' 读取{mail_content}中的内容，获取发件人和指令，处理完毕时返回警告信息及处理结果'content'。

    Args:
        mail_content(dict): check_result中解析后的邮件内容；

    Returns:
        {'warnings': [], 'content': {'user_id': (str), 'name': (str), 'urgent': (bool), 'excludes': (list), 'force': (str)}}

    Raises:
        ValueError: 如果发件人非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'mail_content': mail_content}))
    assert type(mail_content) == dict, 'invalid arg: mail_content'

    ret = {'warnings': [], 'content': {'user_id': '', 'name': '', 'urgent': False, 'excludes': [], 'force': ''}}
    # 从from中读取发信人并校验，校验内容为：
    #   域名必须为配置文件中的_MAIL_DOMAIN & 用户名必须位于user表中
    #   如果subject中包含"--sender userid"参数，则在检验userid有效后，将其作为发信人
    # 预期结果：
    #   流程正常完成时，在ret中填入user_id、name
    #   校验失败时，抛出ValueError，包含发件人邮箱
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s',
        '--sender',
        nargs='?',
        const='',
        default='',
        action='store'
    )
    parser.add_argument('others', nargs='*')
    args = parser.parse_args(re.sub(' +', ' ',mail_content['subject'].strip()).split(' '))
    if args.sender:
        user_id = args.sender
        logger.info('manual sender: {}'.format(args.sender))
    else:
        user_id = parseaddr(mail_content['from'])[1].split('@')[0]

    if mail.valid_domain(mail_content['from']) and mysql.t_user.__contains__(user_id):
        name = mysql.t_user.fetch(user_id)[1]
        ret['content']['user_id'] = user_id
        ret['content']['name'] = name
        logger.info('sender: {}/{}'.format(user_id, name))
    else:
        raise ValueError('Invalid sender "{}"'.format(mail_content['from']))

    # 从content中指令并校验，校验内容为：
    #   是否输入“加急” & 输入内容是否合法
    #   是否输入“组员” & 组员是否具备审核资格
    #   是否输入“指定” & 是否同时设置了“加急” & 指定是否具备审核资格 & 指定是否为发件人或组员
    # 预期结果：
    #   流程正常完成时，在ret中填入urgent、excludes、force。非法指令将被忽略并使用默认值（见下）
    urgent = False
    excludes = []
    force = ''
    content = ''.join(mail_content['content'])
    # logger输出时，\r\n将被渲染导致日志换行，因此替换成<p>增加可读性
    logger.debug('content: {}'.format(re.sub('[\r\n]+', '<p>', content)))
    # 循环读取content中的所有行，尝试校验指令
    # 注意：如果指令重复，将丢弃上一条结果，将结果重置为默认值并处理新行
    for line in content.splitlines():
        # 有人习惯打冒号、全角逗号、半角逗号，一并替换成合法值
        line = re.sub(' +|：', ' ', line.strip())
        line = re.sub('，|,', '、', line.strip())
        # 替换常见错误输入后，按第一个空格分隔1次，长度不为2的指令行将被忽略
        cmds = line.split(' ', 1)
        if len(cmds) != 2:
            continue
        logger.debug('cmds: {}'.format(cmds))
        if cmds[0] == '加急':
            urgent = False
            if cmds[1] == '是' or cmds[1] == '1':
                urgent = True
                logger.info('urgent: {}'.format(urgent))
            elif cmds[1] == '否' or cmds[1] == '0':
                urgent = False
            else:
                ret['warnings'].append('无效的"加急"值，已忽略')
            continue
        if cmds[0] == '组员':
            excludes = []
            members = cmds[1].split('、')
            # 检查组员并修改为user_id
            for member in cmds[1].split('、'):
                excludes.extend(
                    mysql.t_user.search(user_id=member, only_reviewer=True)['user'] +
                    mysql.t_user.search(name=member, only_reviewer=True)['user']
                )
            excludes = [i[0] for i in excludes]
            if len(members) != len(excludes):
                ret['warnings'].append('已去除无效组员 {} -> {}'.format(members, excludes))
            logger.info('excludes: {}'.format(excludes))
        if cmds[0] == '指定':
            # 检查指定并修改为主键
            users = mysql.t_user.search(user_id=cmds[1], only_reviewer=True)['user'] + mysql.t_user.search(name=cmds[1], only_reviewer=True)['user']
            if len(users) == 1:
                force = users[0][0]
            else:
                ret['warnings'].append('已去除无效指定 "{}"'.format(cmds[1]))
            logger.info('force: {}'.format(force))

    # 考虑到指令重复、指令之间有因果关系等情况，仅当读取完所有行之后，再进行总体校验及写入ret
    # “指定”回滚逻辑：
    #   指定了自己或组员
    if force == user_id or force in excludes:
        force = ''
        ret['warnings'].append('指定失败: 项目相关人员')
        logger.warning('rallbacked force due to "in excludes"')

    # 写入ret
    ret['content']['urgent'] = urgent
    ret['content']['excludes'] = excludes
    ret['content']['force'] = force
    logger.debug('return: {}'.format(ret))
    return ret


def check_mail_attachment(work_path:str, operator:str) -> dict:
    ''' 读取存放在{work_path}中的附件，根据操作符获取文档信息。处理完毕后，返回attachment信息。

    Args:
        work_path(str)：工作目录（存放附件的目录）
        operator(str): 操作符（submit/finish）

    Returns:
        {'warnings': [], 'attachment': {'pages': (int), 'company': (str), 'codes': (list), 'names': (dict)}}

    Raises:
        AssertionError: 如果参数类型非法
        ValueError: 如果未读取到有效文档
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'work_path': work_path, 'operator': operator}))
    assert operator == 'submit' or operator == 'finish', 'invalid arg: operator'
    assert os.path.isdir(work_path), 'invalid arg: work_path'

    ret = {'warnings': [], 'attachment': {}}
    # 解压工作目录中的所有压缩包，并添加解压失败的告警
    for archive_file_path_with_error in archive.extract(work_path):
        ret['warnings'].append('解压失败："{}"'.format(os.path.basename(archive_file_path_with_error)))

    # 读取工作目录中的所有文档
    # 传入的操作符用于控制读取逻辑
    # 用返回值的codes参数作为标记，无codes说明读取失败，此时抛出ValueError异常
    if operator == 'submit':
        ret['attachment'] = read_document(work_path)
        if not ret['attachment']['codes']:
            raise ValueError('No valid documents within "submit"')
    if operator == 'finish':
        ret['attachment'] = read_XT13(work_path)
        if not ret['attachment']['codes']:
            raise ValueError('No valid documents within "finish"')

    logger.debug('return: {}'.format(ret))
    return ret

# -------------------------------------------
#           检查文档内容的处理逻辑
# -------------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法
#     函数传入work_path，对工作目录下的所有文件进行处理

def read_document(work_path:str) -> dict:
    ''' 读取{work_path}下的所有word文档，读取项目编号、项目名称、委托单位、文档页数，并尝试将文档转换到最新格式。

    Args:
        work_path: 工作目录

    Returns:
        dict: {'pages': 0, 'company': '', 'codes': [], 'names': {}}
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'work_path': work_path}))
    assert os.path.isdir(work_path), 'invalid arg: work_path'

    # 一个work_path作为一个项目包，读取时会将所有有效文档的页数相加，并返回项目名称的集合
    # 但默认项目包里面只有一个委托单位
    ret = {'pages': 0, 'company': '', 'codes': [], 'names': {}}
    # work_path中的所有doc和docx文件视作有效文档，但忽略审核意见单和临时文件
    document_paths = file_paths(filtered_walk(work_path, included_files=['*.doc', '*.docx'], excluded_files=['~$*', '*XT13*', '*签发意见单*']))
    word = win32com.client.gencache.EnsureDispatch('Word.Application')
    for document_path in document_paths:
        logger.info('reading "{}"'.format(os.path.basename(document_path)))
        page = 0
        code = ''
        name = ''
        company = ''
        try:
            document = None
            document = word.Documents.Open(FileName=document_path)

            # 读取文档页数
            page = document.ComputeStatistics(2) # wdStatisticPages=2
            logger.info('page: {}'.format(page))

            # 读项目编号
            ## 印象中所有项目编号都能在前几行读到
            pattern = re.compile('SHTEC20[0-9]{2}(PRO|PST|DSYS|SOF|SRV|PER|FUN)[0-9]{4}([-_][0-9]+){0,1}')
            for i in range(5):
                re_result = re.search(pattern, document.Paragraphs(i+1).Range.Text)
                if re_result:
                    code = re_result.group()
                    logger.info('code: {}'.format(code))
                    break
            else:
                logger.warning('ignored document')
                continue

            # 附件和复核意见单的逻辑已去除
            
            # 读取系统名称和委托单位
            if 'DSYS' in code:
                logger.debug('reading DSYS')
                # 系统名称在封面页的表格外面
                for i in range(30):
                    paragraph = document.Paragraphs(i+1).Range.Text.strip()
                    if '等级测评报告' in paragraph:
                        name = paragraph[:-6]
                        break
                # 从表格中读取委托单位
                company = document.Tables(1).Cell(1, 2).Range.Text
            elif 'PRO' in code or 'PST' in code or 'PER' in code:
                logger.debug('reading PRO/PST/PER')
                # 直接从第一个表格中读取
                name = document.Tables(1).Cell(1, 2).Range.Text
                company = document.Tables(1).Cell(2, 2).Range.Text
            elif 'SOF' in code or 'FUN' in code:
                logger.debug('reading SOF/FUN')
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
                logger.debug('reading others')
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
            if name:
                name = re.sub('(\r|\n|\x07| *)', '', name)
                logger.info('name: {}'.format(name))
                ret['codes'].append(code)
                ret['names'][code] = name
            # 委托单位有效时覆盖缓存值
            if company:
                company = re.sub('(\r|\n|\x07| *)', '', company)
                logger.info('company: {}'.format(company))
                ret['company'] = company
            # 累加项目包总页数
            ret['pages'] = ret['pages'] + page 
        except Exception as err:
            logger.warning('read failed', exc_info=True)
        finally:
            if document:
                document.Close(SaveChanges=0)

    logger.debug('return: {}'.format(ret))
    return ret


def read_XT13(work_path:str) -> dict:
    ''' 读取{work_path}下的所有审核意见单，读取项目编号。

    Args:
        work_path: 工作目录

    Returns:
        dict: {'pages': 0, 'company': '', 'codes': (list), 'names': {}}
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'work_path': work_path}))
    assert os.path.isdir(work_path), 'invalid arg: work_path'

    ret = {'pages': 0, 'company': '', 'codes': [], 'names': {}}
    # 只读docx格式的审核意见单
    document_paths = file_paths(filtered_walk(work_path, included_files=['*XT13*.docx', '*签发意见单*.docx'], excluded_files=['~$*']))
    for document_path in document_paths:
        logger.info('reading "{}"'.format(os.path.basename(document_path)))
        # 仅从文件名读编号
        re_result = re.search('SHTEC20[0-9]{2}(PRO|PST|DSYS|SOF|SRV|PER|FUN)[0-9]{4}([-_][0-9]+){0,1}', os.path.basename(document_path))
        if re_result:
            ret['codes'].append(re_result.group())
            logger.info('code: {}'.format(re_result.group()))
                
    logger.debug('return: {}'.format(ret))
    return ret
