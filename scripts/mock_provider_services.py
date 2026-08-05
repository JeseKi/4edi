#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start local mock services for external providers and publish runtime config."""

from __future__ import annotations

import importlib
import json
import signal
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.server.config import global_config  # noqa: E402

BACKEND_URL = global_config.providers.mock_provider_backend_url.rstrip("/")
PUBLISH_INTERVAL_SECONDS = global_config.providers.mock_provider_publish_interval_seconds

SERVICE_MODULES = {
    "github_oauth": "src.server.providers.github.server",
    "google_oauth": "src.server.providers.google.server",
    "turnstile": "src.server.providers.cloudflare.server",
    "mail": "src.server.providers.smtp.server",
    "example_external_api": "src.server.providers.example_external_api.server",
}

_running = True


def _publish(configs: dict[str, dict]) -> None:
    body = json.dumps({"providers": configs}).encode("utf-8")
    request = Request(
        f"{BACKEND_URL}/api/dev/providers/runtime-config",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=5) as response:
        response.read()


def _start_services(provider_keys: Iterable[str]):
    services = []
    for provider_key in provider_keys:
        module_name = SERVICE_MODULES.get(provider_key)
        if not module_name:
            raise RuntimeError(f"未知 mock provider：{provider_key}")
        module = importlib.import_module(module_name)
        service = module.start()
        services.append(service)
        print(f"[mock-provider] started {service.provider_key}: {service.config}")
        if service.config.get("base_url"):
            print(f"[mock-provider] {service.provider_key} UI/API: {service.config['base_url']}")
        if service.config.get("inbox_url"):
            print(f"[mock-provider] {service.provider_key} inbox: {service.config['inbox_url']}")
    return services


def _handle_signal(signum, frame) -> None:
    del signum, frame
    global _running
    _running = False


def main() -> None:
    provider_keys = global_config.providers.resolved_mock_list(global_config.app.env)
    if not provider_keys:
        print("[mock-provider] providers.external_provider_mock_list is empty; nothing to start.")
        return

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    services = _start_services(provider_keys)
    configs = {service.provider_key: service.config for service in services}

    try:
        while _running:
            try:
                _publish(configs)
                print(f"[mock-provider] published runtime config to {BACKEND_URL}")
            except HTTPError as exc:
                print(f"[mock-provider] publish failed: HTTP {exc.code} {exc.reason}")
            except URLError as exc:
                print(f"[mock-provider] publish failed: {exc.reason}")
            time.sleep(PUBLISH_INTERVAL_SECONDS)
    finally:
        for service in services:
            service.shutdown()
        print("[mock-provider] stopped")


if __name__ == "__main__":
    main()
