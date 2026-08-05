# -*- coding: utf-8 -*-
"""
邮件依赖模块（模板版）

公开接口：
- get_mail_sender: 获取默认 MailSender 实例
"""

from functools import lru_cache

from fastapi import Request

from .service import MailSender
from .runtime import MailDeliveryExecutor


@lru_cache
def get_mail_sender() -> MailSender:
    """获取默认 MailSender 实例，用于依赖注入。"""

    return MailSender()


def get_mail_delivery_executor(request: Request) -> MailDeliveryExecutor:
    """获取当前 Web 进程的受控邮件投递执行器。"""
    return request.app.state.runtime.mail_delivery_executor


__all__ = ["get_mail_delivery_executor", "get_mail_sender"]
