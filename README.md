# 审核管理机器人 ReportManager

[![OSCS Status](https://www.oscs1024.com/platform/badge/ale10bb/ReportManager.svg?size=small)](https://www.oscs1024.com/project/ale10bb/ReportManager?ref=badge_small)
[![platform](https://img.shields.io/badge/python-3.9-green.svg)]()
[![license](https://img.shields.io/github/license/ale10bb/ReportManager)]()


## 介绍

监听一个邮箱，自动处理发送至该邮箱的提交审核请求及完成审核请求，并实现按工作量自动分配审核任务。

## 核心功能

- 实现“提交审核邮件”及“完成审核邮件”的自动处理
- 记录人员审核页数，将任务分配至工作量最少的人员
- 支持读取和发送加密压缩包
- 支持读取文档信息，并存入历史记录
- 支持接入钉钉群聊机器人，发送任务提醒通知和告警通知
- 支持接入企业微信应用，发送任务提醒通知和告警通知
- 支持任务查询和信息修改

## 运行环境

运行机器人前，请检查并准备以下环境或组件

- python及venv

Linux操作系统可参考以下部署方式

```console
user@host:~$ python --version
Python 3.9.13
user@host:~$ git clone https://github.com/ale10bb/ReportManager.git
user@host:~$ cd ReportManager
user@host:~/ReportManager$ python -m venv .venv
user@host:~/ReportManager$ source .venv/bin/activate
(.venv) user@host:~/ReportManager$ pip install -r requirements.txt 
...
(.venv) user@host:~/ReportManager$ pip install gunicorn[gevent]
...
(.venv) user@host:~/ReportManager$ deactivate
user@host:~/ReportManager$ 
```

Windows操作系统可参考以下部署方式

```powershell
PS C:\Users\user> python --version
Python 3.9.13
PS C:\Users\user> git clone https://github.com/ale10bb/ReportManager.git
PS C:\Users\user> cd ReportManager
PS C:\Users\user\ReportManager> python -m venv .venv
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> pip install -r requirements.txt
...
(.venv) PS C:\Users\user\ReportManager> pip install waitress
...
(.venv) PS C:\Users\user\ReportManager> deactivate
PS C:\Users\user\ReportManager> 
```

- MySQL数据库及表结构

``` sql
-- 建立数据库及对应用户
CREATE DATABASE rm CHARACTER SET utf8mb4;
CREATE USER 'rm'@'%' IDENTIFIED BY '!!';
GRANT ALL PRIVILEGES ON rm.* to 'rm'@'%';
```
```bash
# 导入表结构
mysql -urm -p rm < res/init.sql
# docker exec -i mysql sh -c 'exec mysql -urm -p rm' < res/init.sql
```

- SMTP服务和POP3服务

确保使用的收件邮箱启用了POP3服务，确认POP3是否启用SSL连接，端口一般为110（POP3）或995（POP3withSSL）。

确保使用的发件邮箱启用了SMTP服务，确认SMTP是否启用SSL连接，端口一般为25（SMTP）或465（SMTPwithSSL）。同时需确认SMTP服务最大可发送附件的容量。

- 压缩管理软件

部署在Windows操作系统上时，需用合理的方式安装[WinRAR](https://www.rarlab.com/)。

部署在Linux操作系统上时，需安装unar，并用合理的方式安装rar/unrar。可参考如下命令
``` console
root@host:~# apt-get update
root@host:~# apt-get install -y curl unar
root@host:~# curl -o rarlinux-x64-612.tar.gz https://www.rarlab.com/rar/rarlinux-x64-612.tar.gz
root@host:~# tar -xf rarlinux-x64-612.tar.gz -C /opt
root@host:~# rm rarlinux-x64-612.tar.gz
root@host:~# ln -s /opt/rar/unrar /usr/bin/unrar
root@host:~# ln -s /opt/rar/rar /usr/bin/rar
root@host:~# 
```

- Microsoft Office (Word)

部署在Windows操作系统时，需额外安装Word及pywin32，用于调用Word程序来获取文档页数。

注意：doc或者docx文件类似于xml，自身并不包含“页数”属性，页数由渲染器（Word程序）实时计算，因此python-docx库无法获取文档页数，需由pywin32实现。

```powershell
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> pip install -r pywin32
(.venv) PS C:\Users\user\ReportManager> python .venv\Scripts\pywin32_postinstall.py -install
(.venv) PS C:\Users\user\ReportManager> deactivate
PS C:\Users\user\ReportManager> 
```

- （可选）钉钉群聊机器人

可在特定通知群中添加自定义机器人，操作方法可参照[钉钉开发文档](https://open.dingtalk.com/document/robots/custom-robot-access)。添加后保存机器人的webhook地址和secret。

- （可选）企业微信应用

可在企业微信中添加自定义应用，操作方法可参照[企业微信开发文档](https://developer.work.weixin.qq.com/document/path/90487)。添加后保存企业的corpid、应用的agentid和secret。

## 部署步骤

- 参照[样例配置文件](conf/RM.conf.sample)填写相关配置，配置文件应存放在``conf/RM.conf``

- 部署Web服务

RM预置了一个最小的Flask应用，用于提供一些常见的功能接口。 
在Windows操作系统部署时，minimal_web的运行建议参数如下

```powershell
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> waitress-serve --port=9070 --threads=1 minimal_web:app
```

在Linux操作系统部署时，minimal_web的运行建议参数如下

```console
user@host:~/ReportManager$ source .venv/bin/activate
(.venv) user@host:~/ReportManager$ gunicorn --worker-class gevent --capture-output --bind :9070 --timeout 120 minimal_web:app
```

- 部署Web服务（容器）

RM预置了Dockerfile，可参照如下命令构建镜像并启动容器

```console
user@host:~/ReportManager$ docker build -t rm .
user@host:~/ReportManager$ docker run -d --name rm.main -v conf/RM.conf:/ReportManager/conf/RM.conf -p 9070:9070 --restart unless-stopped rm
```

- 部署win32文档处理器（可选）


```powershell
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> waitress-serve --port=9072 win32:app
```

- 部署超大文件处理器（可选）

可以自行实现一个超大附件处理器供RM调用，生成一个下载URL附在邮件正文中，用于解决SMTP无法发送超大附件的情况。接口规范详见[设计文档](https://github.com/ale10bb/ReportManager/blob/master/doc/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3.md#%E8%B6%85%E5%A4%A7%E9%99%84%E4%BB%B6%E5%A4%84%E7%90%86%E5%99%A8)。
