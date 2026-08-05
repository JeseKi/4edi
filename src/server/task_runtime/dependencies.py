from fastapi import Request

from .runtime import TaskRuntime


def get_task_runtime(request: Request) -> TaskRuntime:
    return request.app.state.runtime.task_runtime
