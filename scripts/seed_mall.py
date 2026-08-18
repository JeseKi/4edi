#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商城演示数据 Seed（可重复执行）。

运行：
    .venv/bin/python scripts/seed_mall.py
    .venv/bin/python scripts/seed_mall.py --reset
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from typing import TypedDict

from sqlalchemy import text

from src.server.auth.dao import UserDAO
from src.server.auth.dependencies.current_user import AuthenticatedPrincipal
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.database import run_in_new_session
from src.server.mall.config import mall_config
from src.server.mall.dao import (
    AddressDAO,
    CategoryDAO,
    EvaluationDAO,
    GoodsDAO,
    GoodsSkuDAO,
    OrderDAO,
    OrderItemDAO,
    ShopDAO,
    WalletDAO,
)
from src.server.mall.models import Goods, GoodsStatus, OrderStatus, ShopStatus
from src.server.mall.service import short_transactions as service


class GoodsSeed(TypedDict):
    slug: str
    category: str
    name: str
    fallback_image: str
    original_price_fen: int
    detail: str
    skus: list[dict]


CATEGORIES = [
    ("数码家电", None, 0),
    ("手机通讯", "数码家电", 1),
    ("电脑办公", "数码家电", 2),
    ("服装鞋包", None, 1),
    ("男装", "服装鞋包", 1),
    ("女装", "服装鞋包", 2),
    ("运动户外", None, 2),
    ("运动鞋", "运动户外", 1),
    ("户外装备", "运动户外", 2),
    ("食品生鲜", None, 3),
    ("休闲零食", "食品生鲜", 1),
    ("家居日用", None, 4),
    ("杯壶水具", "家居日用", 1),
]


GOODS: list[GoodsSeed] = [
    {
        "slug": "wireless-earbuds",
        "category": "手机通讯",
        "name": "AirTone Pro 真无线蓝牙耳机 主动降噪 30H 续航",
        "fallback_image": "/mall/goods-1.svg",
        "original_price_fen": 39900,
        "detail": (
            "面向通勤与日常使用的真无线降噪耳机。支持自适应主动降噪、通透模式和双麦克风通话降噪；"
            "单次播放约 7 小时，配合充电盒综合续航约 30 小时。蓝牙 5.3 支持双设备快速切换，"
            "耳机具备 IP54 日常防尘防泼溅能力。包装内含耳机、充电盒、S/M/L 三组耳塞和 USB-C 充电线。"
        ),
        "skus": [
            {"sku_code": "AT-PRO-IVORY", "specs": {"颜色": "云岩白"}, "price_fen": 29900, "stock": 90},
            {"sku_code": "AT-PRO-BLACK", "specs": {"颜色": "曜石黑"}, "price_fen": 29900, "stock": 80},
            {"sku_code": "AT-PRO-BLUE", "specs": {"颜色": "雾霾蓝"}, "price_fen": 31900, "stock": 50},
        ],
    },
    {
        "slug": "smart-watch",
        "category": "手机通讯",
        "name": "Pulse S2 智能手表 AMOLED 屏 心率血氧监测 14 天续航",
        "fallback_image": "/mall/goods-2.svg",
        "original_price_fen": 79900,
        "detail": (
            "1.43 英寸 AMOLED 高清圆屏智能手表，支持全天心率、血氧、睡眠与压力趋势记录，并提供 100+ 种运动模式。"
            "典型使用场景下续航最长约 14 天，开启常亮显示后约 6 天；5ATM 防水，可覆盖洗手、雨天与泳池训练。"
            "支持消息提醒、蓝牙通话、音乐控制、闹钟与久坐提醒。健康数据仅用于日常趋势参考，不替代医疗设备。"
        ),
        "skus": [
            {"sku_code": "PS2-BLACK-SIL", "specs": {"表壳": "曜石黑", "表带": "硅胶"}, "price_fen": 59900, "stock": 60},
            {"sku_code": "PS2-SILVER-SIL", "specs": {"表壳": "星辉银", "表带": "硅胶"}, "price_fen": 61900, "stock": 50},
            {"sku_code": "PS2-SILVER-LEA", "specs": {"表壳": "星辉银", "表带": "皮革"}, "price_fen": 66900, "stock": 40},
        ],
    },
    {
        "slug": "mechanical-keyboard",
        "category": "电脑办公",
        "name": "KeyFlow K75 三模机械键盘 75% 配列 热插拔",
        "fallback_image": "/mall/goods-1.svg",
        "original_price_fen": 52900,
        "detail": (
            "75% 紧凑配列机械键盘，保留独立方向键与常用功能区。支持 2.4G、蓝牙和 USB-C 有线三种连接方式，"
            "可在电脑、平板与手机之间切换。全键热插拔轴座兼容常见三脚/五脚机械轴，内置多层消音结构，"
            "适合办公与轻度游戏。标配双色 PBT 键帽、拔键器/拔轴器和 USB-C 数据线。"
        ),
        "skus": [
            {"sku_code": "K75-WHITE-LINEAR", "specs": {"配色": "雾白", "轴体": "线性轴"}, "price_fen": 39900, "stock": 45},
            {"sku_code": "K75-WHITE-TACTILE", "specs": {"配色": "雾白", "轴体": "段落轴"}, "price_fen": 41900, "stock": 35},
            {"sku_code": "K75-GRAY-LINEAR", "specs": {"配色": "深空灰", "轴体": "线性轴"}, "price_fen": 39900, "stock": 40},
        ],
    },
    {
        "slug": "laptop-stand",
        "category": "电脑办公",
        "name": "FoldStand X 铝合金笔记本支架 六档可调 可折叠",
        "fallback_image": "/mall/goods-2.svg",
        "original_price_fen": 15900,
        "detail": (
            "适配约 11–17 英寸笔记本电脑与平板设备的桌面支架。六档高度/角度可调，主体采用铝合金结构，"
            "承托面与底部设有防滑硅胶垫。开放式结构有利于设备底部通风，折叠后便于放入电脑包。"
            "长时间抬高屏幕办公时建议搭配外接键鼠使用。"
        ),
        "skus": [
            {"sku_code": "FSX-SILVER", "specs": {"颜色": "银色"}, "price_fen": 10900, "stock": 120},
            {"sku_code": "FSX-GRAY", "specs": {"颜色": "深空灰"}, "price_fen": 11900, "stock": 100},
        ],
    },
    {
        "slug": "vacuum-bottle",
        "category": "杯壶水具",
        "name": "ThermoGo 316L 不锈钢保温杯 500ml 一键弹盖",
        "fallback_image": "/mall/goods-3.svg",
        "original_price_fen": 12900,
        "detail": (
            "500ml 日常随行保温杯，内胆采用 316L 不锈钢，杯身为双层真空结构。杯盖带安全锁与一键弹盖，"
            "通勤途中可单手开启；可拆卸密封圈便于清洁。杯口圆润，也可放入常见车载杯架。"
            "首次使用建议用温水和中性清洁剂充分清洗，不建议盛放碳酸饮料或长时间存放乳制品。"
        ),
        "skus": [
            {"sku_code": "TG500-PINK", "specs": {"颜色": "樱花粉"}, "price_fen": 8900, "stock": 100},
            {"sku_code": "TG500-BLUE", "specs": {"颜色": "星空蓝"}, "price_fen": 8900, "stock": 100},
            {"sku_code": "TG500-WHITE", "specs": {"颜色": "珍珠白"}, "price_fen": 8900, "stock": 100},
        ],
    },
    {
        "slug": "running-shoes",
        "category": "运动鞋",
        "name": "CloudRun 3 轻量缓震跑步鞋 透气回弹",
        "fallback_image": "/mall/goods-4.svg",
        "original_price_fen": 26900,
        "detail": (
            "面向日常慢跑、健走与通勤的轻量跑鞋。一体织网布鞋面增强前掌透气性，中底采用高回弹发泡材料，"
            "后跟区域增加稳定包裹；橡胶耐磨片覆盖主要落地区域。常规楦型，脚背偏高或喜欢宽松脚感的用户建议大半码选择。"
            "鞋垫可拆洗，清洁时建议冷水手洗并自然阴干。"
        ),
        "skus": [
            {"sku_code": "CR3-BW-40", "specs": {"配色": "黑白", "尺码": "40"}, "price_fen": 19900, "stock": 30},
            {"sku_code": "CR3-BW-41", "specs": {"配色": "黑白", "尺码": "41"}, "price_fen": 19900, "stock": 35},
            {"sku_code": "CR3-BW-42", "specs": {"配色": "黑白", "尺码": "42"}, "price_fen": 19900, "stock": 35},
            {"sku_code": "CR3-GRAY-42", "specs": {"配色": "雾灰", "尺码": "42"}, "price_fen": 20900, "stock": 20},
        ],
    },
    {
        "slug": "mens-overshirt",
        "category": "男装",
        "name": "Urban Field 男士轻薄工装衬衫外套 宽松版型",
        "fallback_image": "/mall/goods-3.svg",
        "original_price_fen": 23900,
        "detail": (
            "适合春秋叠穿的轻薄工装衬衫外套，采用有挺度但不过分厚重的棉混纺面料。宽松直筒版型，"
            "前胸双口袋并使用简洁按扣，可作为衬衫单穿或搭配 T 恤作外层。建议深浅色分开洗涤、反面低温清洗，"
            "避免长时间浸泡。尺码为宽松设计，喜欢合身效果可按平时尺码小一码选择。"
        ),
        "skus": [
            {"sku_code": "UF-OLIVE-M", "specs": {"颜色": "橄榄绿", "尺码": "M"}, "price_fen": 16900, "stock": 35},
            {"sku_code": "UF-OLIVE-L", "specs": {"颜色": "橄榄绿", "尺码": "L"}, "price_fen": 16900, "stock": 40},
            {"sku_code": "UF-KHAKI-M", "specs": {"颜色": "浅卡其", "尺码": "M"}, "price_fen": 16900, "stock": 30},
            {"sku_code": "UF-KHAKI-L", "specs": {"颜色": "浅卡其", "尺码": "L"}, "price_fen": 16900, "stock": 35},
        ],
    },
    {
        "slug": "mixed-nuts",
        "category": "休闲零食",
        "name": "每日坚果混合装 25g×20 袋 原味独立包装",
        "fallback_image": "/mall/goods-4.svg",
        "original_price_fen": 13900,
        "detail": (
            "独立小包装混合坚果，共 20 袋，每袋约 25g。搭配巴旦木、腰果、核桃仁与蔓越莓干，采用原味轻烘焙思路，"
            "适合作为办公室或出行零食。配料与实际批次以包装标签为准；坚果属于常见致敏原，对坚果过敏者请勿食用。"
            "开袋后建议一次食用完毕，并置于阴凉干燥处保存。"
        ),
        "skus": [
            {"sku_code": "NUTS-20", "specs": {"规格": "25g×20 袋"}, "price_fen": 9900, "stock": 160},
            {"sku_code": "NUTS-30", "specs": {"规格": "25g×30 袋"}, "price_fen": 13900, "stock": 120},
        ],
    },
    {
        "slug": "womens-cardigan",
        "category": "女装",
        "name": "SoftLine 女士针织开衫 V 领宽松通勤外套",
        "fallback_image": "/mall/goods-1.svg",
        "original_price_fen": 26900,
        "detail": (
            "适合春秋与空调房叠穿的轻薄针织开衫，采用柔软混纺纱线，触感细腻且具有一定垂坠感。"
            "V 领单排扣设计便于搭配衬衫、吊带或基础 T 恤，落肩宽松版型对日常通勤和休闲穿搭都较友好。"
            "建议使用洗衣袋轻柔机洗或冷水手洗，平铺晾干，避免高温烘干导致织物变形。"
        ),
        "skus": [
            {"sku_code": "SL-CARD-OAT-S", "specs": {"颜色": "燕麦色", "尺码": "S"}, "price_fen": 18900, "stock": 28},
            {"sku_code": "SL-CARD-OAT-M", "specs": {"颜色": "燕麦色", "尺码": "M"}, "price_fen": 18900, "stock": 36},
            {"sku_code": "SL-CARD-GRAY-S", "specs": {"颜色": "烟灰色", "尺码": "S"}, "price_fen": 19900, "stock": 24},
            {"sku_code": "SL-CARD-GRAY-M", "specs": {"颜色": "烟灰色", "尺码": "M"}, "price_fen": 19900, "stock": 32},
        ],
    },
    {
        "slug": "camping-chair",
        "category": "户外装备",
        "name": "TrailSeat 便携月亮椅 铝合金折叠露营椅",
        "fallback_image": "/mall/goods-2.svg",
        "original_price_fen": 21900,
        "detail": (
            "面向露营、野餐、钓鱼与户外观赛场景的便携折叠椅。支架采用轻量铝合金结构，椅面使用耐磨牛津布，"
            "包裹式月亮椅面兼顾支撑与放松感。折叠后可收纳进随附束口袋，便于放入后备箱或大型户外背包。"
            "建议在平整坚实地面使用，并在每次展开后确认所有连接点已经完全就位。"
        ),
        "skus": [
            {"sku_code": "TS-CHAIR-KHAKI", "specs": {"颜色": "沙丘卡其"}, "price_fen": 15900, "stock": 55},
            {"sku_code": "TS-CHAIR-GREEN", "specs": {"颜色": "森林绿"}, "price_fen": 15900, "stock": 50},
            {"sku_code": "TS-CHAIR-BLACK", "specs": {"颜色": "曜石黑"}, "price_fen": 16900, "stock": 45},
        ],
    },
    {
        "slug": "commuter-backpack",
        "category": "户外装备",
        "name": "CityTrail 22L 城市通勤双肩包 16 英寸电脑仓",
        "fallback_image": "/mall/goods-3.svg",
        "original_price_fen": 32900,
        "detail": (
            "22L 中等容量通勤双肩包，主仓可容纳日常衣物、书本和随身杂物，独立加厚电脑仓适配多数 16 英寸以内笔记本。"
            "背部采用分区透气网垫与弧形肩带，顶部设快取小袋，两侧可放水杯或折叠伞。表层面料提供日常轻度防泼水能力，"
            "适合城市通勤、短途出行与周末轻户外，不建议长时间暴露于大雨环境。"
        ),
        "skus": [
            {"sku_code": "CT22-GRAY", "specs": {"颜色": "石墨灰"}, "price_fen": 22900, "stock": 65},
            {"sku_code": "CT22-BLACK", "specs": {"颜色": "曜石黑"}, "price_fen": 22900, "stock": 70},
            {"sku_code": "CT22-GREEN", "specs": {"颜色": "松针绿"}, "price_fen": 23900, "stock": 45},
        ],
    },
    {
        "slug": "desk-lamp",
        "category": "电脑办公",
        "name": "HaloDesk Pro LED 护眼台灯 无级调光调色",
        "fallback_image": "/mall/goods-4.svg",
        "original_price_fen": 29900,
        "detail": (
            "适合书桌、宿舍和家庭办公场景的 LED 台灯。灯头采用宽幅发光面，支持亮度无级调节与多档色温切换，"
            "可根据阅读、书写和屏幕办公场景调整光线。多关节灯臂支持俯仰与高度调节，底座保留常用触控操作区。"
            "产品采用 USB-C 供电，建议搭配符合规格的正规电源适配器使用；长时间阅读仍应注意环境整体照明与用眼休息。"
        ),
        "skus": [
            {"sku_code": "HDP-WHITE", "specs": {"颜色": "暖白"}, "price_fen": 21900, "stock": 80},
            {"sku_code": "HDP-GRAY", "specs": {"颜色": "深空灰"}, "price_fen": 22900, "stock": 70},
        ],
    },
]


SELLER_USERNAME = "seller"
SELLER_PASSWORD = "seller123"
SELLER_EMAIL = "seller@example.com"
SELLER_PHONE = "13800000001"

BUYER_USERNAME = "buyer"
BUYER_PASSWORD = "buyer123"
BUYER_EMAIL = "buyer@example.com"
BUYER_PHONE = "13800000002"

SHOP_NAME = "示例优选旗舰店"

ASSET_URLS: dict[str, list[str]] = {
    "mechanical-keyboard": ["https://fstc.kispace.cn/i/1e33eb265a170d578076da3fe80411b1.webp"],
    "running-shoes": ["https://fstc.kispace.cn/i/0c3381c8bd4fb92c86140e52914f3cff.webp"],
    "mixed-nuts": ["https://fstc.kispace.cn/i/048da7cfa11df26648773a77a07e86a9.webp"],
    "mens-overshirt": ["https://fstc.kispace.cn/i/2187e6b1f57ea24941264fa4e1e432ac.webp"],
    "camping-chair": ["https://fstc.kispace.cn/i/9bc120ffb33d52929487b6f8b42973a7.webp"],
    "commuter-backpack": ["https://fstc.kispace.cn/i/1316d4890c8d3e1cb35c09d98f1760bb.webp"],
    "wireless-earbuds": ["https://fstc.kispace.cn/i/71bf95293f6fc9eaeb152d27d5d8bf3b.webp"],
    "vacuum-bottle": ["https://fstc.kispace.cn/i/1905b0b11c9859f0eb838c9b4a911c25.webp"],
    "smart-watch": ["https://fstc.kispace.cn/i/5c65c0e113fd2c4668d864d2a56ff8d8.webp"],
    "laptop-stand": ["https://fstc.kispace.cn/i/cc89b971fde5da1bc473c6e9c8a02462.webp"],
    "womens-cardigan": ["https://fstc.kispace.cn/i/97113047d38e9fcc55902b25513793c5.webp"],
    "desk-lamp": ["https://fstc.kispace.cn/i/c85979cca46e69c6bb7640546fb8fe88.webp"],
}

# 旧版 Seed 使用过的名称。优先复用这些记录，避免完整 Seed 与旧商品并存。
LEGACY_GOODS_NAMES: dict[str, tuple[str, ...]] = {
    "wireless-earbuds": ("无线蓝牙耳机 主动降噪 长续航",),
    "smart-watch": ("智能手表 血氧心率监测 14 天长续航",),
    "vacuum-bottle": ("316L 不锈钢保温杯 500ml",),
    "running-shoes": ("轻便透气跑步鞋 缓震回弹",),
}


def _ensure_user(
    db,
    *,
    username: str,
    password: str,
    email: str,
    phone: str,
    role: str,
) -> User:
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


def _ensure_categories(db) -> dict[str, int]:
    dao = CategoryDAO(db)
    category_map: dict[str, int] = {}

    for name, parent_name, sort in CATEGORIES:
        parent_id = category_map.get(parent_name) if parent_name else None
        existing = next(
            (
                category
                for category in dao.list_all()
                if category.name == name and category.parent_id == parent_id
            ),
            None,
        )
        if existing is None:
            existing = dao.create(
                name=name,
                parent_id=parent_id,
                sort=sort,
                icon=None,
            )
        else:
            existing.sort = sort
        category_map[name] = existing.id

    return category_map


def _ensure_shop(db, seller: User):
    dao = ShopDAO(db)
    shop = dao.get_by_owner(seller.id)
    description = "官方演示店铺：覆盖数码、服饰、运动、食品与日用商品，全部为测试数据。"
    if shop is None:
        shop = dao.create(
            owner_user_id=seller.id,
            name=SHOP_NAME,
            description=description,
            avatar="/mall/shop-avatar.svg",
        )
    else:
        shop.name = SHOP_NAME
        shop.description = description
        shop.avatar = "/mall/shop-avatar.svg"

    if shop.status != ShopStatus.APPROVED:
        shop.status = ShopStatus.APPROVED
        shop.approved_at = shop.approved_at or service._utcnow()

    wallet = WalletDAO(db).get_or_create(shop.id)
    shop.deposit_fen = mall_config.default_deposit_fen
    wallet.deposit_fen = mall_config.default_deposit_fen
    return shop


def _principal_for_seller(seller: User) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=seller.id,
        username=SELLER_USERNAME,
        role=UserRole.USER.value,
        email=SELLER_EMAIL,
        two_factor_enabled=False,
    )


def _goods_payload(
    item: GoodsSeed,
    category_map: dict[str, int],
    assets: dict[str, list[str]],
) -> dict:
    images = assets.get(item["slug"]) or [item["fallback_image"]]
    return {
        "category_id": category_map[item["category"]],
        "name": item["name"],
        "main_image": images[0],
        "images": images,
        "detail": item["detail"],
        "original_price_fen": item["original_price_fen"],
        "skus": item["skus"],
    }


def _find_seed_goods(goods_dao: GoodsDAO, *, shop_id: int, item: GoodsSeed):
    names = (*LEGACY_GOODS_NAMES.get(item["slug"], ()), item["name"])
    for name in names:
        candidates = goods_dao.list_for_shop(
            shop_id=shop_id,
            status=None,
            keyword=name,
            page=1,
            page_size=50,
        )[0]
        existing = next((goods for goods in candidates if goods.name == name), None)
        if existing is not None:
            return existing
    return None


def _seed_goods(
    db, *, seller: User, shop_id: int, category_map: dict[str, int], assets: dict[str, list[str]]
) -> list[Goods]:
    principal = _principal_for_seller(seller)
    goods_dao = GoodsDAO(db)
    seeded_goods: list[Goods] = []
    seeded_goods_ids: set[int] = set()

    for index, item in enumerate(GOODS, start=1):
        payload = _goods_payload(item, category_map, assets)
        existing = _find_seed_goods(goods_dao, shop_id=shop_id, item=item)
        if existing is None:
            goods = service.create_goods(db, principal, payload)
            action = "创建"
        else:
            goods = service.update_goods(db, principal, existing.id, payload)
            action = "更新"

        goods.status = GoodsStatus.ON
        goods.sales = max(goods.sales, index * 37)
        seeded_goods.append(goods)
        seeded_goods_ids.add(goods.id)
        print(f"  商品已{action}：{goods.name}（{len(payload['images'])} 张图片）")

    # 删除本脚本早先错误创建的同名重复演示商品。只作用于示例店铺，且仅清理目录中的精确名称。
    for item in GOODS:
        duplicates = goods_dao.list_for_shop(
            shop_id=shop_id,
            status=None,
            keyword=item["name"],
            page=1,
            page_size=50,
        )[0]
        for goods in duplicates:
            if goods.name == item["name"] and goods.id not in seeded_goods_ids:
                service.delete_goods(db, principal, goods.id)
                print(f"  已清理重复演示商品：{goods.name}")

    return seeded_goods


def _ensure_buyer(db) -> User:
    buyer = _ensure_user(
        db,
        username=BUYER_USERNAME,
        password=BUYER_PASSWORD,
        email=BUYER_EMAIL,
        phone=BUYER_PHONE,
        role="user",
    )
    if not AddressDAO(db).list_for_user(buyer.id):
        AddressDAO(db).create(
            buyer.id,
            receiver="示例买家",
            phone=BUYER_PHONE,
            province="浙江省",
            city="杭州市",
            district="西湖区",
            detail="文三路示例园区 1 号",
            is_default=True,
        )
        print("  示例买家与默认收货地址已创建")
    return buyer


def _seed_evaluations(
    db,
    *,
    buyer: User,
    shop,
    goods_list: list[Goods],
) -> None:
    """为演示商品生成已完成订单与评价数据。"""
    if not goods_list:
        return

    sku_dao = GoodsSkuDAO(db)
    order_dao = OrderDAO(db)
    item_dao = OrderItemDAO(db)
    eval_dao = EvaluationDAO(db)

    existing = sum(
        eval_dao.list_by_goods(goods.id, page=1, page_size=1)[1] for goods in goods_list
    )
    if existing:
        print("  评价数据已存在，跳过")
        return

    review_templates: list[dict[str, int | str]] = [
        {"rating": 5, "content": "质量很好，物流也很快，非常满意！"},
        {"rating": 5, "content": "性价比很高，包装严实，会回购。"},
        {"rating": 4, "content": "商品符合描述，做工不错，物流速度一般。"},
        {"rating": 5, "content": "物美价廉，卖家服务态度也很好。"},
        {"rating": 4, "content": "使用了一段时间，整体体验不错，推荐。"},
        {"rating": 5, "content": "发货速度很快，第二天就到了，好评！"},
        {"rating": 3, "content": "质量还可以，就是颜色和图片有点色差。"},
        {"rating": 5, "content": "超出预期，功能很实用，值得信赖。"},
        {"rating": 4, "content": "整体满意，包装可以再厚实一点。"},
        {"rating": 5, "content": "第二次购买了，家里人都很满意。"},
        {"rating": 4, "content": "不错的产品，客服回复也很及时。"},
        {"rating": 5, "content": "非常喜欢，会推荐给朋友。"},
    ]
    seller_replies: list[str | None] = [
        "感谢您的认可，我们会继续努力！",
        "亲的好评是我们最大的动力，欢迎再次光临！",
        None,
        "谢谢支持，祝您生活愉快！",
    ]

    now = datetime.now(timezone.utc)
    created_count = 0

    for goods in goods_list:
        skus = sku_dao.list_by_goods(goods.id)
        if not skus:
            continue
        sku = skus[0]
        for i in range(2):
            template = review_templates[(goods.id + i) % len(review_templates)]
            rating = int(template["rating"])
            content = str(template["content"])
            order = order_dao.create(
                order_no=service._gen_business_no("M"),
                buyer_id=buyer.id,
                shop_id=shop.id,
                goods_amount_fen=sku.price_fen,
                freight_fen=0,
                pay_amount_fen=sku.price_fen,
                receiver_name="示例买家",
                receiver_phone=BUYER_PHONE,
                receiver_address="浙江省杭州市西湖区文三路示例园区 1 号",
                remark=None,
            )
            order.status = OrderStatus.COMPLETED
            order.completed_at = now

            item = item_dao.create_many(
                order_id=order.id,
                goods_id=goods.id,
                sku_id=sku.id,
                goods_name=goods.name,
                goods_image=goods.main_image,
                sku_specs=sku.specs,
                unit_price_fen=sku.price_fen,
                quantity=1,
                subtotal_fen=sku.price_fen,
            )
            evaluation = eval_dao.create(
                order_id=order.id,
                order_item_id=item.id,
                goods_id=goods.id,
                shop_id=shop.id,
                buyer_id=buyer.id,
                rating=rating,
                content=content,
                images=[],
            )
            reply = seller_replies[(goods.id + i) % len(seller_replies)]
            if reply:
                evaluation.seller_reply = reply
                evaluation.seller_replied_at = now
            created_count += 1

    print(f"  已创建 {created_count} 条演示评价")


def _seed(db, *, assets: dict[str, list[str]]) -> None:
    category_map = _ensure_categories(db)
    seller = _ensure_user(
        db,
        username=SELLER_USERNAME,
        password=SELLER_PASSWORD,
        email=SELLER_EMAIL,
        phone=SELLER_PHONE,
        role="user",
    )
    shop = _ensure_shop(db, seller)
    goods_list = _seed_goods(
        db,
        seller=seller,
        shop_id=shop.id,
        category_map=category_map,
        assets=assets,
    )
    buyer = _ensure_buyer(db)
    _seed_evaluations(db, buyer=buyer, shop=shop, goods_list=goods_list)

    print("种子数据就绪。")
    print(f"  商品数量：{len(GOODS)}")
    if assets:
        print(f"  KiVault 图片清单：{len(assets)} 个商品")
    else:
        print("  商品图片：当前使用本地占位图")


def _reset(db) -> None:
    tables = [
        "mall_chat_messages",
        "mall_payments",
        "mall_withdraw_requests",
        "mall_wallet_ledger",
        "mall_refunds",
        "mall_goods_evaluations",
        "mall_order_logs",
        "mall_order_items",
        "mall_orders",
        "mall_user_coupons",
        "mall_coupons",
        "mall_goods_footprints",
        "mall_favorites",
        "mall_addresses",
        "mall_cart_items",
        "mall_goods_skus",
        "mall_goods",
        "mall_wallets",
        "mall_shops",
        "mall_categories",
    ]
    for table in tables:
        db.execute(text(f'DELETE FROM "{table}"'))
    print("已清空商城数据。")


def main() -> None:
    parser = argparse.ArgumentParser(description="商城演示数据")
    parser.add_argument("--reset", action="store_true", help="先清空商城数据再填充")
    args = parser.parse_args()

    def _job(db) -> None:
        if args.reset:
            _reset(db)
        _seed(db, assets=ASSET_URLS)

    run_in_new_session(_job)


if __name__ == "__main__":
    main()
