# -*- coding: utf-8 -*-
"""External provider boundary."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import (
        get_example_external_api_provider,
        get_github_oauth_provider,
        get_google_oauth_provider,
        get_mail_provider,
        get_turnstile_provider,
        sync_external_providers,
    )

__all__ = [
    "get_example_external_api_provider",
    "get_github_oauth_provider",
    "get_google_oauth_provider",
    "get_mail_provider",
    "get_turnstile_provider",
    "sync_external_providers",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import service

        return getattr(service, name)
    raise AttributeError(name)
