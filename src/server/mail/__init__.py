# -*- coding: utf-8 -*-
"""Mail module public API, loaded lazily to avoid configuration cycles."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dependencies import get_mail_delivery_executor, get_mail_sender
    from .runtime import MailDeliveryExecutor, MailDeliveryOverloadedError
    from .schemas import MailAddress, MailContent, MailSendResult
    from .service import MailSender, send_mail


__all__ = [
    "MailAddress",
    "MailContent",
    "MailSendResult",
    "MailSender",
    "MailDeliveryExecutor",
    "MailDeliveryOverloadedError",
    "get_mail_delivery_executor",
    "get_mail_sender",
    "send_mail",
]

_EXPORTS = {
    "MailAddress": ("schemas", "MailAddress"),
    "MailContent": ("schemas", "MailContent"),
    "MailSendResult": ("schemas", "MailSendResult"),
    "MailSender": ("service", "MailSender"),
    "send_mail": ("service", "send_mail"),
    "MailDeliveryExecutor": ("runtime", "MailDeliveryExecutor"),
    "MailDeliveryOverloadedError": ("runtime", "MailDeliveryOverloadedError"),
    "get_mail_delivery_executor": ("dependencies", "get_mail_delivery_executor"),
    "get_mail_sender": ("dependencies", "get_mail_sender"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, attribute_name)
