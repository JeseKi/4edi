# 模块：example_module（模板版）

## 公开接口
- GET `/api/example/ping`
- POST `/api/example/items`
- GET `/api/example/items/{item_id}`
- GET `/api/example/external/status`
- POST `/api/example/tasks`
- GET `/api/example/tasks/{task_id}`

## 业务定位
- 作为最小示例模块，演示一个简单的实体 `Item` 的创建与查询。

## 数据流
- 路由 -> 依赖注入 `get_db` -> `asyncio.to_thread` 包裹同步 ORM -> SQLAlchemy -> SQLite
- 示例外部 API -> `src/server/providers` -> real/fake provider -> 第三方服务或测试替身
- 长时任务 -> 在短事务内写入 `example_async_tasks`、初始日志和 `background_jobs` -> `src/server/task_runtime/worker.py` 独立进程领取并执行

长时任务 handler 不能持有 `Session` 或 ORM 实体跨越外部 I/O。通过 `TaskContext.run_db(...)` 完成一个短数据库阶段；离开回调时需返回不可变 DTO 或标量快照。

## 服务层划分
- `service/short_transactions.py`：HTTP 请求侧的短事务，包括普通实体读写、长时任务创建、查询和持久化入队。
- `service/long_tasks.py`：worker 执行的长时任务定义与 handler；每个数据库读写阶段都通过 `TaskContext.run_db(...)` 执行。
- 创建长时任务时，业务任务、初始日志和 `background_jobs` 必须在同一受控短事务内写入；不要在请求中等待任务执行。

## 测试结构
- `test_example_router.py` - 路由层测试（API接口测试）
- `test_example_service.py` - 服务层测试（业务逻辑测试）
- `test_example_dao.py` - 数据访问层测试（数据库操作测试）

## 用法示例（curl）
```bash
curl http://localhost:8000/api/example/ping

curl -X POST http://localhost:8000/api/example/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"hello"}'
```
