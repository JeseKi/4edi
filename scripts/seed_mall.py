#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商城种子数据脚本

用法：
- python scripts/seed_mall.py          # 幂等填充分类、演示店铺与商品
- python scripts/seed_mall.py --reset  # 先清空商城数据再填充

前置条件：数据库已完成 Alembic 迁移。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from typing import TypedDict

from sqlalchemy import text

from src.server.auth.dependencies.current_user import AuthenticatedPrincipal
from src.server.auth.schemas import UserRole
from src.server.database import run_in_new_session
from src.server.mall.dao import AddressDAO, CategoryDAO, GoodsDAO, ShopDAO, WalletDAO
from src.server.mall.models import GoodsStatus, ShopStatus
from src.server.mall.service import short_transactions as service

SELLER_USERNAME = "seller"
SELLER_PASSWORD = "seller123"
SELLER_EMAIL = "seller@example.com"
SELLER_PHONE = "13800000001"

BUYER_USERNAME = "buyer"
BUYER_PASSWORD = "buyer123"
BUYER_EMAIL = "buyer@example.com"
BUYER_PHONE = "13800000002"

SHOP_NAME = "示例优选旗舰店"

CATEGORIES = [
    ("数码家电", None, 0),
    ("手机通讯", "数码家电", 1),
    ("电脑办公", "数码家电", 2),
    ("服装鞋包", None, 1),
    ("男装", "服装鞋包", 1),
    ("女装", "服装鞋包", 2),
    ("运动户外", None, 2),
    ("运动鞋", "运动户外", 1),
    ("食品生鲜", None, 3),
    ("休闲零食", "食品生鲜", 1),
]

class _GoodsSeed(TypedDict):
    name: str
    category: str
    image: str
    price: int
    original: int
    stock: int
    detail: str
    skus: list[dict]


GOODS: list[_GoodsSeed] = [
    {
        "category": "手机通讯",
        "name": "无线蓝牙耳机 主动降噪 长续航",
        "image": "/mall/goods-1.svg",
        "price": 29900,
        "original": 39900,
        "stock": 200,
        "detail": "支持主动降噪，30 小时综合续航，蓝牙 5.3 稳定连接，半入耳式设计久戴不累。",
        "skus": [{"specs": {"颜色": "白色"}, "price_fen": 29900, "stock": 100},
                 {"specs": {"颜色": "黑色"}, "price_fen": 29900, "stock": 100}],
    },
    {
        "category": "手机通讯",
        "name": "智能手表 血氧心率监测 14 天长续航",
        "image": "/mall/goods-2.svg",
        "price": 59900,
        "original": 79900,
        "stock": 150,
        "detail": "1.43 英寸 AMOLED 高清屏，支持血氧、心率、睡眠监测，14 天超长续航。",
        "skus": [{"specs": {"颜色": "曜石黑"}, "price_fen": 59900, "stock": 150}],
    },
    {
        "category": "休闲零食",
        "name": "316L 不锈钢保温杯 500ml",
        "image": "/mall/goods-3.svg",
        "price": 8900,
        "original": 12900,
        "stock": 300,
        "detail": "食品级 316L 不锈钢内胆，24 小时保温，一键弹盖单手可开，密封防漏。",
        "skus": [{"specs": {"颜色": "樱花粉"}, "price_fen": 8900, "stock": 150},
                 {"specs": {"颜色": "星空蓝"}, "price_fen": 8900, "stock": 150}],
    },
    {
        "category": "运动鞋",
        "name": "轻便透气跑步鞋 缓震回弹",
        "image": "/mall/goods-4.svg",
        "price": 19900,
        "original": 26900,
        "stock": 120,
        "detail": "一体织透气鞋面，高弹缓震中底，轻量化设计，适合日常跑步与通勤。",
        "skus": [{"specs": {"尺码": "40"}, "price_fen": 19900, "stock": 40},
                 {"specs": {"尺码": "41"}, "price_fen": 19900, "stock": 40},
                 {"specs": {"尺码": "42"}, "price_fen": 19900, "stock": 40}],
    },
]


def _ensure_user(db, *, username: str, password: str, email: str, phone: str, role: str):
    from src.server.auth.dao import UserDAO
    from src.server.auth.models import User

    user = UserDAO(db).get_by_username(username)
    if user is None:
        user = User(
            username=username,
            email=email,
            phone=phone,
            name=username,
            role=UserRole(role),
        )
        user.set_password(password)
        db.add(user)
        db.flush()
    return user


def _seed(db) -> None:
    category_dao = CategoryDAO(db)
    category_map: dict[str, int] = {}
    for name, parent_name, sort in CATEGORIES:
        if name in category_map:
            continue
        parent_id = category_map.get(parent_name) if parent_name else None
        category = category_dao.create(
            name=name, parent_id=parent_id, sort=sort, icon=None
        )
        category_map[name] = category.id

    seller = _ensure_user(
        db,
        username=SELLER_USERNAME,
        password=SELLER_PASSWORD,
        email=SELLER_EMAIL,
        phone=SELLER_PHONE,
        role="user",
    )
    shop_dao = ShopDAO(db)
    shop = shop_dao.get_by_owner(seller.id)
    if shop is None:
        shop = shop_dao.create(
            owner_user_id=seller.id,
            name=SHOP_NAME,
            description="官方示例店铺：主营数码、服饰与食品，支持全场包邮。",
            avatar="/mall/shop-avatar.svg",
        )
    if shop.status != ShopStatus.APPROVED:
        shop.status = ShopStatus.APPROVED
        shop.approved_at = shop.approved_at or service._utcnow()
        wallet = WalletDAO(db).get_or_create(shop.id)
        from src.server.mall.config import mall_config

        shop.deposit_fen = mall_config.default_deposit_fen
        wallet.deposit_fen = mall_config.default_deposit_fen

    principal = AuthenticatedPrincipal(
        user_id=seller.id,
        username=SELLER_USERNAME,
        role=UserRole.USER.value,
        email=SELLER_EMAIL,
        two_factor_enabled=False,
    )
    goods_dao = GoodsDAO(db)
    for index, item in enumerate(GOODS, start=1):
        exists = goods_dao.list_for_shop(
            shop_id=shop.id, status=None, keyword=item["name"], page=1, page_size=10
        )[0]
        if exists:
            continue
        category_id = category_map.get(item["category"])
        goods = service.create_goods(
            db,
            principal,
            {
                "category_id": category_id,
                "name": item["name"],
                "main_image": item["image"],
                "images": [item["image"]],
                "detail": item["detail"],
                "original_price_fen": item["original"],
                "skus": item["skus"],
            },
        )
        goods.status = GoodsStatus.ON
        goods.sales = index * 37
        print(f"  商品已创建：{item['name']}")

    buyer = _ensure_user(
        db,
        username=BUYER_USERNAME,
        password=BUYER_PASSWORD,
        email=BUYER_EMAIL,
        phone=BUYER_PHONE,
        role="user",
    )

    addresses = AddressDAO(db).list_for_user(buyer.id)
    if not addresses:
        AddressDAO(db).create(
            buyer.id,
            receiver="示例买家",
            phone=BUYER_PHONE,
            province="广东省",
            city="深圳市",
            district="南山区",
            detail="科技园示例路 1 号",
            is_default=True,
        )
        print("  示例买家与默认收货地址已创建")

    print("种子数据就绪。")
    print(f"  卖家账号：{SELLER_USERNAME} / {SELLER_PASSWORD}（可申请开店或直接登录查看店铺）")
    print(f"  买家账号：{BUYER_USERNAME} / {BUYER_PASSWORD}")
    print("  管理员账号：admin / admin123（可在管理后台审核店铺）")


def _reset(db) -> None:
    tables = [
        "mall_chat_messages",
        "mall_payments",
        "mall_withdraw_requests",
        "mall_wallet_ledger",
        "mall_wallets",
        "mall_order_logs",
        "mall_order_items",
        "mall_orders",
        "mall_addresses",
        "mall_cart_items",
        "mall_goods_skus",
        "mall_goods",
        "mall_shops",
        "mall_categories",
    ]
    for table in tables:
        db.execute(text(f'DELETE FROM "{table}"'))
    print("已清空商城数据。")


def main() -> None:
    parser = argparse.ArgumentParser(description="商城种子数据")
    parser.add_argument("--reset", action="store_true", help="先清空商城数据再填充")
    args = parser.parse_args()

    def _job(db) -> None:
        if args.reset:
            _reset(db)
        _seed(db)

    run_in_new_session(_job)


if __name__ == "__main__":
    main()
