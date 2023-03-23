# -*- coding: UTF-8 -*-
import os
import logging
import sys
import subprocess


class Archive:
    ''' 压缩包工具的封装客户端，实现压缩和解压缩的功能。
    '''
    _bin_path = {}
    _password = ''

    def __init__(self, bin_path: dict | None = None, password: str = ''):
        ''' 初始化archive的可执行文件和密码

        Args:
            bin_path: win32需包含'winrar'，linux需包含'rar'、'unrar'、'unar'
            password: 默认解压/压缩密码

        Raises:
            ValueError/TypeError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)

        if not bin_path:
            bin_path = {}
        if sys.platform == 'win32':
            bin_path.setdefault(
                'winrar', 'C:\\Program Files\\WinRAR\\WinRAR.exe')
            if not os.path.exists(bin_path['winrar']):
                raise ValueError('invalid arg: bin_path.winrar')
            p = subprocess.run(
                [os.path.join(os.path.dirname(
                    bin_path['winrar']), 'Rar.exe'), '-iver'],
                check=True,
                capture_output=True,
            )
            logger.debug('Rar.exe stdout: %s', p.stdout.decode('utf-8'))
            p = subprocess.run(
                [os.path.join(os.path.dirname(bin_path['winrar']),
                              'UnRAR.exe'), '-iver'],
                check=True,
                capture_output=True,
            )
            logger.debug('UnRAR.exe stdout: %s', p.stdout.decode('utf-8'))
            logger.info('Archive configration (win32 -> WinRAR) confirmed.')
        elif sys.platform == 'linux':
            p = subprocess.run(
                [bin_path.setdefault('rar', 'rar'), '-iver'],
                check=True,
                capture_output=True,
            )
            logger.debug('rar stdout: %s', p.stdout.decode('utf-8'))
            p = subprocess.run(
                [bin_path.setdefault('unrar', 'unrar'), '-iver'],
                check=True,
                capture_output=True
            )
            logger.debug('unrar stdout: %s', p.stdout.decode('utf-8'))
            p = subprocess.run(
                [bin_path.setdefault('unar', 'unar'), '-v'],
                check=True,
                capture_output=True
            )
            logger.debug('unar stdout: %s', p.stdout.decode('utf-8'))
            logger.info(
                'Archive configration (Linux -> rar/unrar/unar) confirmed.')
        else:
            raise OSError('Unsupported platform')
        self._bin_path = bin_path

        if not isinstance(password, str):
            raise TypeError('invalid arg: password')
        if password:
            self._password = password
            logger.info('Archive password set.')

    def archive(self, source: str, archive_path: str) -> bool:
        ''' 忽略目录结构压缩/加密压缩{source}，保存至{archive_path}

        Args:
            source: 源目录
            archive_path: 压缩包路径

        Returns:
            bool: 压缩是否成功

        Raises:
            ValueError: 如果参数非法
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'source': source, 'archive_path': archive_path
        })
        if not os.path.isdir(source):
            raise ValueError('invalid arg: source')
        if os.path.exists(archive_path):
            os.remove(archive_path)

        archive_name = os.path.basename(archive_path)
        # 在1核2G的云服务器时，rar有概率报错退出 (exit 2: 发生致命错误)
        # 猜测原因为OOM，多次尝试应该会减少错误概率
        for idx in range(3):
            logger.debug('attempt %s', idx + 1)
            if sys.platform == 'win32':
                p = subprocess.run([
                    self._bin_path['winrar'],
                    'a',                    # archive
                    '-ep',                  # 忽略目录结构
                    '-hp' + self._password,   # 同时加密文件头
                    '-r',                   # recursive
                    '-xraw.eml',            # 忽略邮件元数据
                    '-x' + archive_name,    # 忽略处理报错但可能产生的临时文件
                    '-o+',                  # overwrite all
                    archive_path,
                    os.path.join(source, '*')
                ], capture_output=True)
                logger.debug('winrar output (%s):\n %s',
                             p.returncode, p.stdout.decode('utf-8'))
            elif sys.platform == 'linux':
                p = subprocess.run([
                    self._bin_path['rar'],
                    'a',                    # archive
                    '-ep',                  # 忽略目录结构
                    '-hp' + self._password,   # 同时加密文件头
                    '-r',                   # recursive
                    '-xraw.eml',            # 忽略邮件元数据
                    '-x' + archive_name,    # 忽略处理报错但可能产生的临时文件
                    '-o+',                  # overwrite all
                    archive_path,
                    os.path.join(source, '*')
                ], capture_output=True)
                logger.debug('rar output (%s):\n %s',
                             p.returncode, p.stdout.decode('utf-8'))
            else:
                raise OSError('Unsupported platform')
            if not p.returncode:
                break
            else:
                logger.warning('non-zero returncode (%s):\n %s',
                               p.returncode, p.stdout.decode('utf-8'))
        else:
            logger.debug('return: False')
            return False
        logger.debug('return: True')
        return True

    def extract(self, target: str, archive_path: str) -> bool:
        ''' 解压缩/带密解压缩{archive_path}，忽略目录结构并输出至{target}

        Args:
            target: 输出目录
            archive_path: 压缩包路径

        Returns:
            bool: 解压是否成功

        Raises:
            ValueError: 如果参数非法
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'target': target, 'archive_path': archive_path
        })
        if not os.path.isdir(target):
            raise ValueError('invalid arg: target')
        if not os.path.isfile(archive_path):
            raise ValueError('invalid arg: archive_path')

        if sys.platform == 'win32':
            p = subprocess.run([
                self._bin_path['winrar'],
                'e',                        # 解压到当前文件夹(忽略目录结构)
                '-p' + self._password,        # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                '-o+',                      # overwrite all
                '-inul',                    # 不显示默认的错误信息框
                archive_path,
                target
            ], capture_output=True)
            logger.debug('winrar output (%s):\n %s',
                         p.returncode, p.stdout.decode('utf-8'))
        elif sys.platform == 'linux':
            match os.path.splitext(archive_path)[1]:
                case '.rar':
                    p = subprocess.run([
                        self._bin_path['unrar'],
                        'e',                        # 解压到当前文件夹(忽略目录结构)
                        '-p' + self._password,        # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                        '-o+',                      # overwrite all
                        '-inul',                    # 不显示默认的错误信息框
                        archive_path,
                        target
                    ], capture_output=True)
                    logger.debug('unrar output (%s):\n %s',
                                 p.returncode, p.stdout.decode('utf-8'))
                case _:
                    p = subprocess.run([
                        self._bin_path['unar'],
                        '-D',                       # 忽略目录结构
                        '-e', 'gbk',                # （文件头不包含unicode信息时）使用gbk编码
                        '-p', self._password,         # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                        '-f',                       # overwrite all
                        '-o', target,               # 输出目录
                        archive_path
                    ], capture_output=True)
                    logger.debug('unar output (%s):\n %s',
                                 p.returncode, p.stdout.decode('utf-8'))
        else:
            raise OSError('Unsupported platform')

        if not bool(p.returncode):
            logger.warning('non-zero returncode (%s):\n %s',
                           p.returncode, p.stdout.decode('utf-8'))
        logger.debug('return: %s', not bool(p.returncode))
        return not bool(p.returncode)
