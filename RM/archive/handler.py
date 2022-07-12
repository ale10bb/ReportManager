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

    archive_name = name + '.rar' if name else os.path.basename(work_path) + '.rar'
    abspath_archive = os.path.join(work_path, archive_name)
    # 在1核2G的云服务器时，rar有概率报错退出 (exit 2: 发生致命错误)
    # 猜测原因为OOM，多次尝试应该会减少错误概率
    for idx in range(3):
        logger.debug('attempt {}'.format(idx + 1))
        if sys.platform == 'win32':
            p = subprocess.run([
                var.bin_path['winrar'],
                'a',                    # archive
                '-ep',                  # 忽略目录结构
                '-hp' + var.password,   # 同时加密文件头
                '-r',                   # recursive
                '-xraw.eml',            # 忽略邮件元数据
                '-x' + archive_name,    # 忽略处理报错但可能产生的临时文件
                abspath_archive,
                os.path.join(work_path, '*')
            ], capture_output=True)
            logger.debug('winrar output ({}):\n {}'.format(p.returncode, p.stdout.decode('utf-8')))
        elif sys.platform == 'linux':
            p = subprocess.run([
                var.bin_path['rar'],
                'a',                    # archive
                '-ep',                  # 忽略目录结构
                '-hp' + var.password,   # 同时加密文件头
                '-r',                   # recursive
                '-xraw.eml',            # 忽略邮件元数据
                '-x' + archive_name,    # 忽略处理报错但可能产生的临时文件
                abspath_archive,
                os.path.join(work_path, '*')
            ], capture_output=True)
            logger.debug('rar output ({}):\n {}'.format(p.returncode, p.stdout.decode('utf-8')))
        else:
            raise OSError('Unsupported platform')
        if not p.returncode:
            break
    else:
        p.check_returncode()
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
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'work_path': work_path}))
    assert os.path.isdir(work_path), 'invalid arg: work_path'

    # 解压失败的压缩文件路径
    archives_with_error = []
    # 解压所有文件
    for item in file_paths(filtered_walk(work_path, included_files=['*.rar', '*.zip', '*.7z', '*.tar'])):
        logger.debug('extracting "{}"'.format(item))
        if sys.platform == 'win32':
            p = subprocess.run([
                var.bin_path['winrar'],
                'e',                        # 解压到当前文件夹(忽略目录结构)
                '-p' + var.password,        # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                '-o+',                      # overwrite all
                '-inul',                    # 不显示默认的错误信息框
                item,
                work_path
            ], capture_output=True)
            logger.debug('winrar output ({}):\n {}'.format(p.returncode, p.stdout.decode('utf-8')))
        elif sys.platform == 'linux':
            p = subprocess.run([
                var.bin_path['unar'],   
                '-D',                       # 忽略目录结构
                '-e', 'gbk',                # （文件头不包含unicode信息时）使用gbk编码
                '-p', var.password,         # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                '-f',                       # overwrite all
                '-o', work_path,            # 输出目录
                item
            ], capture_output=True)
            logger.debug('unar output ({}):\n {}'.format(p.returncode, p.stdout.decode('utf-8')))
        else:
            raise OSError('Unsupported platform')
        # 删除解压正常的压缩包
        if p.returncode:
            archives_with_error.append(item)
        else:
            os.remove(item)
            logger.debug('removed "{}"'.format(item))   

    logger.debug('return: {}'.format(archives_with_error))
    return archives_with_error
