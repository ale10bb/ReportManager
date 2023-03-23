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

    def __init__(self, bin_path: dict[str, str] | None = None, password: str = ''):
        ''' 初始化archive的可执行文件和密码

        Args:
            bin_path: win32需包含'winrar'，linux需包含'rar'、'unrar'、'unar'
            password: 默认解压/压缩密码

        Raises:
            FileNotFoundError/TypeError: 如果参数无效
        '''
        logger = logging.getLogger(__name__)

        if not bin_path:
            bin_path = {}
        if sys.platform == 'win32':
            bin_path.setdefault(
                'winrar', 'C:\\Program Files\\WinRAR\\WinRAR.exe')
            if not os.path.exists(bin_path['winrar']):
                raise FileNotFoundError('invalid arg: bin_path.winrar')
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

    def archive(self, src: str, archive_path: str) -> bool:
        ''' 忽略目录结构压缩/加密压缩{src}目录，保存至{archive_path}

        Args:
            src: 源目录
            archive_path: 压缩包路径

        Returns:
            bool: 压缩是否成功

        Raises:
            FileNotFoundError: 如果路径不存在
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'src': src, 'archive_path': archive_path
        })
        if not os.path.isdir(src):
            raise FileNotFoundError('invalid arg: src')
        if os.path.exists(archive_path):
            os.remove(archive_path)

        # 在1核2G的云服务器时，rar有概率报错退出 (exit 2: 发生致命错误)
        # 猜测原因为OOM，多次尝试应该会减少错误概率
        for idx in range(3):
            logger.debug('attempt %s', idx + 1)
            if sys.platform == 'win32':
                bin_path = self._bin_path['winrar']
            elif sys.platform == 'linux':
                bin_path = self._bin_path['rar']
            else:
                raise OSError('Unsupported platform')
            p = subprocess.run([
                bin_path,
                'a',        # 添加文件到压缩文档
                '-ep',      # 从名称里排除路径
                '-r',       # 递归子目录
                '-o+',      # 设置覆盖模式
                '-inul',    # 禁用所有消息
                f"-hp{self._password}" \
                if self._password else '--',  # 加密文件数据及文件头
                # -- 停止参数扫描
                archive_path,
                os.path.join(src, '*')
            ], capture_output=True)
            if not p.returncode:
                logger.debug('archive output (%s):\n %s',
                             p.returncode, p.stdout.decode('utf-8'))
                break
            else:
                logger.warning('archive output (%s):\n %s',
                               p.returncode, p.stdout.decode('utf-8'))
        else:
            logger.debug('return: False')
            return False
        logger.debug('return: True')
        return True

    def extract(self, dst: str, archive_path: str) -> bool:
        ''' 解压缩/带密解压缩{archive_path}，忽略目录结构并输出至{dst}

        Args:
            dst: 输出目录
            archive_path: 压缩包路径

        Returns:
            bool: 解压是否成功

        Raises:
            FileNotFoundError: 如果路径不存在
        '''
        logger = logging.getLogger(__name__)
        logger.debug('args: %s', {
            'dst': dst, 'archive_path': archive_path
        })
        if not os.path.isdir(dst):
            raise FileNotFoundError('invalid arg: dst')
        if not os.path.isfile(archive_path):
            raise FileNotFoundError('invalid arg: archive_path')

        if sys.platform == 'win32':
            p = subprocess.run([
                self._bin_path['winrar'],
                'e',    # 提取文件不带压缩路径
                '-o+',
                '-inul',
                f"-p{self._password}" if self._password else '--',
                archive_path,
                dst
            ], capture_output=True)
        elif sys.platform == 'linux':
            match os.path.splitext(archive_path)[1]:
                case '.rar':
                    p = subprocess.run([
                        self._bin_path['unrar'],
                        'e',
                        '-o+',
                        f"-p{self._password}" if self._password else '--',
                        archive_path,
                        dst
                    ], capture_output=True)
                case _:
                    p = subprocess.run([
                        self._bin_path['unar'],
                        '-D',                   # 忽略目录结构
                        '-e', 'gbk',            # （文件头不包含unicode信息时）使用gbk编码
                        '-p', self._password,   # '-p'只是传入一个密码，如果压缩包没有加密，则依然解压成功
                        '-f',                   # overwrite all
                        '-o', dst,              # 输出目录
                        archive_path
                    ], capture_output=True)
        else:
            raise OSError('Unsupported platform')
        if not p.returncode:
            logger.debug('extract output (%s):\n %s',
                         p.returncode, p.stdout.decode('utf-8'))
        else:
            logger.warning('extract output (%s):\n %s',
                           p.returncode, p.stdout.decode('utf-8'))
        logger.debug('return: %s', not bool(p.returncode))
        return not bool(p.returncode)
