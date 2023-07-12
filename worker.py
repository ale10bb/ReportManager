# -*- coding: UTF-8 -*-
import os
import sys
import logging
import logging.config
import shutil
import datetime
from walkdir import filtered_walk, file_paths, dir_paths

from RM import mysql, document, notification, validator
from RM.archive import Archive
from RM.dingtalk import Dingtalk
from RM.mail import Mail
from RM.redis import RedisStream
from RM.wxwork import WXWork
from RM.types import *


def init(config):
    # ---运行模式（debug）---
    global debug
    debug = config.getboolean("mode", "debug", fallback=False)

    # ---外部存储---
    global storage
    storage = config.get("path", "storage", fallback="storage")
    # 自动创建目录结构
    for check_dir in [
        os.path.join(storage, child_dir) for child_dir in ["temp", "archive"]
    ]:
        if os.path.isdir(check_dir):
            continue
        os.mkdir(check_dir)

    # ---logger---
    dict_config = {
        "version": 1,
        "formatters": {
            "main": {
                "format": "%(asctime)s - %(levelname)s - %(name)s/%(funcName)s:%(lineno)d -> %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                # 'style': '%',
                # 'validate': True,
            },
        },
        # 'filters': {},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "main",
                "level": "DEBUG",
                # 'filters': '',
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {
                "level": "DEBUG",
                "propagate": False,
                # 'filters': [],
                "handlers": ["console"],
            },
        },
    }
    if config.get("log", "dest", fallback=""):
        dict_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "main",
            "level": config.get("log", "level", fallback="INFO").upper(),
            # 'filters': '',
            "filename": os.path.join(
                storage, os.path.basename(config.get("log", "dest", fallback=""))
            ),
            "maxBytes": 204800,
            "backupCount": 5,
        }
        dict_config["loggers"][""]["handlers"].append("file")
    logging.config.dictConfig(dict_config)

    logger = logging.getLogger(__name__)
    logger.info(
        'logging to "%s" (%s)',
        dict_config["handlers"]["file"]["filename"],
        dict_config["handlers"]["file"]["level"],
    )

    # ---mysql---
    mysql.init(
        user=config.get("mysql", "user", fallback="rm"),
        password=config.get("mysql", "pass", fallback="rm"),
        host=config.get("mysql", "host", fallback="127.0.0.1"),
        database=config.get("mysql", "db", fallback="rm"),
        port=config.getint("mysql", "port", fallback=3306),
    )

    # ---redis---
    global stream
    stream = RedisStream(
        host=config.get("redis", "host", fallback="127.0.0.1"),
        password=config.get("redis", "pass", fallback="rm"),
    )

    # ---mail---
    global mail
    pop3_config = {
        "username": config.get("pop3", "user", fallback="rm@example.com"),
        "password": config.get("pop3", "pass", fallback="rm"),
        "host": config.get("pop3", "host", fallback="example.com"),
        "port": config.getint("pop3", "port", fallback=110),
        "ssl": config.getboolean("pop3", "ssl", fallback=False),
        "tls": config.getboolean("pop3", "tls", fallback=False),
    }
    smtp_config = {
        "username": config.get("smtp", "user", fallback="rm@example.com"),
        "password": config.get("smtp", "pass", fallback="rm"),
        "host": config.get("smtp", "host", fallback="example.com"),
        "port": config.getint("smtp", "port", fallback=25),
        "ssl": config.getboolean("smtp", "ssl", fallback=False),
        "tls": config.getboolean("smtp", "tls", fallback=False),
    }
    mail = Mail(
        pop3_config,
        smtp_config,
        config.get("mail", "domain", fallback="example.com"),
        config.get("mail", "manager", fallback=""),
    )

    # ---archive---
    global archive
    bin_path = {
        "winrar": config.get(
            "archive", "winrar_bin", fallback="C:\\Program Files\\WinRAR\\WinRAR.exe"
        ),
        "rar": config.get("archive", "rar_bin", fallback="rar"),
        "unrar": config.get("archive", "unrar_bin", fallback="unrar"),
        "unar": config.get("archive", "unar_bin", fallback="unar"),
    }
    archive = Archive(bin_path, config.get("archive", "pass", fallback=""))

    # ---dingtalk---
    global dingtalk
    chatbot = {
        "webhook": config.get("dingtalk", "webhook", fallback=""),
        "secret": config.get("dingtalk", "secret", fallback=""),
    }
    chatbot_debug = {
        "webhook": config.get("dingtalk", "webhook_debug", fallback=""),
        "secret": config.get("dingtalk", "secret_debug", fallback=""),
    }
    dingtalk = Dingtalk(
        chatbot,
        chatbot_debug,
        config.get("dingtalk", "attend", fallback=""),
        config.get("dingtalk", "interaction", fallback=""),
    )

    # ---wxwork---
    global wxwork
    wxwork = WXWork(
        config.get("wxwork", "corpid", fallback=""),
        config.getint("wxwork", "agentid", fallback=0),
        config.get("wxwork", "secret", fallback=""),
        config.get("wxwork", "admin_userid", fallback=""),
    )


def do_mail(parsed_mail: Parsed_Mail):
    """邮件处理入口，功能包括：

    1. 邮件检查
    2. 数据库操作
    3. 发送通知

    Args:
        parsed_mail: 预处理的邮件
    """
    logger = logging.getLogger(__name__)
    logger.debug("args: %s", {"parsed_mail": parsed_mail})

    logger.info('reading "%s" from "%s"', parsed_mail["operator"], parsed_mail["from_"])

    # Step 1: 检查邮件内容及附件内容
    # 常规错误为：
    #   发件人非法
    #   未从附件中读取到有效文档
    # 错误时直接终止处理
    check_result = {"warnings": [], "content": {}, "attachment": {}}
    try:
        ret = validator.check_mail_content(
            parsed_mail["from_"],
            parsed_mail["subject"],
            parsed_mail["content"],
            parsed_mail["timestamp"],
        )
        check_result["content"] = ret["content"]
        check_result["warnings"] += ret["warnings"]
        attachments_path = os.path.join(parsed_mail["temp_path"], "attachments")
        for archive_path in file_paths(
            filtered_walk(attachments_path, included_files=["*.rar", "*.zip", "*.7z"])
        ):
            if not archive.extract(attachments_path, archive_path):
                check_result["warnings"].append(
                    f'解压失败："{os.path.basename(archive_path)}"'
                )
            else:
                os.remove(archive_path)
        #   未从附件中读取到有效文档
        ret = validator.check_mail_attachment(attachments_path, parsed_mail["operator"])
        check_result["attachment"] = ret["attachment"]
        check_result["warnings"] += ret["warnings"]
    except Exception as err:
        user_id = (
            check_result["content"]["user_id"]
            if "user_id" in check_result["content"]
            else "unknown"
        )
        logger.error("do_mail(%s) failed.", user_id, exc_info=True)
        dingtalk.send_markdown(
            "[RM] 处理异常", f"({user_id}) {err}", to_debug=True, to_stdout=debug
        )
        wxwork.send_text(
            f"({user_id}) {err}",
            [],
            to_debug=True,
            to_stdout=debug,
        )
        raise
    else:
        # Step 2: 进行数据库操作、发送通知步骤
        if parsed_mail["operator"] == "submit":
            handle_submit(
                parsed_mail["temp_path"],
                check_result["content"],
                check_result["attachment"],
                check_result["warnings"],
            )
        elif parsed_mail["operator"] == "finish":
            handle_finish(
                parsed_mail["temp_path"],
                check_result["content"],
                check_result["attachment"],
                check_result["warnings"],
            )
        else:
            raise ValueError("Invalid operator.")
    finally:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        mysql.t_log.add_mail(
            check_result["warnings"],
            str(exc_value) if exc_type else "",
            parsed_mail,
            check_result["content"],
            check_result["attachment"],
        )


def handle_submit(
    work_path: str, content: Content, attachment: Attachment, warnings: list[str]
):
    """对提交审核邮件进行数据库操作、发送通知步骤

    Args:
        work_path: 临时目录
        content: 处理后的邮件内容信息
        attachment: 处理后的邮件附件信息
        warnings: 前步骤产生的告警信息

    Raises:
        RuntimeError: 如果插入记录失败
    """
    logger = logging.getLogger(__name__)
    logger.debug(
        "args: %s",
        {
            "work_path": work_path,
            "content": content,
            "attachment": attachment,
            "warnings": warnings,
        },
    )

    try:
        attachments_path = os.path.join(work_path, "attachments")
        # 在current表中插入项目
        if content["force"]:
            # 如果有指定审核人，直接设置为该人
            reviewer_id = content["force"]
        else:
            # 否则获取下一顺位的审核人，传入的excludes拼接了组员和自己
            reviewer_id = mysql.t_user.pop(
                excludes=content["excludes"] + [content["user_id"]],
                urgent=content["urgent"],
            )[0]["id"]
        mysql.t_current.add(
            attachment["names"],
            attachment["company"],
            attachment["pages"],
            content["urgent"],
            content["user_id"],
            reviewer_id,
            content["timestamp"],
        )
        # 从current表中取回操作结果record
        record = mysql.t_current.fetch_by_name(attachment["names"])
        if not record:
            raise RuntimeError("Cannot fetch record.")
        logger.debug("record: %s", record)
        logger.info('(submit) "%s" -> "%s"', record["authorid"], record["reviewerid"])
        codes = "+".join(sorted(record["names"]))
        # 生成XT13
        for code, project_name in record["names"].items():
            # 已有XT13时不再重复生成
            if os.path.exists(
                os.path.join(attachments_path, f"RD-XT13测评报告审核、签发意见单{code}.docx")
            ):
                continue
            document.gen_XT13(
                record["authorname"],
                code,
                project_name,
                os.path.join(attachments_path, f"RD-XT13测评报告审核、签发意见单{code}.docx"),
            )
        # 清理文件并重命名文件夹
        new_work_path = os.path.join(
            storage,
            "temp",
            "{}_{}_{}".format(
                datetime.datetime.now().timestamp(),
                record["authorid"],
                codes,
            ),
        )
        logger.info("new work_path: %s", new_work_path)
        os.mkdir(new_work_path)
        for file_path in file_paths(
            filtered_walk(
                attachments_path,
                included_files=["*.doc", "*.docx", "*.rar", "*.zip", "*.7z"],
                excluded_files=["~$*"],
            )
        ):
            shutil.copy(file_path, new_work_path)
            logger.info('copied "%s"', os.path.basename(file_path))
        shutil.rmtree(work_path)
        # 发送邮件及通知
        archive_path = os.path.join(new_work_path, f"{codes}.rar")
        if not archive.archive(new_work_path, archive_path):
            warnings.append(f'压缩失败："{os.path.basename(new_work_path)}"')
            attachments = list(file_paths(filtered_walk(new_work_path)))
        else:
            attachments = [archive_path]
        message = notification.build_submit_mail(record, warnings)
        mail.send(
            mysql.t_user.fetch(record["reviewerid"])["email"],
            message["subject"],
            message["content"],
            attachments,
            to_stdout=debug,
        )
        if os.path.exists(archive_path):
            os.remove(archive_path)
        message = notification.build_submit_dingtalk(record, warnings)
        dingtalk.send_markdown(
            message["subject"],
            message["content"],
            mysql.t_user.fetch(record["reviewerid"])["phone"],
            to_stdout=debug,
        )
        message = notification.build_submit_wxwork(record, warnings)
        wxwork.send_text(
            message["content"],
            [record["authorid"], record["reviewerid"]],
            to_stdout=debug,
        )
    except Exception as err:
        user_id = content["user_id"]
        logger.error("handle_submit(%s) failed.", user_id, exc_info=True)
        dingtalk.send_markdown(
            "[RM] 处理异常", f"({user_id}) {err}", to_debug=True, to_stdout=debug
        )
        wxwork.send_text(
            f"({user_id}) {err}",
            [],
            to_debug=True,
            to_stdout=debug,
        )
        raise


def handle_finish(
    work_path: str, content: Content, attachment: Attachment, warnings: list[str]
):
    """对完成审核邮件进行数据库操作、发送通知步骤

    Args:
        work_path: 临时目录
        content: 处理后的邮件内容信息
        attachment: 处理后的邮件附件信息
        warnings: 前步骤产生的告警信息

    Raises:
        RuntimeError: 如果删除记录失败
    """
    logger = logging.getLogger(__name__)
    logger.debug(
        "args: %s",
        {
            "work_path": work_path,
            "content": content,
            "attachment": attachment,
            "warnings": warnings,
        },
    )

    try:
        attachments_path = os.path.join(work_path, "attachments")
        #   在current表中删除项目
        mysql.t_current.finish_by_name(attachment["names"], content["timestamp"])
        # 从history中取回操作结果record
        # 由于插入history时不检测唯一性，search结果可能重复。在此取第一个结果作为有效返回
        record = mysql.t_history.search(
            page_size=1, code="+".join(attachment["names"])
        )["history"][0]
        logger.debug("record: %s", record)
        logger.info('(finish) "%s" <- "%s"', record["authorid"], record["reviewerid"])
        codes = "+".join(sorted(record["names"]))
        # 将文件移动至archive中，重名时清除上一条记录
        new_work_path = os.path.join(storage, "archive", codes)
        logger.info("new work_path: %s", new_work_path)
        if os.path.isdir(new_work_path):
            shutil.rmtree(new_work_path)
        os.mkdir(new_work_path)
        for file_path in file_paths(
            filtered_walk(
                attachments_path,
                included_files=["*.doc", "*.docx", "*.rar", "*.zip", "*.7z"],
                excluded_files=["~$*"],
            )
        ):
            shutil.copy(file_path, new_work_path)
            logger.info('copied "%s"', os.path.basename(file_path))
        # 清理并同时删除temp中的提交审核记录
        shutil.rmtree(work_path)
        for dir_path in dir_paths(
            filtered_walk(
                os.path.join(storage, "temp"),
                included_dirs=["*" + codes],
                depth=1,
                min_depth=1,
            )
        ):
            shutil.rmtree(dir_path)
        # 加密文件
        for document_path in file_paths(
            filtered_walk(new_work_path, included_files=["*.doc", "*.docx"])
        ):
            document.encrypt(document_path)
        # 发送邮件及通知
        archive_path = os.path.join(new_work_path, f"{codes}.rar")
        if not archive.archive(new_work_path, archive_path):
            warnings.append(f'压缩失败："{os.path.basename(new_work_path)}"')
            attachments = list(file_paths(filtered_walk(new_work_path)))
        else:
            attachments = [archive_path]
        message = notification.build_finish_mail(record, warnings)
        mail.send(
            mysql.t_user.fetch(record["authorid"])["email"],
            message["subject"],
            message["content"],
            attachments,
            to_stdout=debug,
            needs_cc=True,
        )
        if os.path.exists(archive_path):
            os.remove(archive_path)
        message = notification.build_finish_dingtalk(record, warnings)
        dingtalk.send_markdown(
            message["subject"],
            message["content"],
            mysql.t_user.fetch(record["authorid"])["phone"],
            to_stdout=debug,
        )
        message = notification.build_finish_wxwork(record, warnings)
        wxwork.send_text(
            message["content"],
            [record["authorid"], record["reviewerid"]],
            to_stdout=debug,
        )
    except Exception as err:
        user_id = content["user_id"]
        logger.error("handle_finish(%s) failed.", user_id, exc_info=True)
        dingtalk.send_markdown(
            "[RM] 处理异常", f"({user_id}) {err}", to_debug=True, to_stdout=debug
        )
        wxwork.send_text(
            f"({user_id}) {err}",
            [],
            to_debug=True,
            to_stdout=debug,
        )
        raise


def do_resend(id: str | int, redirect: str = ""):
    """邮件重发入口，重新向任务相关人员发送提交审核/完成审核邮件。

    Args:
        id: 项目记录ID
        redirect: 忽略原发件对象，将邮件发送至指定user_id
    """
    logger = logging.getLogger(__name__)
    logger.debug("args: %s", {"id": id, "redirect": redirect})
    if isinstance(id, int):
        record = mysql.t_history.fetch(id)
    elif isinstance(id, str):
        record = mysql.t_current.fetch(id)
    else:
        raise TypeError("invalid arg: id")
    if not record:
        raise ValueError("invalid arg: id")
    if not isinstance(redirect, str) or not mysql.t_user.__contains__(redirect):
        logger.warning("invalid arg: redirect")
        redirect = ""

    codes = "+".join(sorted(record["names"]))
    # 搜索最新的文件记录
    work_path = list(
        dir_paths(
            filtered_walk(
                os.path.join(
                    storage, "temp" if isinstance(record["id"], str) else "archive"
                ),
                included_dirs=[f"*{codes}"],
                depth=1,
                min_depth=1,
            )
        )
    )[-1]
    logger.info("found path: %s", work_path)

    # 对于current中获取的target，重发[分配审核]
    if isinstance(record["id"], str):
        resend_notification = notification.build_submit_mail(record, [])
        resend_notification["subject"] = "(resend) " + resend_notification["subject"]
        to = redirect if redirect else record["reviewerid"]
        logger.info('resending "%s" (分配审核) to "%s"', codes, to)
    # 对于history中获取的target，重发[完成审核]
    else:
        resend_notification = notification.build_finish_mail(record, [])
        resend_notification["subject"] = "(resend) " + resend_notification["subject"]
        to = redirect if redirect else record["authorid"]
        logger.info('resending "%s" (完成审核) to "%s"', codes, to)

    # 发送并清理临时文件
    archive_path = os.path.join(work_path, f"{codes}.rar")
    if not archive.archive(work_path, archive_path):
        attachments = list(file_paths(filtered_walk(work_path)))
    else:
        attachments = [archive_path]
    mail.send(
        mysql.t_user.fetch(to)["email"],
        resend_notification["subject"],
        resend_notification["content"],
        attachments,
        to_stdout=debug,
    )
    if os.path.exists(archive_path):
        os.remove(archive_path)


if __name__ == "__main__":
    from configparser import ConfigParser

    config = ConfigParser()
    config.read(os.path.join("conf", "RM.conf"), encoding="UTF-8")
    init(config)

    import socket

    logger = logging.getLogger("main")
    logger.warning('Worker "%s" initiated.', socket.gethostname())

    while True:
        # 默认阻塞当前进程，直到队列中出现可用的对象
        logger.debug("waiting stream")
        entries = stream.read()
        for stream_entries in entries:
            if stream_entries[0] == "receive":
                for message_id, message_fields in stream_entries[1]:
                    logger.debug(
                        'new item in "%s": (%s) %s',
                        stream_entries[0],
                        message_id,
                        message_fields,
                    )
                    text = f"- [任务结果] -\n\n信息: [邮件处理]完成\nID: {message_id}"
                    try:
                        keywords = {}
                        keywords["submit"] = message_fields.get("submit", "[提交审核]")
                        keywords["finish"] = message_fields.get("finish", "[完成审核]")
                        if not isinstance(keywords["submit"], str):
                            keywords["submit"] = "[提交审核]"
                        if not isinstance(keywords["finish"], str):
                            keywords["finish"] = "[完成审核]"
                        parsed_mails = mail.receive(
                            os.path.join(storage, "temp"), keywords
                        )
                        for parsed_mail in parsed_mails:
                            try:
                                do_mail(parsed_mail)
                            except Exception as err:
                                text += f"\n错误信息: {err}"
                    except Exception as err:
                        logger.error(err, exc_info=True)
                        text += f"\n错误信息: {err}"
                    finally:
                        stream.ack("receive", message_id)
                        if message_fields.setdefault("source", "") != "cron":
                            wxwork.send_text(text, [message_fields["source"]])
                        mysql.disconnect()
            elif stream_entries[0] == "read":
                for message_id, message_fields in stream_entries[1]:
                    logger.debug(
                        'new item in "%s": (%s) %s',
                        stream_entries[0],
                        message_id,
                        message_fields,
                    )
                    text = f"- [任务结果] -\n\n信息: [邮件处理(本地)]完成\n编号: {message_id}"
                    try:
                        temp_path = os.path.join(
                            storage,
                            "temp",
                            os.path.basename(message_fields["folder"]),
                        )
                        parsed_mail = mail.read(temp_path)
                        if not parsed_mail:
                            raise ValueError("invalid arg: folder")
                        do_mail(parsed_mail)
                    except Exception as err:
                        logger.error(err, exc_info=True)
                        text += f"\n错误信息: {err}"
                    finally:
                        stream.ack("read", message_id)
                        if message_fields.setdefault("source", "") != "cron":
                            wxwork.send_text(text, [message_fields["source"]])
                        mysql.disconnect()
            elif stream_entries[0] == "resend":
                for message_id, message_fields in stream_entries[1]:
                    logger.debug(
                        'new item in "%s": (%s) %s',
                        stream_entries[0],
                        message_id,
                        message_fields,
                    )
                    text = f"- [任务结果] -\n\n信息: [重发邮件]完成\n编号: {message_id}"
                    try:
                        record_id = (
                            int(message_fields["id"])
                            if message_fields["id"].isdigit()
                            else message_fields["id"]
                        )
                        do_resend(record_id, message_fields.setdefault("redirect", ""))
                    except Exception as err:
                        logger.error(err, exc_info=True)
                        text += f"\n错误信息: {err}"
                    finally:
                        stream.ack("resend", message_id)
                        if message_fields.setdefault("source", "") != "cron":
                            wxwork.send_text(text, [message_fields["source"]])
                        mysql.disconnect()
            else:
                logger.debug("invalid stream_entries: %s", stream_entries)
