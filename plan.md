# F1~F4 电商功能实施计划（P0）

> F1 已完成（2026-08-17，后端 7 测试 + 前端售后中心/卖家退款管理，make check 与 pnpm build 通过）。
> F2 已完成（2026-08-17，后端 5 测试 + 前端评价中心/卖家评价管理/商品详情评价区，make check 与 pnpm build 通过，本地库迁移至 eval_0005）。
> F3 已完成（2026-08-17，后端 5 测试 + 前端领券中心/卖家券管理/平台券管理/结算选券抵扣，make check（224 测试）与 pnpm build 通过，本地库迁移至 coupon_0006）。
> F4 已完成（2026-08-17，后端 4 测试 + 前端收藏/关注/浏览足迹，make check（228 测试）与 pnpm build 通过，本地库迁移至 fav_0007）。
> 以下为 F1~F4 计划回顾。F1~F4（售后/评价/优惠券/收藏足迹）已全部完成。

---

# F2 商品评价/晒单 实施计划（已完成）

> 目标：确认收货后可评价（评分+文字+晒图）、追评、卖家回复；商品详情页评价列表+评分汇总；买家评价中心（待评价/已评价）；卖家评价管理。
> 2026-08-17 完成：mall_goods_evaluations 表（迁移 eval_0005）、评价/追评/卖家回复/列表/汇总/待评价服务与路由、test_mall_evaluation.py 5 测试、前端评价中心（/mall/evaluations）与卖家评价管理（/mall/seller/evaluations）、商品详情评价区、订单详情"去评价"入口。

---

# F1 售后退款/退货 实施计划（已完成）

> 目标：实现买家申请退款（仅退款/退货退款）、卖家处理（同意/拒绝/确认退货收货）、买家取消、超时自动同意（worker）、管理员仲裁、微信/mock 退款通道、退款成功后钱包扣回与库存回补。UI：买家售后中心 + 订单详情售后入口，卖家退款管理页。

## 一、数据模型（src/server/mall/models.py + alembic 迁移 refund_0004）

### 新表 `mall_refunds`（Refund 模型）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| refund_no | String(32) unique | 商户退款单号（R 前缀，同时作为微信 out_refund_no） |
| order_no | FK mall_orders.order_no | |
| shop_id | FK mall_shops.id | |
| buyer_id | FK users.id | |
| type | SQLEnum(RefundType) | refund_only / return_refund |
| status | SQLEnum(RefundStatus) | pending/returning/refunding/success/rejected/cancelled |
| order_status_snapshot | SQLEnum(OrderStatus) | 申请时订单状态，取消/拒绝时恢复用 |
| reason | String(200) | 申请原因 |
| description | Text nullable | 详细说明 |
| evidence_images | JSON default list | 凭证图 URL |
| amount_fen | BigInteger | 退款金额=订单实付 |
| return_tracking_company / return_tracking_no | String nullable | 退货物流 |
| return_shipped_at / return_received_at | DateTime nullable | |
| channel | String(20) nullable | 退款通道 wechat/mock |
| channel_refund_id | String(64) nullable | 微信 refund_id |
| refuse_reason | Text nullable | 拒绝原因 |
| decided_at / success_at | DateTime nullable | |
| created_at / updated_at | DateTime | |

### 新枚举
- `RefundType`: REFUND_ONLY="refund_only" / RETURN_REFUND="return_refund"
- `RefundStatus`: PENDING="pending" / RETURNING="returning" / REFUNDING="refunding" / SUCCESS="success" / REJECTED="rejected" / CANCELLED="cancelled"

### OrderStatus 扩展（订单表）
- 增加 `REFUNDING="refunding"`、`REFUNDED="refunded"`
- Order 增加字段：`refunded_at: DateTime nullable`

### 迁移 `alembic/versions/0004_refund_tables.py`
- revision=`refund_0004`（≤16 字符），down_revision=`mall_0003`
- 创建 mall_refunds 表 + 索引（refund_no unique、order_no、shop_id）
- mall_orders 增加 refunded_at 列
- orderstatus 枚举扩展：
  - PostgreSQL：`ALTER TYPE orderstatus ADD VALUE 'REFUNDING'` / `'REFUNDED'`（先 COMMIT 再 ADD VALUE 需注意 PG11+ 支持在事务内？PG 不允许事务内 ADD VALUE 后在同一事务使用——用 `op.get_bind()` 判断 dialect，执行 `ALTER TYPE ... ADD VALUE IF NOT EXISTS` 且不依赖新值）
  - SQLite：`batch_alter_table` 重建 status 列（新枚举值列表）
  - 用 `op.get_bind().dialect.name` 分支处理

### 配置（config.py MallConfig）
- `refund_auto_agree_hours: int = 72`（ge=1, le=720）超时自动同意

## 二、支付通道退款能力（payment/）

### base.py
- 新增 `RefundResult` dataclass：success / refund_id / message
- `PaymentProvider` 新增抽象方法 `create_refund(*, out_refund_no, out_trade_no, amount_fen, total_fen, description) -> RefundResult`

### mock.py
- `create_refund` 直接返回 `RefundResult(success=True, refund_id=f"mock-refund-{out_refund_no}")`

### wechat_v3.py
- `create_refund`：`client.refund(out_refund_no=..., out_trade_no=..., amount={"refund": amount_fen, "total": total_fen, "currency": "CNY"}, reason=description, notify_url=...)`；code!=200 抛 RuntimeError；解析 refund_id

## 三、服务层（service/short_transactions.py）

### 状态机流转
```
买家申请（订单 PAID/SHIPPED/COMPLETED）
  → Refund(PENDING)，订单 → REFUNDING，同事务入队自动同意任务
买家取消（PENDING）→ CANCELLED，订单恢复 snapshot
卖家拒绝 / 管理员驳回（PENDING）→ REJECTED，订单恢复 snapshot
卖家同意 / 管理员同意（PENDING）：
  refund_only → 发起通道退款 → REFUNDING（real 等回调）/ SUCCESS（mock）
  return_refund → RETURNING（等买家寄回）
买家填退货物流（RETURNING）→ 记录单号
卖家确认收到退货 / 管理员确认（RETURNING）→ 发起通道退款 → REFUNDING / SUCCESS
通道回调成功（REFUNDING）→ SUCCESS：扣钱包、回补库存、订单 REFUNDED
worker 超时自动同意（PENDING 超时）→ 同上"卖家同意"
```

### 新增服务函数
- `apply_refund(db, runtime, user_id, *, order_no, type, reason, description, evidence_images)` — 校验订单状态/无进行中退款/类型匹配（refund_only 仅 PAID；return_refund 仅 SHIPPED/COMPLETED）；创建退款单；订单→REFUNDING；enqueue `MALL_REFUND_AUTO_AGREE`（同事务）；OrderLog
- `cancel_refund(db, user_id, refund_no)` — 仅 PENDING；订单恢复 snapshot
- `list_my_refunds(db, user_id, page, page_size)` / `get_my_refund(db, user_id, refund_no)`
- `submit_return_tracking(db, user_id, refund_no, *, company, tracking_no)` — 仅 RETURNING
- `seller_agree_refund(db, principal, refund_no, *, shop_id=None)` — PENDING→发起退款/进入 RETURNING
- `seller_reject_refund(db, principal, refund_no, *, reason, shop_id=None)` — PENDING→REJECTED
- `seller_confirm_return(db, principal, refund_no, *, shop_id=None)` — RETURNING→发起退款
- `seller_list_refunds(db, principal, *, status, page, page_size, shop_id=None)` / `seller_get_refund(...)`
- `admin_list_refunds(db, *, status, page, page_size)` / `admin_handle_refund(db, refund_id, *, approved, reason, handler_user_id)` — 仲裁同意（PENDING/RETURNING）或驳回（PENDING）
- `auto_agree_refund(db, refund_no)` — worker；PENDING 且超时（refund_auto_agree_hours）自动同意；幂等
- `_initiate_refund(db, refund, handler_user_id)` — 内部：调 provider.create_refund（失败抛 HTTPException 502，保持 PENDING 可重试）；real → REFUNDING + channel 记录；mock → 直接 `_complete_refund_success`
- `_complete_refund_success(db, refund, *, channel_refund_id)` — 幂等：SUCCESS 已返回；按 snapshot 扣钱包（COMPLETED→available_fen，PAID/SHIPPED→frozen_fen）+ ledger（SALE 负向，FROZEN/AVAILABLE 对应）；回补库存（_restore_stock 复用）+ sales 回减；订单→REFUNDED + refunded_at；Refund→SUCCESS + success_at；OrderLog
- `handle_refund_notification(db, *, out_refund_no, refund_status, channel_refund_id)` — 微信退款回调入口

### worker（service/long_tasks.py）
- `MALL_REFUND_AUTO_AGREE = TaskDefinition(name="mall.refund.auto_agree", queue=TaskQueue.IO, handler=_handle_refund_auto_agree)`；`_handle_refund_auto_agree` 调 `service.auto_agree_refund(db, refund_no)`
- `src/server/platform/features.py` `_mall_tasks()` 加入导出
- `service/__init__.py` 补充导出

## 四、Schema 与路由

### schemas.py 新增
- `RefundStatusLiteral` / `RefundTypeLiteral`
- `RefundCreateIn`（order_no, type, reason, description?, evidence_images?）
- `RefundOut`（全字段）
- `RefundRejectIn`（reason）
- `ReturnTrackingIn`（return_tracking_company, return_tracking_no）
- `RefundHandleIn`（approved, reject_reason?）
- OrderStatusLiteral 扩展 refunding/refunded

### 路由（router.py）
买家（router）：
- POST /api/mall/refunds — 申请
- GET /api/mall/refunds — 我的退款列表（分页）
- GET /api/mall/refunds/{refund_no} — 详情
- POST /api/mall/refunds/{refund_no}/cancel — 取消
- POST /api/mall/refunds/{refund_no}/return-tracking — 填退货物流
卖家（seller_router）：
- GET /api/mall/seller/refunds（status 筛选 + shop_id 参数）
- GET /api/mall/seller/refunds/{refund_no}
- POST /api/mall/seller/refunds/{refund_no}/agree
- POST /api/mall/seller/refunds/{refund_no}/reject
- POST /api/mall/seller/refunds/{refund_no}/confirm-return
管理员（admin_router）：
- GET /api/mall/admin/refunds（status 筛选）
- POST /api/mall/admin/refunds/{refund_id}/handle（仲裁，写 audit）
通道：
- POST /api/mall/payments/wechat/refund-notify（微信退款回调，验签失败 400，幂等 SUCCESS）

## 五、后端测试（src/server/mall/tests/test_mall_refund.py）

复用现有 helper（_register/_login/_seed_shop_and_goods）。覆盖：
1. 仅退款全流程：下单→mock 支付→申请→卖家同意→SUCCESS；校验订单 REFUNDED、frozen 钱包扣回、库存回补、sales 回减、ledger 负向
2. 退货退款全流程：发货→申请→同意→RETURNING→买家填单→卖家确认→SUCCESS
3. 买家取消退款：订单恢复原状态、可重新申请
4. 卖家拒绝：订单恢复、原因记录
5. 幂等：重复同意/重复回调不重复扣钱
6. 校验：未支付订单不可申请、重复申请拒绝、类型与状态不匹配拒绝、非本店卖家 403、非买家本人 404
7. 管理员仲裁：同意/驳回
8. worker：auto_agree_refund 幂等（超时/未超时）

## 六、前端

### types.ts
- MallOrderStatus 增加 `'refunding' | 'refunded'`；MallOrder 增加 `refunded_at: string | null`
- 新增 `MallRefundStatus`、`MallRefundType`、`MallRefund` 接口
### mallFormat.ts
- MALL_ORDER_STATUS_LABELS 增加 refunding:'退款中' / refunded:'已退款'
- 新增 MALL_REFUND_STATUS_LABELS、MALL_REFUND_TYPE_LABELS
### lib/mall.ts（买家）
- createMallRefund / listMyMallRefunds / getMallRefund / cancelMallRefund / submitMallRefundReturnTracking
### lib/sellerMall.ts（卖家+管理员）
- listSellerRefunds / getSellerRefund / agreeSellerRefund / rejectSellerRefund / confirmSellerRefundReturn
- listAdminRefunds / handleAdminRefund
### 买家页面
- 新建 `pages/mall/RefundListPage.tsx`（/mall/refunds 售后中心：列表 + 状态筛选 + 进度 Timeline + 操作：取消/填退货单号）
- `OrderDetailPage.tsx`：REFUNDING 状态显示"退款进度"入口；PAID/SHIPPED/COMPLETED 显示"申请退款"按钮 + Modal（类型/原因/说明）；退款申请后跳转售后中心；状态标签色/Steps 适配
- `App.tsx` 注册 /mall/refunds 路由
### 卖家页面
- 新建 `pages/mall/seller/RefundManagePage.tsx`（/mall/seller/refunds：列表 + 状态筛选 + 详情展开 + 同意/拒绝/确认退货操作 Modal）
- `SellerLayout.tsx` 菜单增加"退款管理"
- `App.tsx` 注册 /mall/seller/refunds 路由

## 七、验证
- 后端：`.venv/bin/python -m pytest . -q`
- `make check`
- 前端：`pnpm build`

## 八、涉及文件清单
- 修改：src/server/mall/models.py、config.py、dao.py（RefundDAO）、schemas.py、router.py、service/short_transactions.py、service/long_tasks.py、service/__init__.py、payment/base.py、payment/mock.py、payment/wechat_v3.py、src/server/platform/features.py、alembic/versions/0004_refund_tables.py（新增）、src/client/lib/types.ts、mallFormat.ts、mall.ts、sellerMall.ts、pages/mall/OrderDetailPage.tsx、components/mall/SellerLayout.tsx、App.tsx
- 新增：src/server/mall/tests/test_mall_refund.py、src/client/pages/mall/RefundListPage.tsx、src/client/pages/mall/seller/RefundManagePage.tsx

---

# F2 商品评价/晒单 实施计划

> 目标：确认收货后可评价（评分+文字+晒图）、追评、卖家回复；商品详情页评价列表+评分汇总；买家评价中心（待评价/已评价）；卖家评价管理。

## 一、数据模型（models.py + alembic 迁移 eval_0005，≤16 字符）

### 新表 `mall_goods_evaluations`（Evaluation 模型）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| order_id | FK mall_orders.id CASCADE | |
| order_item_id | FK mall_order_items.id CASCADE | 唯一：一个订单项仅可评价一次（unique index） |
| goods_id | FK mall_goods.id | index |
| shop_id | FK mall_shops.id | index |
| buyer_id | FK users.id | index |
| rating | Integer | 1-5 |
| content | Text | |
| images | JSON default list | 晒图 URL |
| seller_reply | Text nullable | 卖家回复 |
| seller_replied_at | DateTime nullable | |
| append_content | Text nullable | 追评 |
| append_images | JSON default list | |
| appended_at | DateTime nullable | |
| created_at / updated_at | DateTime | |

- 评分汇总不落库，用聚合查询（AVG(rating)/COUNT/好评率 rating>=4）；评价量上来后再考虑商品表冗余评分字段
- 追评：同一评价记录更新 append_* 字段（每次评价只允许一次追评）

## 二、服务层（short_transactions.py）

- `create_evaluation(db, user_id, *, order_no, order_item_id, rating, content, images)`
  - 校验：订单属于买家且 COMPLETED（确认收货后）；order_item 属于该订单；该 order_item 未评价过
- `append_evaluation(db, user_id, evaluation_id, *, content, images)` — 仅本人、未追评过
- `seller_reply_evaluation(db, principal, evaluation_id, *, content, shop_id=None)` — 仅本店，可多次回复（覆盖或追加？设计：覆盖更新 seller_reply，记录时间）
- `list_goods_evaluations(db, goods_id, page, page_size)` — 公开，按时间倒序；返回 items + rating_summary（avg_rating/rating_count/good_rate）
- `list_my_evaluations(db, user_id, page, page_size)` — 已评价列表（含订单商品信息）
- `list_pending_evaluations(db, user_id)` — 待评价：COMPLETED 订单中未评价的 order_items（去重）

## 三、Schema 与路由

### schemas.py
- `EvaluationCreateIn`（order_no, order_item_id, rating 1-5, content, images?）
- `EvaluationAppendIn`（content, images?）
- `EvaluationReplyIn`（content）
- `EvaluationOut`（全字段 + buyer_username + 商品快照 goods_name/goods_image/sku_specs + 订单号）
- `EvaluationSummaryOut`（avg_rating, rating_count, good_rate）
- `PendingEvaluationOut`（order_no, order_item_id, goods_name, goods_image, sku_specs）

### 路由（router.py）
买家（router）：
- POST /api/mall/orders/{order_no}/evaluations — 评价
- GET /api/mall/evaluations/pending — 待评价列表
- GET /api/mall/evaluations/mine — 已评价列表
- POST /api/mall/evaluations/{evaluation_id}/append — 追评
公开：
- GET /api/mall/goods/{goods_id}/evaluations — 评价列表+评分汇总
卖家（seller_router）：
- GET /api/mall/seller/evaluations（shop_id 参数）
- POST /api/mall/seller/evaluations/{evaluation_id}/reply

## 四、后端测试（tests/test_mall_evaluation.py）

复用现有 helper。覆盖：
1. 未确认收货不可评价；确认收货后可评价；重复评价 400
2. 评价列表+评分汇总正确（好评率）
3. 追评一次、重复追评 400
4. 卖家回复、非本店卖家 404
5. 待评价列表（含已评价过滤）
6. 权限：非本人订单 404

## 五、前端

- types.ts：MallEvaluation、MallEvaluationSummary、PendingEvaluation；mallFormat 无需新增
- lib/mall.ts：createMallEvaluation / listPendingEvaluations / listMyEvaluations / appendMallEvaluation / listGoodsEvaluations
- lib/sellerMall.ts：listSellerEvaluations / replySellerEvaluation
- 新建 `pages/mall/EvaluationCenterPage.tsx`（/mall/evaluations：Tab 待评价/已评价；评价 Modal：星级评分+文字+晒图 URL 列表）
- `OrderDetailPage.tsx`：COMPLETED 订单商品行加"评价"按钮（跳评价中心或直接评价 Modal）——简化：跳转 /mall/evaluations?order_no=xxx
- `GoodsDetailPage.tsx`：商品信息区下方加"商品评价"区（评分汇总 + 列表分页）
- 新建 `pages/mall/seller/EvaluationManagePage.tsx`（/mall/seller/evaluations：评价列表 + 回复 Modal）
- `SellerLayout.tsx` 菜单加"评价管理"；`App.tsx` 注册路由；MallLayout 用户菜单加"评价中心"

## 六、验证与文件清单
- `.venv/bin/python -m pytest . -q` + `make check` + `pnpm build`；本地库 `alembic upgrade head` 验证 eval_0005
- 新增：alembic/versions/0005_evaluation_tables.py、tests/test_mall_evaluation.py、pages/mall/EvaluationCenterPage.tsx、pages/mall/seller/EvaluationManagePage.tsx
- 修改：models.py、dao.py（EvaluationDAO）、schemas.py、router.py、service/short_transactions.py、service/__init__.py、lib/types.ts、mall.ts、sellerMall.ts、pages/mall/GoodsDetailPage.tsx、pages/mall/OrderDetailPage.tsx、components/mall/SellerLayout.tsx、components/mall/MallLayout.tsx、App.tsx

---

# F3 优惠券系统 实施计划（已完成）

> 目标：平台券/店铺券（满减/折扣）、领券中心、结算选券抵扣（防超发/防并发）、订单记录用券、我的优惠券、卖家/平台券管理、过期清理 worker。
> 2026-08-17 完成：mall_coupons/mall_user_coupons 表 + 订单 coupon_id/coupon_discount_fen 列（迁移 coupon_0006）、领券/用券/计算/管理/过期 worker 服务与路由（with_for_update 防超发）、MALL_COUPON_EXPIRE worker、test_mall_coupon.py 5 测试、前端领券中心（/mall/coupons）与卖家券管理（/mall/seller/coupons）与平台券管理（/mall/admin/coupons）、结算页选券抵扣。

> 目标：平台券/店铺券（满减/折扣）、领券中心、结算选券抵扣（防超发/防并发）、订单记录用券、我的优惠券、卖家/平台券管理、过期清理 worker。

## 一、数据模型（models.py + alembic 迁移 coupon_0006，≤16 字符）

### 新表 `mall_coupons`（CouponTemplate 模型）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| name | String(100) | 券名称 |
| type | SQLEnum(CouponType) | FIXED=满减 / DISCOUNT=折扣 |
| value_fen | BigInteger default 0 | 满减面额（分） |
| discount | Integer default 100 | 折扣（90=9 折，1-99） |
| min_amount_fen | BigInteger default 0 | 使用门槛（满 X 可用） |
| scope | SQLEnum(CouponScope) | PLATFORM / SHOP |
| shop_id | FK mall_shops.id nullable | 店铺券归属 |
| total_count | Integer default 0 | 发行量（0=不限） |
| received_count | Integer default 0 | 已领取数 |
| per_user_limit | Integer default 1 | 每人限领 |
| valid_from / valid_until | DateTime | 有效期 |
| status | SQLEnum(CouponStatus) | ACTIVE / PAUSED / EXPIRED |
| created_at / updated_at | DateTime | |

### 新表 `mall_user_coupons`（UserCoupon 模型）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| user_id | FK users.id | index |
| coupon_id | FK mall_coupons.id | |
| status | SQLEnum(UserCouponStatus) | UNUSED / USED / EXPIRED |
| order_no | String(32) nullable | 使用时关联订单 |
| received_at / used_at / expired_at | DateTime nullable | |
| unique (user_id, coupon_id) | | per_user_limit 按计数校验（默认 1） |

### mall_orders 增加字段（迁移中 add_column）
- `coupon_id: BigInteger nullable`（不设 FK，避免删除券模板影响订单）
- `coupon_discount_fen: BigInteger default 0`
- 计算：pay_amount_fen = goods_amount + freight - coupon_discount_fen（下限 0）

## 二、服务层（short_transactions.py）

### 买家
- `list_available_coupons(db, user_id, *, scope, shop_id, page, page_size)` — 领券中心：ACTIVE 且未过期且未领完（total_count=0 或 received_count<total_count）
- `receive_coupon(db, user_id, coupon_id)` — 锁模板行防超发（total_count 校验+received_count+1）；per_user_limit 校验（按 UserCoupon 计数）；创建 UserCoupon（expired_at=valid_until 快照）
- `list_my_coupons(db, user_id, *, status, page, page_size)` — 查询时惰性把已过期的 UNUSED 标记 EXPIRED
- `_validate_coupon(db, coupon, user_coupon, shop_id, goods_amount)` — 公共校验：状态 UNUSED、未过期、门槛、店铺范围匹配（券属于该店或平台券）
- `preview_order` 扩展：`coupon_id: int | None` 参数 → 校验可用券 → 计算 discount（满减=value_fen 取 min(门槛内金额)；折扣=round(goods_amount*(100-discount)/100)）→ 返回 coupon_discount_fen
- `create_order` 扩展：`coupon_id: int | None` → 同短事务内锁行校验 + 标记 UserCoupon USED（order_no/used_at）+ 计算 pay_amount
- 订单创建失败（异常回滚）时券自动恢复 UNUSED（同事务）

### 卖家/平台
- 卖家：`seller_create_coupon / seller_update_coupon / seller_list_coupons / seller_set_coupon_status`（店铺券 CRUD，scope 固定 SHOP；锁模板行更新）
- 平台：`admin_create_coupon / admin_update_coupon / admin_list_coupons / admin_set_coupon_status`（scope 可选 PLATFORM/SHOP；管理员可指定 shop_id 发店铺券）

### worker（long_tasks.py）
- `MALL_COUPON_EXPIRE = TaskDefinition("mall.coupon.expire", TaskQueue.BATCH, ...)` — 每日清理：把 valid_until < now 且 UNUSED 的 UserCoupon 置 EXPIRED；模板 valid_until < now 置 EXPIRED
- 注册到 features.py `_mall_tasks()` 与 conftest

## 三、Schema 与路由

### schemas.py
- `CouponTemplateCreateIn / CouponTemplateUpdateIn / CouponTemplateOut`
- `UserCouponOut`（含模板信息快照：name/type/value/discount/min_amount/scope/shop_name/valid_until）
- `CouponReceiveOut`
- OrderCreateIn/OrderPreviewOut/OrderOut 增加 coupon 相关字段；preview 请求体加 coupon_id

### 路由
买家（router）：
- GET /api/mall/coupons（领券中心，scope/shop_id 筛选）
- POST /api/mall/coupons/{coupon_id}/receive
- GET /api/mall/coupons/mine（status 筛选）
- preview：POST /api/mall/orders/preview 请求体加 coupon_id；create：POST /api/mall/orders 加 coupon_id
卖家（seller_router）：GET/POST/PUT /api/mall/seller/coupons、POST /api/mall/seller/coupons/{id}/status
管理员（admin_router）：GET/POST/PUT /api/mall/admin/coupons、POST /api/mall/admin/coupons/{id}/status（写 audit）

## 四、后端测试（tests/test_mall_coupon.py）

1. 领券：超发上限（received_count 锁行）、每人限领、过期券不可领
2. 满减/折扣计算正确（含门槛不满足、店铺范围不匹配拒绝）
3. 下单用券：pay_amount 扣减正确、券置 USED、订单详情带 coupon 信息
4. 并发防超发：两用户同时领最后一张只成功一个（锁行语义用 with_for_update 验证）
5. 券管理 CRUD + 状态上下架；卖家只能管本店券（404 校验）
6. worker 过期清理幂等

## 五、前端

- types.ts：MallCouponTemplate、MallUserCoupon、CouponType/Scope/Status 类型；MallOrder/MallOrderPreview 增加 coupon 字段
- lib/mall.ts：listAvailableCoupons / receiveCoupon / listMyCoupons；preview/create 请求带 coupon_id
- lib/sellerMall.ts：卖家券 CRUD；listAdminCoupons / adminCoupon CRUD
- `CheckoutPage.tsx`：优惠券选择区（可用券列表 Radio + 优惠金额展示，preview 带 coupon_id 重算）
- 新建 `pages/mall/CouponCenterPage.tsx`（/mall/coupons：领券中心 Tab + 我的优惠券 Tab）
- 新建 `pages/mall/seller/CouponManagePage.tsx`（/mall/seller/coupons：券模板 CRUD + 上下架）
- 新建 `pages/mall/admin/CouponAdminPage.tsx`（/mall/admin/coupons：平台券管理；App.tsx 注册 + 管理员入口）
- `MallLayout.tsx` 用户菜单加"领券中心"；`SellerLayout.tsx` 菜单加"优惠券"

## 六、验证与文件清单
- 测试 + make check + pnpm build + 本地库迁移 coupon_0006 验证（含 SQLite 订单表 add_column）
- 新增：alembic/versions/0006_coupon_tables.py、tests/test_mall_coupon.py、pages/mall/CouponCenterPage.tsx、pages/mall/seller/CouponManagePage.tsx、pages/mall/admin/CouponAdminPage.tsx
- 修改：models.py、dao.py（CouponTemplateDAO/UserCouponDAO）、schemas.py、router.py、service/short_transactions.py、service/long_tasks.py、service/__init__.py、platform/features.py、conftest.py、lib/types.ts、mall.ts、sellerMall.ts、pages/mall/CheckoutPage.tsx、components/mall/MallLayout.tsx、components/mall/SellerLayout.tsx、App.tsx

---

# F4 收藏/关注 + 浏览足迹 实施计划（已完成）

> 目标：商品收藏、店铺关注、浏览足迹；商品详情页收藏按钮；我的收藏/我的足迹页。
> 2026-08-17 完成：mall_favorites/mall_goods_footprints 表（迁移 fav_0007）、收藏增删幂等/列表快照/状态查询/足迹 upsert 服务与路由、test_mall_favorite.py 4 测试、前端商品详情收藏按钮+静默足迹、我的收藏（/mall/favorites）与浏览足迹（/mall/footprints）页、商城首页支持 shop_id 参数。

## 一、数据模型（models.py + alembic 迁移 fav_0007，≤16 字符）

### 新表 `mall_favorites`（Favorite 模型）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| user_id | FK users.id CASCADE | index |
| target_type | SQLEnum(FavoriteTargetType) | GOODS / SHOP |
| target_id | Integer | 商品或店铺 id |
| created_at | DateTime | |
| unique (user_id, target_type, target_id) | | 防重复收藏 |

### 新表 `mall_goods_footprints`（Footprint 模型）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| user_id | FK users.id CASCADE | index |
| goods_id | FK mall_goods.id CASCADE | |
| shop_id | FK mall_shops.id CASCADE | |
| viewed_at | DateTime | index |
| unique (user_id, goods_id) | | 每用户每商品保留最新一条（upsert） |

## 二、服务层（short_transactions.py）

- `add_favorite(db, user_id, *, target_type, target_id)` — 幂等（已存在直接返回）；校验目标存在（商品 ON / 店铺 APPROVED）
- `remove_favorite(db, user_id, *, target_type, target_id)` — 不存在不报错（幂等）
- `list_my_favorites(db, user_id, *, target_type, page, page_size)` — 返回带商品/店铺快照（商品：名称/主图/价格/状态；店铺：名称/头像）
- `is_favorited(db, user_id, *, target_type, target_id) -> bool`
- `record_footprint(db, user_id, *, goods_id)` — upsert：存在则更新 viewed_at，不存在则插入；触发列表查询时仅返回最近 50 条
- `list_my_footprints(db, user_id, page, page_size)` — 按 viewed_at 倒序，带商品快照

## 三、Schema 与路由

### schemas.py
- `FavoriteAddIn`（target_type, target_id）
- `FavoriteOut`（id, target_type, target_id, target_name, target_image, target_price_fen?, shop_id?, created_at）
- `FootprintOut`（goods_id, goods_name, goods_image, price_fen, shop_id, shop_name, viewed_at）

### 路由（router.py）
买家（router，均需登录）：
- POST /api/mall/favorites（收藏/关注）
- DELETE /api/mall/favorites（query: target_type, target_id；或 body——DELETE 用 query 更 RESTful，沿用项目风格用 query）
- GET /api/mall/favorites（type 筛选 + 分页）
- GET /api/mall/favorites/status?target_type=&target_id=（批量查收藏状态，detail 页用）
- POST /api/mall/footprints（浏览记录）
- GET /api/mall/footprints（分页）
- GET /api/mall/goods/{goods_id}/detail 保持公开（收藏状态由前端单独查）

## 四、后端测试（tests/test_mall_favorite.py）

1. 收藏商品/店铺、重复收藏幂等、取消收藏
2. 收藏列表带快照；未登录 401
3. 足迹 upsert（重复浏览只保留一条且时间更新）、列表倒序
4. 权限/校验：收藏不存在的商品 404
5. 商品详情页收藏状态接口

## 五、前端

- types.ts：MallFavorite、MallFootprint、FavoriteTargetType
- lib/mall.ts：addFavorite / removeFavorite / listMyFavorites / getFavoriteStatus / recordFootprint / listMyFootprints
- `GoodsDetailPage.tsx`：收藏按钮（心形，登录后可用，点击切换状态）+ 浏览时调用 recordFootprint（登录后静默）
- 新建 `pages/mall/FavoritesPage.tsx`（/mall/favorites：Tab 商品/店铺，取消收藏）
- 新建 `pages/mall/FootprintsPage.tsx`（/mall/footprints：足迹列表，点击跳详情）
- `MallLayout.tsx` 用户菜单加"我的收藏/我的足迹"；`App.tsx` 注册路由

## 六、验证与文件清单
- 测试 + make check + pnpm build + 本地库迁移 fav_0007 验证
- 新增：alembic/versions/0007_favorite_tables.py、tests/test_mall_favorite.py、pages/mall/FavoritesPage.tsx、pages/mall/FootprintsPage.tsx
- 修改：models.py、dao.py（FavoriteDAO/FootprintDAO）、schemas.py、router.py、service/short_transactions.py、service/__init__.py、lib/types.ts、mall.ts、pages/mall/GoodsDetailPage.tsx、components/mall/MallLayout.tsx、App.tsx

---

## 通用实施注意事项（AGENTS.md 约束）

- 后端分层参照 `src/server/example_module`；创建任务与持久化入队处于同一短事务；worker 任务注册到 `features.py _mall_tasks()` 与 `conftest.py`
- 新增表统一走 alembic 迁移，revision ≤16 字符；模型导入走 `database.py import_all_models()`（mall.models 已被导入）
- 金额一律分 `*_fen` BigInteger；库存/券/退款等并发敏感操作沿用 `with_for_update()` 锁行；资金相关逻辑幂等
- 每完成一个 F 做一轮 `make check` + `pnpm build`
- SQLite 迁移注意：枚举扩展/列变更需处理索引与 CHECK 约束（参照 0004 的删索引-重建模式）；PG 用 ALTER TYPE ADD VALUE
