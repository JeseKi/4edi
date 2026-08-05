#!/usr/bin/env python3
"""压测受控后台任务，并同时验证健康检查可用性。"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from statistics import median
from time import perf_counter, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout_seconds: float = 30,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")
    except URLError as error:
        return 0, {"error": str(error.reason)}
    except TimeoutError as error:
        return 0, {"error": str(error)}


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * ratio))
    return ordered[index]


def run_case(
    base_url: str,
    token: str,
    task_count: int,
    item_count: int,
    delay_ms: int,
    health_count: int,
) -> dict[str, Any]:
    def submit(index: int) -> tuple[int, dict[str, Any], float]:
        started_at = perf_counter()
        status, body = request_json(
            base_url,
            "/api/example/tasks",
            method="POST",
            token=token,
            payload={
                "name": f"load-{task_count}-{index}",
                "total_count": item_count,
                "fail_every": 0,
                "delay_ms": delay_ms,
            },
            timeout_seconds=60,
        )
        return status, body, perf_counter() - started_at

    started_at = perf_counter()

    def check_health(_: int) -> tuple[int, dict[str, Any], float]:
        health_started_at = perf_counter()
        status, body = request_json(base_url, "/api/health", timeout_seconds=5)
        return status, body, perf_counter() - health_started_at

    with ThreadPoolExecutor(max_workers=task_count) as executor:
        submissions = [executor.submit(submit, index) for index in range(task_count)]
        sleep(0.1)
        with ThreadPoolExecutor(max_workers=min(health_count, 32)) as health_executor:
            health_results = list(health_executor.map(check_health, range(health_count)))
        submission_results = [future.result() for future in as_completed(submissions)]

    task_ids = [body["id"] for status, body, _ in submission_results if status == 202]
    terminal_statuses: dict[str, str] = {}
    deadline = perf_counter() + max(60, task_count * item_count * delay_ms / 500)
    while len(terminal_statuses) < len(task_ids) and perf_counter() < deadline:
        for task_id in task_ids:
            if task_id in terminal_statuses:
                continue
            status, body = request_json(
                base_url,
                f"/api/example/tasks/{task_id}",
                token=token,
                timeout_seconds=5,
            )
            task_status = body.get("status") if status == 200 else None
            if task_status in {"completed", "failed"}:
                terminal_statuses[task_id] = str(task_status)
        sleep(0.2)

    submit_latencies = [latency for _, _, latency in submission_results]
    health_latencies = [latency for status, _, latency in health_results if status == 200]
    return {
        "concurrent_tasks": task_count,
        "accepted": len(task_ids),
        "submit_p50_ms": round(median(submit_latencies) * 1000, 1),
        "submit_p95_ms": round(percentile(submit_latencies, 0.95) * 1000, 1),
        "health_ok": len(health_latencies),
        "health_total": health_count,
        "health_p50_ms": round(median(health_latencies) * 1000, 1) if health_latencies else None,
        "health_p95_ms": round(percentile(health_latencies, 0.95) * 1000, 1) if health_latencies else None,
        "completed": sum(status == "completed" for status in terminal_statuses.values()),
        "failed": sum(status == "failed" for status in terminal_statuses.values()),
        "unfinished": len(task_ids) - len(terminal_statuses),
        "case_elapsed_seconds": round(perf_counter() - started_at, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--task-counts", default="4,12,20")
    parser.add_argument("--item-count", type=int, default=20)
    parser.add_argument("--delay-ms", type=int, default=100)
    parser.add_argument("--health-count", type=int, default=100)
    args = parser.parse_args()

    status, body = request_json(
        args.base_url,
        "/api/auth/login",
        method="POST",
        payload={"username": args.username, "password": args.password},
    )
    if status != 200:
        raise SystemExit(f"登录失败: HTTP {status}, {body}")
    token = str(body["access_token"])
    results = [
        run_case(
            args.base_url,
            token,
            int(task_count),
            args.item_count,
            args.delay_ms,
            args.health_count,
        )
        for task_count in args.task_counts.split(",")
        if task_count.strip()
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
