# -*- coding: UTF-8 -*-
import os
import logging
import sys
import subprocess
from walkdir import filtered_walk, file_paths
from . import var

def init(bin_path:dict={}, password:str=''):
    ''' 初始化archive的可执行文件和密码

    Args:
        bin_path(dict): win32需包含'winrar'，linux需包含'rar'、'unrar'、'unar'
        password(str): 默认解压/压缩密码

    Raises:
        AssertionError: 如果参数无效
    '''
    logger = logging.getLogger(__name__)

    if sys.platform == 'win32':
        bin_path.setdefault('winrar', 'C:\\Program Files\\WinRAR\\WinRAR.exe')
        assert (os.path.exists(bin_path['winrar']) and 
            subprocess.run(
                [os.path.join(os.path.dirname(bin_path['winrar']), 'Rar.exe'), '-iver'], 
                check=True, 
                capture_output=True
            ).stdout and
            subprocess.run(
                [os.path.join(os.path.dirname(bin_path['winrar']), 'UnRAR.exe'), '-iver'], 
                check=True, 
                capture_output=True
            ).stdout
        ), 'invalid arg: bin_path.winrar'
        logger.info('Archive configration (win32 -> WinRAR) confirmed.')
    elif sys.platform == 'linux':
        assert subprocess.run(
            [bin_path.setdefault('rar', 'rar'), '-iver'], 
            check=True, 
            capture_output=True
        ).stdout, 'invalid arg: bin_path.rar'
        assert subprocess.run(
            [bin_path.setdefault('unrar', 'unrar'), '-iver'], 
            check=True, 
            capture_output=True
        ).stdout, 'invalid arg: bin_path.unrar'
        assert subprocess.run(
            [bin_path.setdefault('unar', 'unar'), '-v'], 
            check=True, 
            capture_output=True
        ).stdout, 'invalid arg: bin_path.unar'
        logger.info('Archive configration (Linux -> rar/unrar/unar) confirmed.')
    else:
        raise OSError('Unsupported platform')
    var.bin_path = bin_path

    assert type(password) == str, 'invalid arg: password'
    if password:
        var.password = password
        logger.info('Archive password set.')


def archive(work_path:str, name:str='') -> str:
    ''' 压缩{work_path}，若初始化了密码，则进行加密压缩。压缩包存放到工作目录下的{name}.rar。

    Args:
        work_path(str): 需压缩的工作目录
        name(str): 目标压缩包名（可选/默认为文件夹名）

    Returns:
        str: 压缩包的绝对路径

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'work_path': work_path, 'name': name}))
    assert os.path.isdir(work_path), 'invalid arg: work_path'
    assert type(name) == str, 'invalid arg: name'

    abspath_archive = os.path.join(work_path, name + '.rar') if name else os.path.join(work_path, os.path.basename(work_path) + '.rar')
    if sys.platform == 'win32':
        p = subprocess.run([
            var.bin_path['winrar'],
            'a',                    # archive
            '-ep',                  # 忽略目录结构
            '-hp' + var.password,   # 同时加密文件头
            '-r',                   # recursive
            '-xraw.eml',            # 忽略邮件元数据
            abspath_archive,
            os.path.join(work_path, '*')
        ], check=True, capture_output=True)
        logger.debug('winrar output:\n {}'.format(p.stdout.decode('utf-8')))
    if sys.platform == 'linux':
        p = subprocess.run([
            var.bin_path['rar'],
            'a',                    # archive
            '-ep',                  # 忽略目录结构
            '-hp' + var.password,   # 同时加密文件头
            '-r',                   # recursive
            '-xraw.eml',            # 忽略邮件元数据
            abspath_archive,
            os.path.join(work_path, '*')
        ], check=True, capture_output=True)
        logger.debug('rar output:\n {}'.format(p.stdout.decode('utf-8')))

    logger.debug('return: {}'.format(abspath_archive))
    return abspath_archive


def extract(work_path:str) -> list:
    ''' 则尝试使用密码解压缩{work_path}下的所有压缩包（不递归）
    
    解压时忽略压缩包的文件结构，自动删除解压成功的压缩包

    Args:
        work_path: 工作目录

    Returns:
        list: 解压失败压缩包的绝对路径

    Raises:
        TypeError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'work_path': work_path}))
    assert os.path.isdir(work_path), 'invalid arg: work_path'

    # rar错误日志
    log_file_path = os.path.join(work_path, 'rar.log')
    # 所有压缩文件路径
    archive_file_paths = file_paths(filtered_walk(work_path, included_files=['*.rar', '*.zip', '*.7z', '*.tar']))
    # 解压所有文件
    for archive_file_path in archive_file_paths:
        if sys.platform == 'win32':
            p = subprocess.run([
                var.bin_path['winrar'],
                'e',                        # 解压到当前文件夹(忽略目录结构)
                '-p' + var.password,        # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                '-o+',                      # overwrite all
                '-ilog' + log_file_path,    # 将错误信息写入日志文件(utf-16le)
                '-inul',                    # 不显示默认的错误信息框
                archive_file_path,
                work_path
            ], check=True, capture_output=True)
            logger.debug('winrar output:\n {}'.format(p.stdout.decode('utf-8')))
        if sys.platform == 'linux':
            if os.path.splitext(archive_file_path)[1] == '.rar':
                p = subprocess.run([
                    var.bin_path['unrar'],
                    'e',                        # 解压到当前文件夹(忽略目录结构)
                    '-p' + var.password,        # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                    '-o+',                      # overwrite all
                    '-ilog' + log_file_path,    # 将错误信息写入日志文件(utf-16le)
                    '-inul',                    # 不显示默认的错误信息框
                    archive_file_path,
                    work_path
                ], check=True, capture_output=True)
                logger.debug('unrar output:\n {}'.format(p.stdout.decode('utf-8')))
            else:
                p = subprocess.run([
                    var.bin_path['unar'],   
                    '-D',                       # 忽略目录结构
                    '-e', 'gbk',                # （文件头不包含unicode信息时）使用gbk编码
                    '-p', var.password,         # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                    '-f',                       # overwrite all
                    '-o', work_path,            # 输出目录
                    archive_file_path
                ], check=True, capture_output=True)
                logger.debug('unar output:\n {}'.format(p.stdout.decode('utf-8')))
    # 所有文件解压完后，检查错误日志
    # 解压失败的压缩文件路径
    archive_file_paths_with_error = []
    if os.path.exists(log_file_path):
        for line in open(log_file_path, 'r', encoding='utf-16le').readlines():
            # rar的log只记录错误日志，每个文件用分隔符隔离
            if '--------' in line:
                #暂存错误文件的列表
                archive_file_paths_with_error.append(os.path.abspath(line.split('Archive', 1)[1].strip()))
        # 处理完后无需保留日志
        os.remove(log_file_path)
        logger.warning('extraction failed: {}'.format(archive_file_paths_with_error))

    # 删除解压正常的压缩包
    for archive_file_path in archive_file_paths:
        if archive_file_path not in archive_file_paths_with_error:
            os.remove(archive_file_path)
            logger.debug('removed "{}"'.format(archive_file_path))

    logger.debug('return: {}'.format(archive_file_paths_with_error))
    return archive_file_paths_with_error
