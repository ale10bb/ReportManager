# 审核管理机器人 ReportManager

[![OSCS Status](https://www.oscs1024.com/platform/badge/ale10bb/ReportManager.svg?size=small)](https://www.oscs1024.com/project/ale10bb/ReportManager?ref=badge_small)
[![platform](https://img.shields.io/badge/python-3.11-green.svg)]()
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

## Worker 运行环境

Worker 是机器人的核心组件，部署在 Windows 操作系统中，实现分配逻辑及文件管理。Worker 启动后，与 Redis 保持长连接并监听消息队列。运行 Worker 前，请检查并准备以下环境或组件

- python 及 venv

```powershell
PS C:\Users\user> python --version
Python 3.11.5
PS C:\Users\user> git clone https://github.com/ale10bb/ReportManager.git
PS C:\Users\user> cd ReportManager
PS C:\Users\user\ReportManager> python -m venv .venv
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> pip install -r requirements_worker.txt
...
(.venv) PS C:\Users\user\ReportManager> deactivate
PS C:\Users\user\ReportManager>
```

- 安装 MySQL 数据库并导入表结构

```sql
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

- 安装 Redis 数据库（用于消息队列）
- SMTP 服务和 POP3 服务

确保使用的收件邮箱启用了 POP3 服务，确认 POP3 是否启用 SSL 连接，端口一般为 110（POP3）或 995（POP3withSSL）。

确保使用的发件邮箱启用了 SMTP 服务，确认 SMTP 是否启用 SSL 连接，端口一般为 25（SMTP）或 465（SMTPwithSSL）。同时需确认 SMTP 服务最大可发送附件的容量。

- 压缩管理软件

需用合理的方式安装[WinRAR](https://www.rarlab.com/)。

- Microsoft Office (Word)

部署在 Windows 操作系统时，需额外安装 Word 及 pywin32，用于调用 Word 程序来获取文档页数。

注意：doc 或者 docx 文件类似于 xml，自身并不包含“页数”属性，页数由渲染器（Word 程序）实时计算，因此 python-docx 库无法获取文档页数，需由 pywin32 实现。

```powershell
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> pip install pywin32
(.venv) PS C:\Users\user\ReportManager> python .venv\Scripts\pywin32_postinstall.py -install
(.venv) PS C:\Users\user\ReportManager> deactivate
PS C:\Users\user\ReportManager>
```

- （可选）钉钉群聊机器人

可在特定通知群中添加自定义机器人，操作方法可参照[钉钉开发文档](https://open.dingtalk.com/document/robots/custom-robot-access)。添加后保存机器人的 webhook 地址和 secret。

- （可选）企业微信应用

可在企业微信中添加自定义应用，操作方法可参照[企业微信开发文档](https://developer.work.weixin.qq.com/document/path/90487)。添加后保存企业的 corpid、应用的 agentid 和 secret。

## Worker 部署步骤

- 参照[样例配置文件](conf/RM.conf.sample)填写相关配置，配置文件应存放在`conf/RM.conf`

- 启动监听

```powershell
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> python worker.py
...
```

- （可选）使用 nssm 将 Worker 注册为系统服务

## Manage 部署步骤

RM 预置了一个管理应用，用于提供一些常见的功能接口（包括向消息队列发布任务的 WebCron）。

- 在 Windows 操作系统部署时，运行建议参数如下

```powershell
PS C:\Users\user\ReportManager> & .venv\Scripts\activate
(.venv) PS C:\Users\user\ReportManager> pip install waitress
...
(.venv) PS C:\Users\user\ReportManager> waitress-serve --port=9070 manage:app
```

- 在 Linux 操作系统部署时，运行建议参数如下

```console
user@host:~/ReportManager$ source .venv/bin/activate
(.venv) user@host:~/ReportManager$ pip install gunicorn[gevent]
...
(.venv) user@host:~/ReportManager$ gunicorn --worker-class gevent --capture-output --bind :9070 manage:app
```

- （可选）容器化部署管理服务

Manage 预置了 Dockerfile，可参照如下命令构建镜像并启动管理应用容器

```console
user@host:~/ReportManager$ docker build -t rm .
user@host:~/ReportManager$ docker run -d --name rm.main -v conf/RM.conf:/ReportManager/conf/RM.conf -p 9070:9070 --restart unless-stopped rm
```

- 设置定时任务

```
4 9 * * * curl http://127.0.0.1:9070/utils/cron?type=attend
*/5 9-16 * * * curl http://127.0.0.1:9070/utils/cron?type=mail
```
