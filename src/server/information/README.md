# 模块：information（分类信息发布）

## 公开接口
- GET `/api/information/categories` - 分类及属性字段定义
- GET `/api/information` - 公开信息列表（仅已通过审核；支持分类/关键词/排序/分页）
- GET `/api/information/{post_id}` - 公开信息详情（浏览量 +1，联系电话打码）
- POST `/api/information` - 登录用户发布信息（进入待审核）
- GET `/api/information/mine` - 我的发布（含完整联系电话与审核状态）
- DELETE `/api/information/{post_id}` - 删除自己发布的信息
- GET `/api/information/admin/posts` - 管理员审核列表
- POST `/api/information/admin/posts/{post_id}/review` - 通过 / 驳回
- POST `/api/information/admin/posts/{post_id}/top` - 置顶 / 取消置顶

## 业务定位
- 仿参考站 https://ljmzj.cn/information/ 的分类信息中心：四大分类（小程序开发 /
  APP开发 / 软件开发 / 网站建设），登录发布、平台审核、游客阅览。
- 新发布的信息一律进入「待审核」（`pending`），管理员通过（`approved`）后才在公开列表
  与详情出现；驳回（`rejected`）需填写原因。

## 数据流
- 路由 -> 依赖注入 `get_database_executor` -> 短事务内同步 ORM -> SQLAlchemy -> SQLite/PostgreSQL
- 联系方式隐私：公开详情/列表不暴露手机号；详情页手机号经 `mask_phone` 打码后返回；
  「我的发布」与管理员列表返回完整手机号。

## 设计要点
- 分类元数据位于 `constants.py`（key -> 中文名 + 属性字段定义），是发布表单与详情属性表
  的唯一事实来源；发布时 `category` 必须属于四类之一，否则 400。
- 本模块无后台长时任务，服务层只需 `service/short_transactions.py`，不引入 task_runtime。
- 管理员审核/置顶通过 `audit_service.attach_audit_context` 记录操作审计。

## 测试结构
- `test_information_router.py` - 路由层测试（API 接口）
- `test_information_service.py` - 服务层测试（业务逻辑与手机号打码）
- `test_information_dao.py` - 数据访问层测试（查询/筛选/排序/分页）

## 用法示例（curl）
```bash
# 分类
curl http://localhost:8000/api/information/categories

# 公开列表
curl "http://localhost:8000/api/information?category=mini_program&sort=latest"

# 发布（需登录，拿 access token）
curl -X POST http://localhost:8000/api/information \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -d '{"category":"mini_program","title":"示例小程序开发","content":"详情内容","contact_name":"张三","contact_phone":"18312345067"}'

# 管理员审核（admin 登录）
curl -X POST http://localhost:8000/api/information/admin/posts/1/review \
  -H 'Authorization: Bearer <admin-token>' -H 'Content-Type: application/json' \
  -d '{"approved": true}'
```
