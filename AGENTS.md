对于 python 测试，你需要以 `.venv/bin/python -m pytest . -q` 这样的格式来跑测试。
后端实际开发和文件分布应当参考 src/server/example_module。
示例模块的服务层按 `service/short_transactions.py`（请求短事务）与 `service/long_tasks.py`（worker 长时任务）划分；创建任务与持久化入队必须处于同一短事务。
如果需要补全数据库中可能缺失的字段，应当优先编写 alembic 的数据库迁移脚本，而非在代码中进行硬性的 ensure， 同时, 为了避免数据库迁移失败, `revision` 应当限制在 16 个字符内。
每完成一整轮修改，应当 make check 来确保当前系统代码可以通过检查，若修改的代码涉及到前端还需要进行 pnpm build。
应用的运行日志通常在 logs 下。