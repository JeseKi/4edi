# Fullstack Template

基于 FastAPI + React + Vite 的全栈模板，内置认证、管理员用户管理、示例业务模块、SQLite / PostgreSQL 数据库基础设施、本地日志、前端打包产物托管，以及一套可直接运行的测试样例。

这个仓库默认启用认证、管理、文件资产和示例模块；审计、OAuth 登录和 OAuth
Provider 通过 `config/system.toml` 的 `app.enabled_features` 显式启用。
本地查看完整演示时在 `config/system.toml` 的 `app.enabled_features` 中设置 `all`；非开发环境的 `all` 不包含
仅开发使用的 Provider mock 路由。

可用功能包：`auth`、`admin`（含权限范围管理）、`audit`、`oauth-login`、
`oauth-provider`、`files`、`example`、`frontend-error-reporting`，以及仅开发环境可用的 `dev-providers`。
除 `auth` 外的功能都依赖 `auth`。

这个仓库的开发模式是：

- 开发环境下，前后端分别启动
- 构建或容器部署后，由 FastAPI 直接托管 `dist/` 中的前端 SPA

## 功能概览

- 用户认证：注册、登录、刷新令牌、个人资料、修改密码、TOTP 双因素认证（含 backup codes）
- OAuth 登录：支持通过 `config/system.toml` 的 `oauth.enabled_providers` 选择性启用 GitHub / Google OAuth 登录
- 密码重置：支持发送重置链接与基于 token 的重置流程
- 管理员功能：查看用户列表、更新用户角色/状态/基础信息
- 默认管理员引导：首次初始化数据库时自动创建管理员账号
- 示例业务模块：提供独立的 router / service / dao / tests 结构
- 外部 Provider：支持 GitHub、Google、Turnstile、SMTP、示例外部 API 的 real/mock target 切换
- 数据库基础设施：本地默认 SQLite，生产可使用 PostgreSQL 与显式连接池预算
- 后台任务：同容器的独立 worker 进程、持久化队列、租约恢复与短事务数据库回调
- 文件资产：本地磁盘开发模式与 S3 兼容对象存储预签名直传
- 日志能力：Web、worker、访问和错误日志写入 `logs/`
- SPA 托管：后端在检测到 `dist/` 后会挂载前端静态资源
- 测试样例：后端模块已附带 pytest 测试

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic Settings、Alembic、python-jose、bcrypt、Loguru
- 前端：React 19、Vite 7、React Router 7、Tailwind CSS 4、Ant Design、Axios、TypeScript 5
- 工具链：pnpm、pytest、mypy、ruff、ESLint、Docker、docker compose

## 目录结构

```text
.
├── .env.example
├── Dockerfile
├── Makefile
├── README.md
├── alembic/
├── data/                         # SQLite 数据目录
├── dist/                         # 前端构建产物（构建后生成）
├── logs/                         # 日志目录
├── run.py                        # 本地后端启动入口
├── scripts/
│   ├── init_db.py                # 数据库初始化 / 检查 / 重置脚本
│   └── mock_provider_services.py # 本地 mock provider 一键启动脚本
├── src/
│   ├── client/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── contexts/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── pages/
│   │   └── providers/
│   └── server/
│       ├── admin/                # 管理员接口
│       ├── auth/                 # 认证与密码重置
│       ├── example_module/       # 示例模块
│       ├── providers/            # 外部服务 provider 与本地 mock services
│       ├── task_runtime/         # 持久化任务发布端、worker 与任务注册表
│       ├── config.py
│       ├── database.py
│       └── main.py
├── vite.config.ts
└── package.json
```

## 环境要求

- Python 3.11+
- Node.js 18+
- pnpm

容器镜像当前使用：

- 前端构建阶段：Node 23
- 后端运行阶段：Python 3.11 slim

## 快速开始

### 方式一：使用 Makefile

```bash
make setup
cp .env.example .env
make dev
```

前端开发服务器需要单独启动：

```bash
pnpm dev
```

### 方式二：手动启动

1. 创建并安装 Python 虚拟环境

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. 安装前端依赖

```bash
pnpm install
```

3. 准备环境变量

```bash
cp .env.example .env
```

4. 启动后端

```bash
.venv/bin/python run.py
```

5. 启动前端

```bash
pnpm dev
```

默认地址：

- 前端开发环境：`http://localhost:5173`
- 后端 API：`http://localhost:8000`
- 健康检查：`http://localhost:8000/api/health`

## 系统配置

非敏感的后端基线配置位于 [`config/system.toml`](./config/system.toml)，按 `app`、`database`、`task_database`、`logging`、`tasks`、`files`、`auth`、`mail`、`oauth` 和 `providers` 分区。修改后重启 Web 与 worker 即可生效。

`.env.example` 只保留密钥、数据库 URL、前端 `VITE_*` 构建变量以及 PostgreSQL 备份等容器基础设施变量。配置优先级从高到低为：构造参数、进程环境变量、`.env.{APP_ENV}`、`.env`、`config/system.toml`、代码默认值。因此既有变量名仍可作为临时的部署覆盖；列表变量继续兼容 JSON 数组、逗号分隔和单值格式。

`APP_ENV` 仍是环境变量，用于选择可选的 `.env.{APP_ENV}` 覆盖文件。`DATABASE_URL`、JWT/TOTP/Turnstile/OAuth/SMTP/S3 密钥、初始化管理员凭据、`VITE_*`、`POSTGRES_*` 与 `PG_BACKUP_*` 不应写入 TOML。

常见修改包括：在 `[app]` 设置 CORS、域名、端口和功能包；在 `[database]`、`[task_database]`、`[tasks]` 调整连接和并发预算；在 `[files]`、`[mail]`、`[oauth]` 填写非敏感服务配置。OAuth 密钥、邮件密码等仍通过环境变量提供。

- SQLite 默认写入 `data/database.db`；启动时固定启用 WAL、外键约束和 5 秒 busy timeout。它适合本地开发或低频任务；同一数据库文件只能由一个模板 worker 串行执行任务。
- HTTP 数据库操作统一由 `DatabaseExecutor` 在线程池内执行完整短事务；它先排队、后借连接，并在成功时提交、异常时回滚。业务回调不得执行外部 I/O，也不得返回 ORM 实体或 Session。
- PostgreSQL 的 `[database]` 连接池总预算必须不小于 `executor_max_workers`；还应为 worker、迁移和管理工具预留连接。`[task_database]` 是 worker 的独立预算。
- `POSTGRES_*` 只供可选的本地 Compose PostgreSQL 服务使用；外部 PostgreSQL 只需提供完整 `DATABASE_URL`。

### 自建 PostgreSQL 备份与恢复

`docker-compose.postgres.yml` 内置可选的 pgBackRest 物理备份。它不会在应用启动时执行导出：PostgreSQL 自行归档 WAL，独立的 `postgres-backup` 服务负责调度、状态和恢复演练，故备份异常不会重启 Web 或 worker。

生产环境先生成两份互不相同的密钥：`PG_BACKUP_REPO_CIPHER_PASS` 用于 pgBackRest 的客户端加密；`PG_BACKUP_AGE_RECIPIENT` 是月度逻辑快照的 age 公钥。age 私钥必须离线保存，绝不能写入 `.env`、镜像或服务器日志。

```bash
# 在安全的管理员工作站生成；将 identity 文件离线保存。
age-keygen -o age-identity.txt
age-keygen -y age-identity.txt

# 生成 pgBackRest 加密口令并写入受保护的部署密钥管理系统。
openssl rand -base64 48
```

将以下变量写入生产环境的 `.env`（示例值不可直接用于生产）：

```ini
PG_BACKUP_ENABLED=true
PG_BACKUP_MODE=auto
PG_BACKUP_STANZA=template
PG_BACKUP_REPO_CIPHER_PASS=<independent-random-secret>
PG_BACKUP_AGE_RECIPIENT=age1...

# 优先使用 S3 或任意兼容对象存储；bucket 必须预先创建。
PG_BACKUP_S3_BUCKET=production-database-backups
PG_BACKUP_S3_ENDPOINT=s3.example.com
PG_BACKUP_S3_PORT=443
PG_BACKUP_S3_REGION=us-east-1
PG_BACKUP_S3_ACCESS_KEY_ID=<backup-writer>
PG_BACKUP_S3_SECRET_ACCESS_KEY=<backup-writer-secret>
PG_BACKUP_S3_PREFIX=/fullstack-template/production
PG_BACKUP_S3_URI_STYLE=path
PG_BACKUP_S3_VERIFY_TLS=y
```

`PG_BACKUP_S3_ENDPOINT` 只填写主机名，不包含 `https://` 或路径；端口由 `PG_BACKUP_S3_PORT` 指定。S3 端点必须提供 HTTPS，`PG_BACKUP_S3_VERIFY_TLS=n` 只用于临时接受自签名证书，不能启用明文 HTTP。`auto` 模式仅在所有 S3 变量都未配置时使用独立的 `postgres-backups` 本地卷；任意 S3 变量不完整都会拒绝启动。S3 已配置但不可用时不会静默回退到本地。为了明确提示这种非异地保护状态，本地模式会让 `postgres-backup` 保持 `unhealthy` 并输出告警日志；应用仍可继续运行。

调度和保留策略：每 5 分钟执行 pgBackRest 校验，WAL 的 `archive_timeout` 为 5 分钟；每周日 02:00 全量、其余每日 02:00 差异，保留 5 个全量链及每链 6 个差异备份，约可进行 35 天 PITR。每月 1 日 03:30 生成一个 age 加密的 `pg_dump -Fc` 快照并保留 12 个；每月 2 日 03:30 将最新物理备份恢复到隔离临时实例并验证可启动，若备份中已有 `alembic_version` 则额外校验其版本可读。

S3 凭据仅应拥有对应 bucket 前缀的 list/read/write/delete 权限。建议在 bucket 上开启版本控制，并按组织政策清理非当前版本；pgBackRest 本身会按保留策略删除过期恢复链。`postgres-backup` 的健康检查会在 WAL 校验超过 10 分钟、物理备份超过 26 小时、全量超过 8 天、月度快照或恢复演练超过 40 天时变为 `unhealthy`。

按时间点恢复只写入一个必须为空的目录，绝不覆盖 `postgres-data`：

```bash
scripts/restore_postgres_pitr.sh postgres-restore/incident-1 '2026-07-29 10:15:00+00'
```

恢复完成后，可使用同版本 PostgreSQL 容器以无对外端口方式挂载该目录进行检查或导出。月度快照恢复到同一集群中一个新数据库，脚本会拒绝使用当前生产数据库名：

```bash
scripts/restore_postgres_monthly.sh ./template-2026-08-01T033000Z.dump.age \
  ./age-identity.txt template_restore_202608
```
- 首次数据库初始化会按 `INIT_ADMIN_*` 引导管理员；生产环境请同时替换三项默认值
- 开发/测试环境如果未配置邮件发送账号，验证码和重置链接会写入日志，便于本地联调

## 文件资产

文件模块提供私有文件资产，不把文件内容写入数据库，也不绑定任意业务资源。业务模块应自行保存 `file_id` 或维护自己的关联表和资源级授权。

- `FILE_STORAGE_DRIVER=local` 是开发默认值，文件写入 `FILE_LOCAL_ROOT`（默认 `data/uploads`，已被 compose 的 `data` volume 持久化）。
- `FILE_STORAGE_DRIVER=s3` 使用短时预签名 POST；必须配置 bucket，若配置静态凭据则 access key 与 secret 必须成对提供。`FILE_S3_ENDPOINT_URL` 必须可同时被后端与浏览器访问。
- bucket 保持私有。浏览器直传需在对象存储 CORS 中允许应用来源的 `POST`、`GET`，并允许 `Content-Type` 与 S3 签名相关的 `x-amz-*` 请求头。
- 默认仅允许常见图片、PDF、文本、CSV 与 Office 文档，单文件上限 50 MiB；准入只依据 `FILE_ALLOWED_EXTENSIONS` 白名单，不读取客户端 MIME 或文件内容。可通过 `FILE_MAX_UPLOAD_BYTES` 调整大小上限。
- 上传意图一小时后过期。创建意图和过期清理任务在同一短事务持久化；删除与过期对象由 worker 异步、幂等清理。

## 后台任务队列与压测边界

容器和 `run.py` 都会同时启动两个进程：Web 仅接收 HTTP 请求并发布任务，worker 不监听端口、只领取 `background_jobs` 中的任务。两者共用同一数据库，因此不需要 HTTP、Socket 或额外端口来传递任务。

示例后台任务使用模板提供的持久化运行时：提交时先用独立短事务完成鉴权，再在**同一受控事务**内写入业务任务、初始日志和 `background_jobs`。HTTP 请求不等待 worker 或内存队列；任一写入失败会整体回滚。任务 payload 必须是 JSON，大型或敏感数据应只传业务记录 ID。worker 在无 Session 状态下执行，所有数据库操作必须通过短生命周期的 `context.run_db(...)` 执行；回调外只能使用 dataclass / 标量等快照，不能保留 ORM 实体。

任务没有积压数量上限，`background_jobs` 会持续增长；部署方必须监控积压和数据库容量，并制定历史任务清理策略。运行中任务以租约维持；重启或异常退出后，租约到期的任务会重新排队，语义为“至少一次执行”，因此 handler 必须幂等。`TASK_DISPATCH_POLL_INTERVAL_SECONDS`、`TASK_JOB_LEASE_SECONDS` 与 `TASK_JOB_HEARTBEAT_INTERVAL_SECONDS` 分别控制领取频率、租约时长与心跳间隔。SQLite 下 worker 强制单执行槽位；PostgreSQL 下可按 `TASK_IO_WORKERS`、`TASK_NOTIFICATION_WORKERS`、`TASK_BATCH_WORKERS` 调整队列并发。

### 2026-07-13 本机参考结果（非生产容量承诺）

测试机器为 AMD Ryzen 7 7745HX（8 核 / 16 线程）、30 GiB 内存（测试开始时约 17 GiB 可用）；Python 3.11.14、FastAPI 0.115.0、SQLAlchemy 2.0.35、Uvicorn 0.30.6。服务使用单个 Uvicorn worker、回环网络和隔离 SQLite 文件；`batch` 配置保持默认的 2 worker / 16 队列槽位。每个任务处理 20 项，每项模拟 100ms 非数据库等待；压测期间额外并发请求 100 次 `/api/health`。

| 并发提交任务数 | 提交成功 | 健康检查成功 | 健康检查 P50 / P95 | 任务结果 | 用例耗时 | 结论 |
| --- | ---: | ---: | --- | --- | ---: | --- |
| 4 | 4 / 4 | 100 / 100 | 81.1ms / 132.7ms | 4 完成，0 失败 | 6.47s | 通过 |
| 12 | 未完成 | 0 / 100（3 秒超时） | 不适用 | 未完成 | 超过 20 秒仍阻塞 | 不通过 |

因此，在当前默认 SQLite 配置下，只能将“4 个这类并发批任务 + 100 个并发健康检查”视为已验证的参考场景；12 个并发批任务已跨越当前实现的稳定边界。SQLite 只有文件级并发特性，且没有 PostgreSQL/MySQL 的 `QueuePool` 行为，无法验证 KiVault 曾遇到的连接池耗尽问题。

### 2026-07-13 Compose PostgreSQL 复测：持久化队列改造前的边界

同一台测试机、单个 Uvicorn worker、回环网络，使用项目自带的 `postgres:17-alpine` Compose 服务；任务参数仍为每任务 20 项、每项 100ms 非数据库等待，并发请求 100 次 `/api/health`。应用的 PostgreSQL 连接池为默认预算（`pool_size=5`、`max_overflow=5`）。

| 并发提交任务数 | 提交成功 | 健康检查成功 | 健康检查 P50 / P95 | 任务结果 | 结论 |
| --- | ---: | ---: | --- | --- | --- |
| 4 | 4 / 4 | 100 / 100 | 74.3ms / 188.8ms | 4 完成，0 失败 | 通过：DTO 快照修复后，worker 不再访问已关闭 Session 的 ORM 实体 |
| 6 | 0 / 6（客户端 15 秒超时） | 100 / 100 | 44.7ms / 164.6ms | 无法确认 | 不通过：服务随后出现 `QueuePool` 30 秒超时；PostgreSQL 观察到 10 个 `idle in transaction` 连接 |
| 8 | 已中止 | 健康检查超时 | 不适用 | 已中止并重启测试容器 | 不通过：再次耗尽默认连接池 |

这次复测证明 PostgreSQL 本身已正常运行，且 DTO 快照已修复 detached-instance 任务失败；但这些结果是持久化队列改造前的数据，不能作为当前版本容量承诺。改造后须重新以 4、6、8、12、20 等梯度建立基线，重点确认提交不再等待队列、无 `idle in transaction` 堆积且无 `QueuePool` 超时。

### 2026-07-14 Compose PostgreSQL 复测：Web / worker 双进程版

测试机器为 AMD Ryzen 7 7745HX（8 核 / 16 线程）、30 GiB 内存（测试开始时约 15 GiB 可用）；Python 3.11.14、FastAPI 0.115.0、SQLAlchemy 2.0.35、Uvicorn 0.30.6。使用项目自带的 `postgres:17-alpine`、回环网络、单个 Web 进程与同容器的独立 worker 进程。Web 连接预算为 `5 + 5`，worker 为 `2 + 0`；每个任务处理 20 项，每项模拟 100ms 非数据库等待，并在任务提交期间额外并发请求 100 次 `/api/health`。

| 并发提交任务数 | 提交 P50 / P95 | 提交成功 | 健康检查成功 | 健康检查 P50 / P95 | 任务结果 | 用例耗时 |
| --- | --- | ---: | ---: | --- | --- | ---: |
| 4 | 19.7ms / 19.8ms | 4 / 4 | 100 / 100 | 34.5ms / 95.7ms | 4 完成，0 失败 | 4.77s |
| 8 | 27.9ms / 31.5ms | 8 / 8 | 100 / 100 | 27.4ms / 34.2ms | 8 完成，0 失败 | 9.11s |
| 12 | 48.4ms / 55.3ms | 12 / 12 | 100 / 100 | 27.8ms / 33.4ms | 12 完成，0 失败 | 13.33s |
| 20 | 85.9ms / 101.8ms | 20 / 20 | 100 / 100 | 32.6ms / 34.6ms | 20 完成，0 失败 | 21.80s |
| 100 | 475.5ms / 580.2ms | 100 / 100 | 100 / 100 | 158.6ms / 239.6ms | 100 完成，0 失败 | 106.94s |

本轮共验证 188 个新增 job，全部为 `succeeded`；压测结束后 PostgreSQL 仅有 7 条空闲连接、没有 `idle in transaction`，应用日志也没有 `QueuePool` 超时。**因此当前配置已验证至少可承受这类 100 个并发提交任务，同时保持 100 个并发健康检查可用。**这不是最大容量承诺：`batch` 队列当前只有 2 个 worker，故任务总耗时会随积压近似线性增长；生产部署仍须以目标硬件、真实外部 I/O、Web 副本数及 PostgreSQL `max_connections` 重新压测。

可用以下脚本在目标环境复测（先启动服务并准备管理员账号）：

```bash
.venv/bin/python scripts/load_test_background_tasks.py \
  --base-url http://127.0.0.1:8000 \
  --task-counts 4,6,8,12,20 \
  --submit-timeout-seconds 15 \
  --completion-timeout-seconds 60
```

脚本位于 `scripts/load_test_background_tasks.py`，可通过 `--submit-timeout-seconds`、`--health-timeout-seconds` 和 `--completion-timeout-seconds` 分别限制提交、健康检查和任务完成等待时间；它会创建示例任务与审计记录，因此应只对测试环境运行。高并发但 worker 数较少时，应按预期排队时长调大 `--completion-timeout-seconds`。

生产前应以目标数据库和真实 Web worker 数重新压测，并至少同时观察：任务队列长度、提交等待时间、健康检查/鉴权的 P95 延迟、数据库活动连接数，以及 `QueuePool` 超时数。完成“明确配置并校准连接池”后，才应为具体部署设定容量边界。

## 本地 Mock Provider

本项目的 provider mock 模式不是在后端直接返回假数据，而是启动本地 mock service。后端仍然执行真实 HTTP/SMTP 请求，只是目标地址由 dev runtime config 指向本地随机端口。

1. 在 `config/system.toml` 的 `[providers]` 中启用需要 mock 的 provider：

```toml
[providers]
external_provider_mock_list = ["github_oauth", "google_oauth", "turnstile", "mail", "example_external_api"]
mock_provider_backend_url = "http://localhost:8000"
```

2. 启动后端和前端：

```bash
.venv/bin/python run.py
pnpm dev
```

3. 另开终端启动 mock services：

```bash
.venv/bin/python scripts/mock_provider_services.py
```

脚本会为每个 mock service 绑定随机端口，并持续调用 `POST /api/dev/providers/runtime-config` 把配置推给后端。浏览器侧配置通过 `GET /api/dev/providers/frontend-config` 从后端读取，所以不需要手动填写随机端口。

可用 mock provider：

- `github_oauth`：带确认页的 GitHub OAuth mock
- `google_oauth`：带确认页的 Google OAuth mock
- `turnstile`：提供 mock `api.js` 和 siteverify API
- `mail`：本地 SMTP mock，并提供 inbox 页面查看收到的邮件
- `example_external_api`：示例 HTTP API mock

更多细节见 [src/server/providers/README.md](./src/server/providers/README.md) 及各 provider 子目录 README。

## 2FA 流程

- 用户未开启 2FA 时，`POST /api/auth/login` 保持原行为，直接返回 access token 并设置 refresh cookie
- 用户已开启 2FA 时，`POST /api/auth/login` 返回 `202` 和一次性的 `challenge_token`
- 前端继续调用 `POST /api/auth/2fa/verify`，提交 `challenge_token + TOTP/backup code`
- 在个人中心可以完成 2FA 开启、关闭以及 backup codes 重新生成

## OAuth 流程

- `GET /api/oauth/providers` 返回当前启用的 OAuth 渠道，前端按 `GITHUB` / `GOOGLE` 显示对应登录按钮
- `GET /api/oauth/github/authorize` 发起 GitHub OAuth，`GET /api/oauth/github/callback` 处理 GitHub 回调
- `GET /api/oauth/google/authorize` 发起 Google OAuth，`GET /api/oauth/google/callback` 处理 Google 回调
- GitHub 首次登录会使用已验证主邮箱自动创建普通用户；邮箱已存在时绑定已有本地用户
- Google 首次登录会使用已验证邮箱自动创建普通用户；邮箱已存在时绑定已有本地用户
- OAuth 回调后前端通过一次性 ticket 换取本地登录态，ticket 仅可使用一次并会过期
- 已开启本地 2FA 的用户在第三方 OAuth 验证后仍需输入本地 TOTP 或 backup code

## OAuth Provider 流程

- 管理员通过 `/api/oauth-provider/clients` 管理可接入本系统的 OAuth Client
- Authorization Code + PKCE：第三方应用跳转 `/oauth/authorize`，确认后用 `POST /api/oauth-provider/token` 换取 token
- Device Code Flow：设备端调用 `POST /api/oauth-provider/device_authorization` 获取 `device_code/user_code`
- 用户在 `verification_uri` 或 `/oauth/device` 输入 `user_code` 并确认授权
- 设备端轮询 `POST /api/oauth-provider/token`，`grant_type` 使用 `urn:ietf:params:oauth:grant-type:device_code`

## 开发说明

### 后端

本地启动：

```bash
.venv/bin/python run.py
```

`run.py` 是完整的本地集成入口：它同时监督 Web 与 worker；任一子进程非正常退出时，另一个会被停止，方便尽早暴露故障。它**不启用热重载**，修改后请整体重启，避免 Web 与 worker 使用不同版本的任务定义。

只开发 Web API、且不需要执行后台任务时，可以单独启动：

```bash
.venv/bin/python -m uvicorn src.server.main:app --reload --port 8000
```

后端会在启动时：

- 加载 `config/system.toml`，再加载 `.env` 与 `.env.{APP_ENV}` 作为覆盖
- 初始化日志配置
- 假定数据库 schema 已由 Alembic 迁移到最新版本
- 幂等引导默认管理员和内置 provider 记录
- Web 进程只发布任务；worker 由 `run.py` 或容器启动
- 如果 `dist/` 存在，则在根路径挂载前端 SPA

### 前端

```bash
pnpm dev
pnpm build
pnpm preview
pnpm lint
```

前端通过 [`src/client/lib/api.ts`](/home/jese--ki/Projects/dev/fullstack-template/src/client/lib/api.ts) 中的 Axios 实例访问后端，默认基地址为 `/api`。

### 数据库工具

```bash
.venv/bin/alembic upgrade head
.venv/bin/python scripts/init_db.py
.venv/bin/python scripts/init_db.py --check
.venv/bin/python scripts/init_db.py --reset
```

`scripts/init_db.py` 会执行 `alembic upgrade head` 并引导默认管理员等业务数据。
如果已有数据库是旧版 `create_all()` 生成且缺少 `alembic_version`，确认 schema 与当前模型匹配并备份后，再执行：

```bash
docker compose run --rm --entrypoint sh app -lc "alembic stamp head"
```

## 质量检查与测试

后端测试请使用仓库约定命令：

```bash
.venv/bin/python -m pytest . -q
```

默认测试配置使用 4 个 `pytest-xdist` worker；每个 worker 只创建一次 SQLite
schema 模板，各用例从模板复制独立数据库文件，以同时保持隔离和测试速度。
排查顺序相关问题时可临时追加 `-n 0` 关闭并行。

PostgreSQL 兼容性测试使用独立、可销毁且名称包含 `test` 的数据库；测试会执行升级和降级迁移：

```bash
TEST_DATABASE_URL=postgresql+psycopg://template:change-me@127.0.0.1:5432/template_test \
  .venv/bin/python -m pytest . -q -m postgresql
```

常用检查：

```bash
pnpm lint
.venv/bin/ruff check --fix
.venv/bin/mypy .
```

也可以直接执行：

```bash
make check
```

## 生产构建与部署

### 构建前端并由后端托管

```bash
pnpm build
.venv/bin/python run.py
```

构建完成后，后端会从 `dist/` 提供前端静态资源，并对非 `/api` 路径执行 SPA 回退。

### Docker

默认 Compose 不会启动 PostgreSQL，应用会使用 `.env` 或部署环境中的 `DATABASE_URL`；`config/` 会以只读方式挂载到容器，覆盖镜像内的版本化基线：

```bash
docker compose up -d --build
```

若希望由仓库自动提供 PostgreSQL，先在 `.env` 设置安全的 `POSTGRES_PASSWORD`，再叠加 PostgreSQL 配置：

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

该模式中，PostgreSQL 容器首次初始化时通过 `POSTGRES_DB` 创建数据库；应用会等待其健康检查，通过内部 `database` 网络中的 `postgres:5432` 连接，随后自动重试 `alembic upgrade head`。`postgres-data` volume 会保留数据库；修改 `POSTGRES_DB` 不会为已有 volume 自动创建新数据库。PostgreSQL 默认不映射宿主机端口；需要管理时使用 `docker compose exec postgres psql`，或由运维额外提供受控访问入口。

使用外部 PostgreSQL 时不叠加该文件，只在部署环境设置 `DATABASE_URL=postgresql+psycopg://...`。应用会重试迁移连接，但不会创建 PostgreSQL 数据库本身；数据库须由平台或管理员预先创建。

当前容器行为：

- 构建阶段执行前端打包
- 运行阶段重试执行 `alembic upgrade head`
- SQLite 模式下启动时确保数据库目录存在并轮转文件备份；PostgreSQL 模式下跳过文件备份
- PostgreSQL 备份默认关闭；设置 `PG_BACKUP_ENABLED=true` 后启用 pgBackRest WAL 归档与独立 `postgres-backup` 调度服务
- 最终以 `python run.py` 监督同一容器中的 Web 与 worker；worker 没有对外端口
- 任一子进程异常退出时，容器以非零状态退出；Compose 默认 `restart: unless-stopped` 会重启整个一致性单元
- Web 日志为 `logs/app.log` / `logs/error.log`，前端请求失败日志为 `logs/frontend/frontend-error.log`，worker 日志为 `logs/worker.log` / `logs/worker-error.log`

`docker-compose.yml` 默认挂载：

- `./data:/app/data`
- `./logs:/app/logs`

## 相关接口文档

- 认证模块文档：[src/server/auth/README.md](./src/server/auth/README.md)
- 示例模块文档：[src/server/example_module/README.md](./src/server/example_module/README.md)
- 外部 Provider 文档：[src/server/providers/README.md](./src/server/providers/README.md)

可直接试用：

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/example/ping
```

## 开发约定

- 路由层负责参数校验与编排
- 业务逻辑放在 service 层
- 数据访问下沉到 DAO 层
- 新增模块时，需要在 Alembic env 的模型导入路径中导入模型，并在 `main.py` 中挂载 router
- 数据库 schema 变更需要新增 Alembic 迁移，不能依赖应用启动时 `create_all()`
- 测试环境下数据库会被重建，以保证测试隔离
