# -*- coding: utf-8 -*-
"""商城 worker 长时任务。

- 支付超时自动取消订单并恢复库存
- 发货后超时自动确认收货并解冻资金

每个数据库阶段通过 ``TaskContext.run_db`` 在独立短事务内完成；状态机
均带幂等保护（状态校验 + 时间校验）。
"""

from __future__ import annotations

from src.server.task_runtime import TaskContext, TaskDefinition, TaskQueue


def _handle_payment_timeout(context: TaskContext, order_no: str) -> None:
    from . import short_transactions as service

    context.run_db(lambda db: service.cancel_expired_order(db, order_no))


def _handle_auto_confirm(context: TaskContext, order_no: str) -> None:
    from . import short_transactions as service

    context.run_db(lambda db: service.auto_confirm_order(db, order_no))


MALL_ORDER_PAYMENT_TIMEOUT = TaskDefinition(
    name="mall.order.payment_timeout",
    queue=TaskQueue.IO,
    handler=_handle_payment_timeout,
)

MALL_ORDER_AUTO_CONFIRM = TaskDefinition(
    name="mall.order.auto_confirm",
    queue=TaskQueue.IO,
    handler=_handle_auto_confirm,
)
