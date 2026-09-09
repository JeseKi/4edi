#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商城种子数据（可重复执行）。

运行：
    # 默认准备整改取证用的真实主体账号与内容；传入材料后自动完成审核与签约。
    .venv/bin/python scripts/seed_mall.py

    # 仅在 dev/test 环境生成原有的商城演示数据。
    .venv/bin/python scripts/seed_mall.py --profile demo

    # dev/test 环境可先清空商城数据。
    .venv/bin/python scripts/seed_mall.py --reset
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import getpass
import hashlib
import mimetypes
import os
from pathlib import Path
import re
import sys
import termios

sys.path.append(str(Path(__file__).resolve().parent.parent))

from typing import TextIO, TypedDict

from sqlalchemy import text

from src.server.audit import service as audit_service
from src.server.audit.models import AuditEvent
from src.server.auth.dao import UserDAO
from src.server.config import global_config
from src.server.auth.dependencies.current_user import AuthenticatedPrincipal
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.auth.service import short_transactions as auth_transactions
from src.server.database import run_in_new_session
from src.server.files.models import FileAsset
from src.server.files.service import short_transactions as file_transactions
from src.server.files.storage import LocalFileStorage, get_file_storage
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
from src.server.mall.models import (
    Goods,
    GoodsStatus,
    OrderStatus,
    Shop,
    ShopAgreement,
    ShopOnboardingStage,
    ShopQualificationReview,
    ShopStatus,
)
from src.server.mall.service import short_transactions as service
from src.server.information.dao import InformationPostDAO
from src.server.information.models import (
    InformationPost,
    InformationStatus,
    PublisherVerification,
    PublisherVerificationStatus,
)
from src.server.information.service import short_transactions as information_service


class GoodsSeed(TypedDict):
    slug: str
    category: str
    name: str
    fallback_image: str
    original_price_fen: int | None
    detail: str
    skus: list[dict]


class InformationSeed(TypedDict):
    title: str
    category: str
    price: str
    content: str
    contact_name: str
    contact_phone: str
    attributes: dict[str, str]
    poster: str
    status: InformationStatus
    is_top: bool
    view_count: int
    age_days: int
    reject_reason: str | None


class ComplianceInformationSeed(TypedDict):
    title: str
    category: str
    price: str
    content: str
    contact_name: str
    contact_phone: str
    attributes: dict[str, str]


@dataclass(frozen=True)
class ComplianceApplicationInputs:
    merchant_business_license_path: Path | None = None
    merchant_identity_front_path: Path | None = None
    merchant_identity_back_path: Path | None = None
    merchant_authorization_path: Path | None = None
    merchant_identity_number: str | None = None
    merchant_applicant_name: str | None = None
    merchant_business_address: str | None = None
    merchant_contact_phone: str | None = None
    merchant_license_valid_until: date | None = None
    merchant_license_long_term: bool = False
    publisher_identity_front_path: Path | None = None
    publisher_identity_back_path: Path | None = None
    publisher_identity_number: str | None = None
    publisher_document_valid_until: date | None = None
    publisher_document_long_term: bool = False


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

RESTRICTED_CATEGORY_NAMES = {"食品生鲜", "休闲零食"}
SEED_QUALIFICATION_EVIDENCE_ASSET_ID = "5eed0000000000000000000000000000"


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
            {
                "sku_code": "AT-PRO-IVORY",
                "specs": {"颜色": "云岩白"},
                "price_fen": 29900,
                "stock": 90,
            },
            {
                "sku_code": "AT-PRO-BLACK",
                "specs": {"颜色": "曜石黑"},
                "price_fen": 29900,
                "stock": 80,
            },
            {
                "sku_code": "AT-PRO-BLUE",
                "specs": {"颜色": "雾霾蓝"},
                "price_fen": 31900,
                "stock": 50,
            },
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
            {
                "sku_code": "PS2-BLACK-SIL",
                "specs": {"表壳": "曜石黑", "表带": "硅胶"},
                "price_fen": 59900,
                "stock": 60,
            },
            {
                "sku_code": "PS2-SILVER-SIL",
                "specs": {"表壳": "星辉银", "表带": "硅胶"},
                "price_fen": 61900,
                "stock": 50,
            },
            {
                "sku_code": "PS2-SILVER-LEA",
                "specs": {"表壳": "星辉银", "表带": "皮革"},
                "price_fen": 66900,
                "stock": 40,
            },
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
            {
                "sku_code": "K75-WHITE-LINEAR",
                "specs": {"配色": "雾白", "轴体": "线性轴"},
                "price_fen": 39900,
                "stock": 45,
            },
            {
                "sku_code": "K75-WHITE-TACTILE",
                "specs": {"配色": "雾白", "轴体": "段落轴"},
                "price_fen": 41900,
                "stock": 35,
            },
            {
                "sku_code": "K75-GRAY-LINEAR",
                "specs": {"配色": "深空灰", "轴体": "线性轴"},
                "price_fen": 39900,
                "stock": 40,
            },
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
            {
                "sku_code": "FSX-SILVER",
                "specs": {"颜色": "银色"},
                "price_fen": 10900,
                "stock": 120,
            },
            {
                "sku_code": "FSX-GRAY",
                "specs": {"颜色": "深空灰"},
                "price_fen": 11900,
                "stock": 100,
            },
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
            {
                "sku_code": "TG500-PINK",
                "specs": {"颜色": "樱花粉"},
                "price_fen": 8900,
                "stock": 100,
            },
            {
                "sku_code": "TG500-BLUE",
                "specs": {"颜色": "星空蓝"},
                "price_fen": 8900,
                "stock": 100,
            },
            {
                "sku_code": "TG500-WHITE",
                "specs": {"颜色": "珍珠白"},
                "price_fen": 8900,
                "stock": 100,
            },
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
            {
                "sku_code": "CR3-BW-40",
                "specs": {"配色": "黑白", "尺码": "40"},
                "price_fen": 19900,
                "stock": 30,
            },
            {
                "sku_code": "CR3-BW-41",
                "specs": {"配色": "黑白", "尺码": "41"},
                "price_fen": 19900,
                "stock": 35,
            },
            {
                "sku_code": "CR3-BW-42",
                "specs": {"配色": "黑白", "尺码": "42"},
                "price_fen": 19900,
                "stock": 35,
            },
            {
                "sku_code": "CR3-GRAY-42",
                "specs": {"配色": "雾灰", "尺码": "42"},
                "price_fen": 20900,
                "stock": 20,
            },
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
            {
                "sku_code": "UF-OLIVE-M",
                "specs": {"颜色": "橄榄绿", "尺码": "M"},
                "price_fen": 16900,
                "stock": 35,
            },
            {
                "sku_code": "UF-OLIVE-L",
                "specs": {"颜色": "橄榄绿", "尺码": "L"},
                "price_fen": 16900,
                "stock": 40,
            },
            {
                "sku_code": "UF-KHAKI-M",
                "specs": {"颜色": "浅卡其", "尺码": "M"},
                "price_fen": 16900,
                "stock": 30,
            },
            {
                "sku_code": "UF-KHAKI-L",
                "specs": {"颜色": "浅卡其", "尺码": "L"},
                "price_fen": 16900,
                "stock": 35,
            },
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
            {
                "sku_code": "NUTS-20",
                "specs": {"规格": "25g×20 袋"},
                "price_fen": 9900,
                "stock": 160,
            },
            {
                "sku_code": "NUTS-30",
                "specs": {"规格": "25g×30 袋"},
                "price_fen": 13900,
                "stock": 120,
            },
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
            {
                "sku_code": "SL-CARD-OAT-S",
                "specs": {"颜色": "燕麦色", "尺码": "S"},
                "price_fen": 18900,
                "stock": 28,
            },
            {
                "sku_code": "SL-CARD-OAT-M",
                "specs": {"颜色": "燕麦色", "尺码": "M"},
                "price_fen": 18900,
                "stock": 36,
            },
            {
                "sku_code": "SL-CARD-GRAY-S",
                "specs": {"颜色": "烟灰色", "尺码": "S"},
                "price_fen": 19900,
                "stock": 24,
            },
            {
                "sku_code": "SL-CARD-GRAY-M",
                "specs": {"颜色": "烟灰色", "尺码": "M"},
                "price_fen": 19900,
                "stock": 32,
            },
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
            {
                "sku_code": "TS-CHAIR-KHAKI",
                "specs": {"颜色": "沙丘卡其"},
                "price_fen": 15900,
                "stock": 55,
            },
            {
                "sku_code": "TS-CHAIR-GREEN",
                "specs": {"颜色": "森林绿"},
                "price_fen": 15900,
                "stock": 50,
            },
            {
                "sku_code": "TS-CHAIR-BLACK",
                "specs": {"颜色": "曜石黑"},
                "price_fen": 16900,
                "stock": 45,
            },
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
            {
                "sku_code": "CT22-GRAY",
                "specs": {"颜色": "石墨灰"},
                "price_fen": 22900,
                "stock": 65,
            },
            {
                "sku_code": "CT22-BLACK",
                "specs": {"颜色": "曜石黑"},
                "price_fen": 22900,
                "stock": 70,
            },
            {
                "sku_code": "CT22-GREEN",
                "specs": {"颜色": "松针绿"},
                "price_fen": 23900,
                "stock": 45,
            },
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
            {
                "sku_code": "HDP-WHITE",
                "specs": {"颜色": "暖白"},
                "price_fen": 21900,
                "stock": 80,
            },
            {
                "sku_code": "HDP-GRAY",
                "specs": {"颜色": "深空灰"},
                "price_fen": 22900,
                "stock": 70,
            },
        ],
    },
]

# 本轮新增的 20 个商品。图片均由 KiVault 公共图床托管，便于演示环境直接访问。
GOODS.extend(
    [
        {
            "slug": "garment-steamer",
            "category": "家居日用",
            "name": "SteamGo 便携手持挂烫机 旅行小型除皱",
            "fallback_image": "/mall/goods-1.svg",
            "original_price_fen": 21900,
            "detail": "轻巧手持设计，预热后可用于衬衫、针织物等日常衣物的快速除皱。可拆卸水箱便于补水，旅行和宿舍收纳更省空间。使用时请保持衣物平整，并避开不耐高温面料。",
            "skus": [
                {
                    "sku_code": "SG-CREAM",
                    "specs": {"颜色": "奶油白"},
                    "price_fen": 15900,
                    "stock": 68,
                },
                {
                    "sku_code": "SG-GRAY",
                    "specs": {"颜色": "雾灰"},
                    "price_fen": 15900,
                    "stock": 56,
                },
            ],
        },
        {
            "slug": "open-ear-earbuds",
            "category": "手机通讯",
            "name": "OpenBeat 开放式运动蓝牙耳机 低延迟长续航",
            "fallback_image": "/mall/goods-2.svg",
            "original_price_fen": 45900,
            "detail": "开放式耳挂结构让双耳保持环境感知，适合通勤、骑行与轻运动。定向声学单元配合双麦通话降噪，充电盒可提供额外续航。日常防汗防泼溅，运动后请擦干再收纳。",
            "skus": [
                {
                    "sku_code": "OB-BLACK",
                    "specs": {"颜色": "曜石黑"},
                    "price_fen": 32900,
                    "stock": 72,
                },
                {
                    "sku_code": "OB-BEIGE",
                    "specs": {"颜色": "沙岩米"},
                    "price_fen": 33900,
                    "stock": 45,
                },
            ],
        },
        {
            "slug": "magnetic-power-bank",
            "category": "手机通讯",
            "name": "MagCharge 10000mAh 磁吸无线充电宝 轻薄快充",
            "fallback_image": "/mall/goods-3.svg",
            "original_price_fen": 26900,
            "detail": "10000mAh 容量的轻薄磁吸充电宝，可为兼容设备提供无线充电，也支持 USB-C 有线输出。磨砂铝合金外壳耐日常刮擦，出行前建议为本品充满电。实际可用容量受设备与使用环境影响。",
            "skus": [
                {
                    "sku_code": "MC-NAVY",
                    "specs": {"颜色": "深海蓝"},
                    "price_fen": 19900,
                    "stock": 88,
                },
                {
                    "sku_code": "MC-SILVER",
                    "specs": {"颜色": "银灰"},
                    "price_fen": 19900,
                    "stock": 75,
                },
            ],
        },
        {
            "slug": "usb-c-hub",
            "category": "电脑办公",
            "name": "DockMini 7 合 1 USB-C 扩展坞 HDMI 读卡器",
            "fallback_image": "/mall/goods-4.svg",
            "original_price_fen": 19900,
            "detail": "为 USB-C 设备扩展 HDMI、USB-A、USB-C 与 SD/microSD 读卡接口的小型扩展坞。铝合金机身便于携带，适合会议投屏和移动办公。请确认设备 USB-C 接口支持所需的视频输出协议。",
            "skus": [
                {
                    "sku_code": "DM-GRAY",
                    "specs": {"颜色": "深空灰"},
                    "price_fen": 13900,
                    "stock": 96,
                }
            ],
        },
        {
            "slug": "scented-candle",
            "category": "家居日用",
            "name": "暮木香氛蜡烛 180g 岩兰草檀木调",
            "fallback_image": "/mall/goods-1.svg",
            "original_price_fen": 15900,
            "detail": "温暖木质香调香氛蜡烛，陶瓷杯搭配防尘盖，适合卧室、书房与休闲时刻。首次点燃建议使表层蜡充分融化以获得更均匀的燃烧效果。请置于平稳耐热表面并远离儿童和可燃物。",
            "skus": [
                {
                    "sku_code": "CANDLE-SANDAL",
                    "specs": {"香型": "岩兰草檀木"},
                    "price_fen": 10900,
                    "stock": 110,
                },
                {
                    "sku_code": "CANDLE-FIG",
                    "specs": {"香型": "无花果绿叶"},
                    "price_fen": 10900,
                    "stock": 90,
                },
            ],
        },
        {
            "slug": "lunch-tote",
            "category": "家居日用",
            "name": "FreshDay 加厚保温午餐包 大容量便携饭盒袋",
            "fallback_image": "/mall/goods-2.svg",
            "original_price_fen": 9900,
            "detail": "加厚保温层搭配拉链主仓，可容纳常见饭盒、水果与饮品。外层耐磨易清洁，双提手携带轻松。保温效果受环境与装入食物温度影响，建议与冰袋或保温容器搭配使用。",
            "skus": [
                {
                    "sku_code": "FD-SAGE",
                    "specs": {"颜色": "鼠尾草绿"},
                    "price_fen": 6900,
                    "stock": 150,
                },
                {
                    "sku_code": "FD-BEIGE",
                    "specs": {"颜色": "燕麦米"},
                    "price_fen": 6900,
                    "stock": 130,
                },
            ],
        },
        {
            "slug": "travel-umbrella",
            "category": "户外装备",
            "name": "WindLite 轻量折叠晴雨伞 防晒防泼水",
            "fallback_image": "/mall/goods-3.svg",
            "original_price_fen": 8900,
            "detail": "轻量三折伞骨结合防泼水伞布，折叠后可放入通勤包侧袋。伞面提供日常遮阳与挡雨能力，遇强风天气请注意使用安全。收伞后建议晾干再放入收纳套。",
            "skus": [
                {
                    "sku_code": "WL-BLACK",
                    "specs": {"颜色": "曜石黑"},
                    "price_fen": 5900,
                    "stock": 180,
                },
                {
                    "sku_code": "WL-BLUE",
                    "specs": {"颜色": "雾蓝"},
                    "price_fen": 5900,
                    "stock": 140,
                },
            ],
        },
        {
            "slug": "coffee-grinder",
            "category": "家居日用",
            "name": "GrindCraft 手摇咖啡磨豆机 陶瓷芯可调粗细",
            "fallback_image": "/mall/goods-4.svg",
            "original_price_fen": 18900,
            "detail": "不锈钢机身与木质握柄兼具耐用和手感，陶瓷磨芯支持调节研磨粗细，适合手冲、法压等日常冲煮方式。首次使用前请清洁研磨仓，研磨后保持干燥避免水洗磨芯。",
            "skus": [
                {
                    "sku_code": "GC-WALNUT",
                    "specs": {"木纹": "胡桃木色"},
                    "price_fen": 12900,
                    "stock": 64,
                }
            ],
        },
        {
            "slug": "knit-throw",
            "category": "家居日用",
            "name": "CozyWeave 针织盖毯 130×170cm 柔软保暖",
            "fallback_image": "/mall/goods-1.svg",
            "original_price_fen": 19900,
            "detail": "细密罗纹针织毯，适合沙发午休、空调房与居家阅读。柔软混纺面料有自然垂坠感，简约色调便于融入不同家居风格。建议冷水轻柔洗涤并平铺晾干。",
            "skus": [
                {
                    "sku_code": "CW-OAT",
                    "specs": {"颜色": "燕麦色"},
                    "price_fen": 14900,
                    "stock": 80,
                },
                {
                    "sku_code": "CW-GRAY",
                    "specs": {"颜色": "烟灰色"},
                    "price_fen": 14900,
                    "stock": 70,
                },
            ],
        },
        {
            "slug": "crossbody-bag",
            "category": "女装",
            "name": "Mellow 半月斜挎包 轻量通勤小方包",
            "fallback_image": "/mall/goods-2.svg",
            "original_price_fen": 23900,
            "detail": "半月轮廓的小巧斜挎包，采用细腻纹理面料与可调节肩带，容纳手机、卡包、钥匙等出门随身物品。内置分隔袋方便收纳，日常清洁请使用微湿软布轻擦。",
            "skus": [
                {
                    "sku_code": "MELLOW-NAVY",
                    "specs": {"颜色": "海军蓝"},
                    "price_fen": 16900,
                    "stock": 76,
                },
                {
                    "sku_code": "MELLOW-BROWN",
                    "specs": {"颜色": "焦糖棕"},
                    "price_fen": 16900,
                    "stock": 66,
                },
            ],
        },
        {
            "slug": "cotton-tshirt",
            "category": "男装",
            "name": "Everyday 260g 男士重磅纯棉短袖 T 恤",
            "fallback_image": "/mall/goods-3.svg",
            "original_price_fen": 12900,
            "detail": "260g 纯棉面料打造挺括基础版型，圆领与落肩剪裁便于单穿或作内搭。无夸张图案，适合日常通勤与休闲搭配。建议反面冷水洗涤，深浅色分开，避免高温烘干。",
            "skus": [
                {
                    "sku_code": "ED-CHARCOAL-M",
                    "specs": {"颜色": "炭灰", "尺码": "M"},
                    "price_fen": 8900,
                    "stock": 90,
                },
                {
                    "sku_code": "ED-CHARCOAL-L",
                    "specs": {"颜色": "炭灰", "尺码": "L"},
                    "price_fen": 8900,
                    "stock": 100,
                },
                {
                    "sku_code": "ED-WHITE-L",
                    "specs": {"颜色": "暖白", "尺码": "L"},
                    "price_fen": 8900,
                    "stock": 85,
                },
            ],
        },
        {
            "slug": "yoga-leggings",
            "category": "女装",
            "name": "FlexMove 女士高腰瑜伽裤 弹力速干运动紧身裤",
            "fallback_image": "/mall/goods-4.svg",
            "original_price_fen": 17900,
            "detail": "高腰包裹与四面弹力面料兼顾日常训练的舒适度和活动自由度，面料具备速干特性。适合瑜伽、普拉提和轻度健身，建议使用洗衣袋冷水清洗，不与粗糙衣物混洗。",
            "skus": [
                {
                    "sku_code": "FM-PLUM-S",
                    "specs": {"颜色": "梅子紫", "尺码": "S"},
                    "price_fen": 12900,
                    "stock": 65,
                },
                {
                    "sku_code": "FM-PLUM-M",
                    "specs": {"颜色": "梅子紫", "尺码": "M"},
                    "price_fen": 12900,
                    "stock": 75,
                },
            ],
        },
        {
            "slug": "sports-bottle",
            "category": "户外装备",
            "name": "HydraLoop 750ml 运动水壶 防漏提环设计",
            "fallback_image": "/mall/goods-1.svg",
            "original_price_fen": 7900,
            "detail": "750ml 大容量运动水壶，旋盖配合硅胶密封圈降低漏水风险，提环方便跑步、徒步和健身携带。宽口便于清洗与放入冰块。首次使用前请充分清洗，不建议盛装高温液体。",
            "skus": [
                {
                    "sku_code": "HL-ORANGE",
                    "specs": {"颜色": "活力橙"},
                    "price_fen": 4900,
                    "stock": 160,
                },
                {
                    "sku_code": "HL-TEAL",
                    "specs": {"颜色": "湖水绿"},
                    "price_fen": 4900,
                    "stock": 140,
                },
            ],
        },
        {
            "slug": "foam-roller",
            "category": "户外装备",
            "name": "RecoverPro 按摩泡沫轴 33cm 深层放松筋膜",
            "fallback_image": "/mall/goods-2.svg",
            "original_price_fen": 10900,
            "detail": "高密度泡沫材质配合分区纹理，可用于运动前热身和运动后肌肉放松。33cm 长度方便收纳携带，适合腿部、背部等大肌群的自我按摩。请根据自身承受能力循序渐进使用。",
            "skus": [
                {
                    "sku_code": "RP-TEAL",
                    "specs": {"颜色": "深青绿"},
                    "price_fen": 7900,
                    "stock": 98,
                }
            ],
        },
        {
            "slug": "bluetooth-speaker",
            "category": "手机通讯",
            "name": "PocketSound 迷你蓝牙音箱 户外便携低音增强",
            "fallback_image": "/mall/goods-3.svg",
            "original_price_fen": 16900,
            "detail": "掌心大小的便携蓝牙音箱，织物网罩与圆角机身便于随身携带。支持蓝牙连接和日常防泼溅，可用于桌面听歌、野餐和轻户外场景。实际续航会随音量与内容变化。",
            "skus": [
                {
                    "sku_code": "PS-CORAL",
                    "specs": {"颜色": "珊瑚红"},
                    "price_fen": 11900,
                    "stock": 82,
                },
                {
                    "sku_code": "PS-BLUE",
                    "specs": {"颜色": "海盐蓝"},
                    "price_fen": 11900,
                    "stock": 74,
                },
            ],
        },
        {
            "slug": "carry-on-suitcase",
            "category": "户外装备",
            "name": "TripShell 20 英寸登机拉杆箱 静音万向轮",
            "fallback_image": "/mall/goods-4.svg",
            "original_price_fen": 49900,
            "detail": "20 英寸硬壳登机箱，分区内里便于整理短途出行衣物，静音万向轮让移动更平稳。铝合金拉杆多档可调，密码锁使用前请阅读说明。不同航空公司的登机尺寸规定可能不同，请提前确认。",
            "skus": [
                {
                    "sku_code": "TS-MUSTARD",
                    "specs": {"颜色": "芥末黄"},
                    "price_fen": 35900,
                    "stock": 42,
                },
                {
                    "sku_code": "TS-BLACK",
                    "specs": {"颜色": "曜石黑"},
                    "price_fen": 35900,
                    "stock": 50,
                },
            ],
        },
        {
            "slug": "lint-remover",
            "category": "家居日用",
            "name": "CedarCare 实木除毛球器 可重复使用衣物清洁刷",
            "fallback_image": "/mall/goods-1.svg",
            "original_price_fen": 6900,
            "detail": "雪松木手柄搭配金属网面，可清理针织衫、毛呢外套和沙发织物表面的浮毛与毛球。无需电池，可重复使用。建议先在衣物不显眼处测试，并以轻柔单向动作操作。",
            "skus": [
                {
                    "sku_code": "CC-CEDAR",
                    "specs": {"材质": "雪松木柄"},
                    "price_fen": 4500,
                    "stock": 140,
                }
            ],
        },
        {
            "slug": "ceramic-bowls",
            "category": "杯壶水具",
            "name": "日常白釉陶瓷面碗 2 只装 1100ml",
            "fallback_image": "/mall/goods-2.svg",
            "original_price_fen": 11900,
            "detail": "两只装大容量陶瓷面碗，细砂白釉外观简洁耐看，适合面食、沙拉和汤饭。加厚碗沿握持舒适，可用于日常餐桌。请避免骤冷骤热，清洗时轻拿轻放。",
            "skus": [
                {
                    "sku_code": "BOWL-WHITE-2",
                    "specs": {"规格": "1100ml×2"},
                    "price_fen": 7900,
                    "stock": 120,
                }
            ],
        },
        {
            "slug": "kitchen-towels",
            "category": "家居日用",
            "name": "BambooSoft 竹纤维厨房抹布 3 条装 吸水不易掉屑",
            "fallback_image": "/mall/goods-3.svg",
            "original_price_fen": 5900,
            "detail": "三色组合厨房抹布，竹纤维混纺织物吸水性好、触感柔软，可用于擦拭台面、餐具和日常清洁。建议首次使用前清洗，使用后及时晾干并定期更换。",
            "skus": [
                {
                    "sku_code": "BS-NEUTRAL-3",
                    "specs": {"颜色": "中性色 3 条装"},
                    "price_fen": 3900,
                    "stock": 220,
                }
            ],
        },
        {
            "slug": "precision-screwdriver",
            "category": "电脑办公",
            "name": "FixMate 精密螺丝刀套装 24 合 1 磁吸收纳盒",
            "fallback_image": "/mall/goods-4.svg",
            "original_price_fen": 13900,
            "detail": "24 合 1 精密螺丝刀套装，磁吸收纳盒内含常用批头与铝合金手柄，适合眼镜、小型数码设备和玩具的日常维护。拆装电子设备前请先断电，并确认操作不会影响保修。",
            "skus": [
                {
                    "sku_code": "FM-24-GRAY",
                    "specs": {"规格": "24 合 1"},
                    "price_fen": 9900,
                    "stock": 105,
                }
            ],
        },
    ]
)


COMPLIANCE_CATEGORIES = [
    ("企业服务", None, 0),
    ("网站建设", "企业服务", 1),
    ("软件开发", "企业服务", 2),
]

# 整改站点只保留一个经真实资质核验的商家主体。原商城目录中的普通类目和商品
# 继续保留，但统一归到商家 A；食品等需要专项许可的类目仍不对外开放。
MERCHANT_A_CATEGORIES = [
    category
    for category in CATEGORIES
    if category[0] not in RESTRICTED_CATEGORY_NAMES
] + COMPLIANCE_CATEGORIES

COMPLIANCE_WEBSITE_IMAGE_URL = (
    "https://tuchuang.s3.fstc.kispace.cn/1/"
    "object_def9376fb2ae46608b669a3b15672f4f_18-website-delivery.webp"
)
COMPLIANCE_SOFTWARE_IMAGE_URL = (
    "https://tuchuang.s3.fstc.kispace.cn/1/"
    "object_17e42206db8f417685cc92ff97b160d8_19-software-delivery.webp"
)

# 整改取证商品使用“业务场景封面 + 通用交付效果图”的两图组合。
# 图片托管在公开 KiVault 对象存储中，不将二进制文件纳入 Git。
COMPLIANCE_ASSET_URLS: dict[str, list[str]] = {
    "responsive-website-service": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_97bb59f0337f4226befe8de4d49d351d_01-responsive-website.webp",
        COMPLIANCE_WEBSITE_IMAGE_URL,
    ],
    "mini-program-service": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_87cb42fae91e42b9828b2a96beaac64a_02-mini-program.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-01": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_fd8a397032cb4839a1a942633ec29661_03-restaurant-ordering.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-02": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_427582de49684f05adfbb33184fe5b54_04-appointment-booking.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-04": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_1a091db1bde74e02a1917bb17eba225e_05-fitness-app.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-07": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_7ebf3504308c4afb87b4f830e1c8b318_06-inventory-management.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-08": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_49e1b2712eb64a48a47d465fe24d80eb_07-lab-scheduling.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-10": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_027abcd9f8d14249a3b4d2c322a4a31c_09-cms-website.webp",
        COMPLIANCE_WEBSITE_IMAGE_URL,
    ],
    "information-service-11": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_a668f90c22a1409b8656dd92643b5d4c_08-marketing-landing-page.webp",
        COMPLIANCE_WEBSITE_IMAGE_URL,
    ],
    "information-service-13": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_34ffb890a61342288206dc8a76c51773_10-smart-property.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-14": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_8562b038d1d94cde990c2989d1f42611_11-campus-marketplace.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-15": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_29589fdf37d042bbad3865a337256b65_12-pet-clinic.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-16": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_4533181a2a8b465c8605fed90c01036f_13-store-inspection.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-17": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_d574562906ce42bcada0096d6f6a604c_14-school-scheduling.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-18": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_475060e0b7084b65b9d25a681d60b028_15-membership-pos.webp",
        COMPLIANCE_SOFTWARE_IMAGE_URL,
    ],
    "information-service-19": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_4f87cdf03def4fd892d7fa228ee51c21_16-multilingual-seo.webp",
        COMPLIANCE_WEBSITE_IMAGE_URL,
    ],
    "information-service-20": [
        "https://tuchuang.s3.fstc.kispace.cn/1/"
        "object_fc599939ab6f411ea4835bd6280b88e5_17-association-portal.webp",
        COMPLIANCE_WEBSITE_IMAGE_URL,
    ],
}

COMPLIANCE_GOODS: list[GoodsSeed] = [
    {
        "slug": "responsive-website-service",
        "category": "网站建设",
        "name": "响应式企业官网建设服务",
        "fallback_image": COMPLIANCE_WEBSITE_IMAGE_URL,
        "original_price_fen": None,
        "detail": (
            "由杭州互动递归科技有限公司提供的企业官网建设服务。服务范围包括需求梳理、信息架构、"
            "响应式页面设计、前后端开发、内容管理后台配置、部署上线协助和基础使用培训。\n\n"
            "基础方案适用于企业介绍、产品与服务展示、案例展示、新闻动态、联系我们等常见栏目。"
            "项目开始前，双方将根据实际需求确认页面数量、功能边界、交付周期、验收标准和后续维护方式。\n\n"
            "商品页面价格为基础方案参考价，不包含域名、云服务器、第三方短信、支付、地图等外部服务费用。"
            "最终服务内容和价格以双方确认的需求清单及订单约定为准。"
        ),
        "skus": [
            {
                "sku_code": "HDDG-WEB-BASE",
                "specs": {"服务方案": "企业官网基础版"},
                "price_fen": 350000,
                "stock": 10,
            }
        ],
    },
    {
        "slug": "mini-program-service",
        "category": "软件开发",
        "name": "小程序定制开发服务",
        "fallback_image": COMPLIANCE_SOFTWARE_IMAGE_URL,
        "original_price_fen": None,
        "detail": (
            "由杭州互动递归科技有限公司提供的小程序定制开发服务。服务流程包括需求访谈、原型确认、"
            "界面设计、功能开发、测试验收、上线协助和操作说明。\n\n"
            "可根据企业展示、预约报名、客户服务、内部协作等一般业务场景进行功能设计。"
            "如项目涉及支付、医疗、教育、食品、地图定位或其他依法需要行政许可的业务，"
            "将在核验委托方资质及平台准入范围后另行确定是否承接。\n\n"
            "商品页面价格为基础需求评估后的起始参考价。具体功能、工期、交付物、知识产权归属和"
            "维护范围以双方确认的需求清单及订单约定为准。"
        ),
        "skus": [
            {
                "sku_code": "HDDG-MINI-BASE",
                "specs": {"服务方案": "基础定制版"},
                "price_fen": 800000,
                "stock": 10,
            }
        ],
    },
]

COMPLIANCE_INFORMATION_POST: ComplianceInformationSeed = {
    "title": "响应式企业官网建设，含后台内容管理",
    "category": "website",
    "price": "3,500 元起",
    "content": (
        "杭州互动递归科技有限公司提供响应式企业官网设计与开发服务，适用于企业介绍、产品与服务展示、"
        "案例展示、新闻动态和联系信息等一般企业宣传场景。网站可适配电脑、平板和手机访问，并配置基础"
        "内容管理后台，便于企业自行维护公开内容。\n\n"
        "标准流程包括需求沟通、栏目与页面清单确认、原型或设计稿确认、开发测试、验收和部署上线协助。"
        "交付内容、工期、验收标准及后续维护范围将在项目开始前书面确认。\n\n"
        "页面标示价格为基础方案参考价，不包含域名、云服务器以及短信、支付、地图等第三方服务费用。"
        "如业务内容依法需要专项许可，将在核验相关资质后再确定是否提供服务。"
    ),
    "contact_name": "王勃智",
    "contact_phone": "19935644212",
    "attributes": {
        "site_type": "企业官网",
        "responsive": "是",
        "backend": "内容管理后台",
        "deliverable": "定制开发",
    },
}

COMPLIANCE_MERCHANT_USERNAME = "hddg"
COMPLIANCE_MERCHANT_PASSWORD = "88888888"
COMPLIANCE_MERCHANT_EMAIL = "hddg@hemu.site"
COMPLIANCE_MERCHANT_NAME = "互动递归"
COMPLIANCE_SHOP_NAME = "互动递归官方旗舰店"
COMPLIANCE_SHOP_DESCRIPTION = (
    "杭州互动递归科技有限公司直营网店，提供企业官网、小程序及一般软件定制开发服务。"
)
COMPLIANCE_MERCHANT_ENTITY_NAME = "杭州互动递归科技有限公司"
COMPLIANCE_MERCHANT_CREDIT_CODE = "91330108MAKCCCHP50"
COMPLIANCE_MERCHANT_LEGAL_REPRESENTATIVE = "周子轩"
COMPLIANCE_MERCHANT_REGISTERED_ADDRESS = (
    "浙江省杭州市滨江区浦沿街道清旷街422号2号楼2层0772室"
)
COMPLIANCE_MERCHANT_DEFAULT_CONTACT_PHONE = "19935644212"
COMPLIANCE_PUBLISHER_USERNAME = "互动递归"
COMPLIANCE_PUBLISHER_PASSWORD = "88888888"
COMPLIANCE_PUBLISHER_EMAIL = "publisher@hemu.site"
COMPLIANCE_PUBLISHER_PHONE = "19935644212"
COMPLIANCE_PUBLISHER_REAL_NAME = "王勃智"

SELLER_USERNAME = "seller"
SELLER_PASSWORD = "seller123"
SELLER_EMAIL = "seller@example.com"
SELLER_PHONE = "13800000001"

SELLER2_USERNAME = "seller2"
SELLER2_PASSWORD = "seller123"
SELLER2_EMAIL = "seller2@example.com"
SELLER2_PHONE = "13800000003"

SELLER3_USERNAME = "seller3"
SELLER3_PASSWORD = "seller123"
SELLER3_EMAIL = "seller3@example.com"
SELLER3_PHONE = "13800000004"

BUYER_USERNAME = "buyer"
BUYER_PASSWORD = "88888888"
BUYER_EMAIL = "buyer@example.com"
BUYER_PHONE = "13800000002"

INFORMATION_POSTS: list[InformationSeed] = [
    {
        "title": "杭州本地餐饮小程序开发，支持点餐、会员和配送",
        "category": "mini_program",
        "price": "项目报价 8,000 元起",
        "content": (
            "本团队长期扎根杭州，专注餐饮行业小程序定制开发，累计为本地餐饮商户交付小程序项目四十余个，覆盖中式正餐、快餐简餐、火锅烧烤、茶饮烘焙与连锁加盟等多种业态。\n"
            "我们交付的餐饮小程序围绕「堂食点餐、外卖配送、会员运营、门店管理」四大场景展开：\n"
            "一、堂食扫码点餐，顾客入座扫描桌码即可浏览图文菜单、选择规格备注、在线支付，订单实时同步后厨出单系统，服务员端支持开台、加菜、并台、结账与打印小票；\n"
            "二、外卖与自提，支持小程序内下单外卖或到店自取，可设置起送价、配送费、配送范围、营业时间与自提时段，骑手或自配送订单状态全程可跟踪；\n"
            "三、会员与储值，支持余额储值、消费积分、次卡、优惠券、生日礼包与会员等级，会员账户可与线下收银系统双向打通，余额与积分实时同步，避免多系统对账差异；\n"
            "四、营销玩法，内置限时秒杀、拼团、砍价、分享有礼、新人立减、满减满赠等常用活动模板，门店运营人员可自行创建活动，无需开发介入；\n"
            "五、门店管理后台，支持多门店独立核算，实时查看营业额、订单明细、菜品销量排行、库存预警、客流时段分布与经营周报。\n"
            "开发流程上，我们坚持先访谈、再原型、后开发：\n"
            "需求访谈免费上门，原型阶段提供可点击的高保真原型并免费修改两轮，开发阶段按里程碑交付，每个里程碑均提供可运行的演示版本供您验收，从源头避免返工。\n"
            "技术方案上，采用微信原生小程序配合云开发或自建服务器两种路线，视您的并发规模、数据归属与二次开发需求而定；\n"
            "支付接入微信支付商户号，订单与对账单支持导出 Excel，方便财务核对。\n"
            "交付内容包括小程序源码、管理后台、操作手册、上线资质协助与员工操作培训，并提供三个月免费质保，质保期内常规问题远程处理、重大故障两小时内响应。\n"
            "报价方面，标准单店版二万八千元起，连锁多店版按门店数量与功能模块评估，最终以需求清单为准；\n"
            "我们也承接存量小程序的升级改造、功能迭代与活动页面开发，按工时计费。\n"
            "若您在杭州及周边城市，我们可以上门沟通与演示，异地客户支持远程会议讲解，签约后每周同步项目进度。\n"
            "欢迎有数字化需求的餐饮老板前来咨询，我们提供免费需求评估，先了解您的门店规模、客流结构与预算，再给出量身定制的落地方案。\n"
            "我们服务的客户中，既有日流水上千单的连锁快餐，也有藏在写字楼里的精品咖啡店，每个项目都配备专属项目经理与测试工程师，上线前完成支付、并发与多机型兼容性测试，确保高峰时段平稳运行。我们相信口碑是最好的名片，许多新客户来自老客户转介绍，这也激励我们认真对待每一个项目；项目验收后，我们仍会保持联系，定期回访使用情况，结合后台数据帮您优化菜单结构与营销活动。"
        ),
        "contact_name": "陈工",
        "contact_phone": "13800000001",
        "attributes": {
            "dev_method": "原生开发",
            "secondary_dev": "是",
            "industry": "餐饮零售",
            "language": "TypeScript",
            "database": "MySQL",
        },
        "poster": SELLER_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": True,
        "view_count": 326,
        "age_days": 1,
        "reject_reason": None,
    },
    {
        "title": "预约报名小程序模板，可按行业二次开发",
        "category": "mini_program",
        "price": "2,999 元起",
        "content": (
            "这是一套经过多行业打磨的预约报名小程序方案，适用于活动报名、课程预约、场地预约、会议签到、服务排队等需要「先约后到」的业务场景，目前已服务教育培训、健身场馆、亲子乐园、律师事务所、牙科诊所等上百家客户。\n"
            "系统包含用户端小程序与运营管理后台两大模块。\n"
            "用户端支持查看活动或服务介绍、选择日期时段、填写报名表单、在线支付订金或全款、接收预约成功通知与临期提醒、查看历史预约记录与电子凭证，凭证支持转赠；\n"
            "管理后台支持创建不限数量的活动与服务项目，自定义报名表单字段，设置每日名额上限、时段容量、提前截止时间、取消与改期规则，报名数据实时汇总并支持按日期导出；\n"
            "同时提供候补队列、爽约自动释放名额、分店隔离与多运营角色权限。\n"
            "为了贴近各行业的真实用法，我们内置了教育培训的课表排班、健身场馆的私教约课、线下活动的签到核销等行业模板，购买模板后可直接修改文案、价格与视觉样式，按品牌规范进行二次开发，包括自定义表单、对接公众号消息、接入微信支付与储值体系、同步企业微信通知、以及和您现有 ERP、教务系统做数据对接。\n"
            "模板采用模块化开发，所有功能均通过后台配置完成，运营人员无需编程即可上架新活动；\n"
            "源码交付后您拥有全部代码，可自行部署到自有服务器，也可以委托我们托管运维。\n"
            "购买流程为：\n"
            "先提供您的业务介绍与参考案例，我们给出适配清单与改造成本评估，确认后签订合同，标准版改造周期约一到两周，交付时提供使用手册与视频教程，并附带一个月的免费运维期。\n"
            "售价方面，标准模板 2,999 元起，含基础配置与上线协助；\n"
            "行业深度定制按需求评估，老客户后续功能迭代享有折扣。\n"
            "我们提供终身免费的业务咨询，运营中遇到流程问题可以随时沟通调整方案，确保系统能长期贴合您的实际业务，而不是买回来就变成摆设。\n"
            "相比一次性开发，我们更看重系统上线后的持续运营，因此模板内置了数据统计看板，可查看每日预约量、各时段负荷、渠道来源、取消率与爽约率，帮您及时发现问题；所有数据支持导出，方便财务对账与活动复盘。系统支持多管理员协同，店长、前台、财务各司其职，操作日志完整记录，责任清晰；手机端与电脑端数据实时同步，在门店现场也能完成核销与查询。我们还提供上线后的运营建议，包括活动模板、文案与推广渠道建议，帮助新业务快速跑起来，而不是把系统买回去当摆设。\n"
            "同时支持对接微信公众号与视频号，预约通知与营销推文可以触达更广泛的用户；系统还预留了接口，后续若需对接教务系统、CRM 或企业微信，均可平滑扩展。我们每个季度都会根据客户反馈迭代模板，购买过的客户可免费获得基础功能的升级，让您的系统持续跟上业务发展，避免重复投资。"
        ),
        "contact_name": "林先生",
        "contact_phone": "13800000003",
        "attributes": {
            "dev_method": "模板开发",
            "secondary_dev": "是",
            "industry": "教育培训",
            "language": "JavaScript",
            "database": "PostgreSQL",
        },
        "poster": SELLER2_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 187,
        "age_days": 3,
        "reject_reason": None,
    },
    {
        "title": "企业展示小程序开发，适合品牌宣传与获客",
        "category": "mini_program",
        "price": "面议",
        "content": (
            "面向中小企业提供品牌展示类小程序开发服务，帮助企业在微信生态内建立官方形象窗口，实现品牌曝光、产品展示、线索收集与门店引流的一体化。\n"
            "我们服务过的客户涵盖制造工厂、设计工作室、连锁门店、律所与咨询机构等行业，深知不同行业对展示内容与转化路径的需求差异。\n"
            "功能上，小程序包含品牌首页、企业介绍、产品与服务分类、案例展示、新闻动态、团队介绍、资质荣誉、地图导航与在线留言等模块，每个模块均可按需增删；\n"
            "首页支持沉浸式 Banner 轮播、视频宣传片播放与多级导航菜单，视觉风格贴合企业 VI 色系；\n"
            "获客方面内置表单留资、一键拨号、微信客服直连、电子名片分享与门店位置跳转，留资数据实时推送到管理员微信或邮箱，方便销售及时跟进；\n"
            "内容运营上提供可视化后台，运营人员可以自助更新产品图文、发布新闻、维护案例，无需每次改动都找开发。\n"
            "我们支持三种实施方式：\n"
            "一是基于现有官网内容快速迁移，两周内上线；\n"
            "二是根据品牌调性重新策划内容结构与页面设计；\n"
            "三是对已有小程序做改版升级，在不影响线上版本的前提下逐步切换。\n"
            "开发过程中，我们会先产出信息架构图与高保真设计稿，确认后再进入开发，确保最终效果与预期一致；\n"
            "上线前协助完成微信认证、类目审核与备案等手续，并培训运营人员使用后台。\n"
            "交付物包括小程序源码、管理后台、设计源文件与操作文档，提供半年免费质保与日常技术答疑，后续功能扩展按工时报价。\n"
            "价格根据页面数量与功能复杂度评估，基础展示版通常在一万至三万元之间，请提供您的行业、页面清单与预算，我们会给出详细报价单与排期。\n"
            "选择我们，您获得的不只是一个能打开的小程序，而是一套可持续运营的品牌获客工具，我们也会在交付后定期回访，根据后台数据帮您优化内容与转化路径。\n"
            "我们深知展示类小程序的成败往往在细节：首屏加载速度、图片清晰度、文案的商务感都会影响客户对企业的第一印象，因此设计中我们坚持极简克制，把品牌气质放在第一位；同时重视可维护性，所有内容结构清晰、后台操作顺手，即使不熟悉技术的同事也能很快上手。服务过程中，我们每周同步进度，重大节点主动汇报，绝不让项目失联；验收后提供半年免费质保与长期技术答疑，如果贵司后续需要新增页面或功能，我们按老客户优惠价支持。我们还可协助申请微信支付、企业认证与相关资质，让上线之路顺畅无忧。\n"
            "我们还可以为企业搭建轻量级的电子画册与产品中心，方便销售在拜访客户时用手机直接展示，提升专业形象；同时支持多语言版本扩展，为未来布局海外市场预留空间，避免后期推倒重来。交付时我们提供设计源文件与素材清单，所有图片与文案资料归贵司所有，随时可以更换团队继续维护。"
        ),
        "contact_name": "周女士",
        "contact_phone": "13800000004",
        "attributes": {
            "dev_method": "混合开发",
            "secondary_dev": "否",
            "industry": "企业服务",
            "language": "Vue",
            "database": "MySQL",
        },
        "poster": SELLER3_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 96,
        "age_days": 6,
        "reject_reason": None,
    },
    {
        "title": "跨平台健身打卡 APP 定制开发",
        "category": "app",
        "price": "20,000 元起",
        "content": (
            "为健身工作室、私教团队与运动品牌提供跨平台 APP 定制开发服务，一套代码同时覆盖 iOS 与 Android，大幅降低双端开发与维护成本。\n"
            "我们交付的健身 APP 围绕「训练内容、打卡激励、数据沉淀、会员变现」四个核心展开：\n"
            "训练内容方面，支持训练计划库、动作库、课程视频播放与训练指导，教练可在后台编排课程并指派给学员；\n"
            "打卡激励方面，支持每日打卡、连续打卡日历、成就徽章、积分排行榜与好友 PK，配合消息提醒帮助用户养成运动习惯；\n"
            "数据沉淀方面，记录体重、体脂、心率、训练时长与卡路里等健康数据，以图表形式呈现趋势，并可生成周报月报分享到社交平台；\n"
            "会员变现方面，支持会员订阅、单次课程购买、训练营拼团与私教预约，支付对接微信支付与支付宝，订单与退款在后台自动处理。\n"
            "开发流程上，我们从产品原型与 UI 设计开始，设计阶段提供全套界面稿与交互说明，确认后进入开发；\n"
            "开发阶段每周给出可安装的测试包，您可以第一时间在真机上体验最新进度；\n"
            "上线前协助完成开发者账号注册、隐私合规、应用商店审核材料准备与提交上架。\n"
            "技术架构采用 Flutter 跨平台框架，后端使用 Node.js 或 Python 构建，数据库按数据规模选择 MySQL 或 PostgreSQL，音视频点播接入云服务商 CDN，确保高峰期课程播放流畅；\n"
            "接口全部使用 HTTPS 并做权限校验，用户健康数据加密存储，符合个人信息保护法要求。\n"
            "交付内容包含双端源码、后端源码、管理后台、部署文档与运维手册，提供三个月免费质保与持续迭代支持。\n"
            "报价按功能模块评估，MVP 版本通常两万元起，含训练、打卡、会员与支付等核心功能；\n"
            "若您已有原型或设计稿，价格可相应下调。\n"
            "我们服务过连锁健身房、线上训练营与运动营养品牌，可提供同行业案例参考，欢迎带着需求来聊，先做免费的功能评估与排期估算，确认方案后再签约开发，合同明确里程碑与付款节点，保障双方权益。\n"
            "我们特别关注训练社区的运营氛围，因此系统内置了教练动态、学员社区与每日一练等轻社交功能，帮助训练营营造持续打卡的氛围；数据看板让教练随时掌握学员活跃度与训练完成率，及时跟进掉队学员，减少课程流失。交付后我们提供三个月免费质保，并支持按季度迭代版本；已上线的客户普遍反馈，系统帮助他们的课程复购率明显提升，私教约课率也有显著改善。欢迎带着您的课程体系与运营模式来聊，我们会结合行业经验给出针对性的功能建议与报价方案。\n"
            "我们还会在版本迭代中持续优化性能与体验，已购客户可获得优惠升级，让系统与业务共同成长。"
        ),
        "contact_name": "陈工",
        "contact_phone": "13800000001",
        "attributes": {
            "dev_method": "混合开发",
            "secondary_dev": "是",
            "platform": "跨平台",
            "industry": "运动健康",
            "language": "Flutter",
        },
        "poster": SELLER_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": True,
        "view_count": 241,
        "age_days": 2,
        "reject_reason": None,
    },
    {
        "title": "Android / iOS 上门家政预约 APP 开发",
        "category": "app",
        "price": "按功能模块报价",
        "content": (
            "面向家政公司、保洁团队与社区服务商提供上门家政预约 APP 开发，帮助线下团队完成接单、派单、上门服务与结算的全流程数字化，目前已交付的服务场景包括日常保洁、深度清洗、家电维修、月嫂育儿、搬家搬运与上门开锁。\n"
            "系统由用户端、服务人员端与商家管理后台三部分组成。\n"
            "用户端支持浏览服务项目与价格、按区域和时间段下单、选择服务人员、在线支付定金或全款、实时查看服务人员位置与预计到达时间、服务完成后评价打分；\n"
            "服务人员端支持接单抢单、行程导航、上门签到、服务完成确认、加项收费与每日收入明细，工资按单自动结算；\n"
            "管理后台支持服务项目与价格配置、人员排班与区域划分、订单调度与改派、投诉处理、优惠券与会员储值、财务对账与报表导出。\n"
            "针对家政行业特点，我们还提供了重点功能：\n"
            "一是订单跟踪与轨迹留痕，每个订单从下单到完成的状态变化全程记录，避免纠纷时说不清责任；\n"
            "二是押金与保险对接，支持服务人员保证金线上缴纳与退款审核；\n"
            "三是区域定价，同一服务在不同商圈可以设置不同价格与起送标准；\n"
            "四是消息通知，预约成功、上门提醒、服务完成与评价结果均通过短信和推送同步。\n"
            "开发上采用原生与混合结合的技术路线，消息推送、支付、地图与短信均接入成熟服务商，保障稳定可靠；\n"
            "上线前协助完成各应用商店注册与上架，并提供隐私政策与合规建议。\n"
            "报价按功能模块拆分评估，基础版（用户端+后台）约三万元起，含服务人员端约四万元起，我们也可以先做需求梳理会，输出功能清单与报价明细后再决定。\n"
            "交付包含源码、部署文档与操作培训，提供半年免费质保。\n"
            "若您的团队已有成熟业务流程，我们更建议先做一轮流程梳理，把线下的派单规则、结算规则原样搬到线上，再逐步叠加营销功能，这样系统上线快、团队适应成本低，这是我们在家政行业项目上总结出的最佳实践。\n"
            "家政行业的订单往往具有强时效性，用户今天下单往往希望明天上门，因此系统对派单时效做了专门设计：新订单自动推送给附近可用服务人员，超时未接自动转派，全流程时限可配置；同时支持备用人员机制，服务人员临时请假时可一键改派，最大限度减少爽约。财务模块支持按订单、按人员、按门店三种维度核算，佣金比例灵活配置，月底结算一键生成工资单。我们还提供上门驻点实施服务，帮助团队完成人员信息录入、区域划分与流程演练，确保系统真正用起来，而不是买了一堆功能放在那里。\n"
            "系统同时提供经营分析看板，服务订单量、客单价、复购率、人员绩效等关键指标一目了然，帮助管理者用数据驱动决策；我们还支持对接短信服务商与地图平台，降低集成成本，让上线更省心。整体验收后提供半年免费质保，并按季度提供功能优化建议，陪伴您的团队持续成长。"
        ),
        "contact_name": "林先生",
        "contact_phone": "13800000003",
        "attributes": {
            "dev_method": "原生开发",
            "secondary_dev": "否",
            "platform": "Android",
            "industry": "生活服务",
            "language": "Kotlin",
        },
        "poster": SELLER2_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 154,
        "age_days": 5,
        "reject_reason": None,
    },
    {
        "title": "企业内部审批与报销 APP 方案咨询",
        "category": "app",
        "price": "免费初步评估",
        "content": (
            "我们为企业提供移动端审批与报销系统的方案咨询与实施服务，帮助团队把线下的纸质审批、口头请假与手工报销搬到线上，让流程可追踪、数据可统计、管理有依据。\n"
            "适用对象包括 20 至 500 人规模的中小企业，以及正在从微信群办公向规范化管理过渡的成长型团队。\n"
            "系统覆盖常用办公场景：\n"
            "一、审批中心，支持请假、加班、出差、采购、用印、合同会签等审批类型，表单字段完全可配置，审批流支持多级审批、会签、或签、委托与加急催办，手机端即可完成提交、审批与抄送，全程留痕；\n"
            "二、费用报销，支持发票拍照上传、OCR 自动识别发票信息、费用科目与预算校验、差旅标准控制、报销单审批与打款登记，财务可在后台批量处理并生成月度费用报表；\n"
            "三、考勤与公告，支持外勤打卡、补卡申请、考勤异常提醒与通知公告发布，重要文件已读未读一目了然；\n"
            "四、通讯录与日程，组织架构清晰展示，支持会议邀约与日程提醒，减少内部沟通成本。\n"
            "我们提供的不仅是软件，更重要的是流程梳理：\n"
            "咨询阶段会与 HR、财务与业务负责人逐一访谈，绘制现状流程图，输出改进建议与系统落地方案，评估报告与流程建议书免费提供，您可以根据方案自行选择是否继续实施。\n"
            "实施阶段我们负责需求细化、系统开发或配置、数据迁移、权限设置与全员培训，上线后提供运维支持与季度流程复盘。\n"
            "技术方案灵活，既可以选择成熟的 SaaS 版本快速开通，也可以基于开源框架二次开发部署到企业内网，满足数据不出本地的合规要求；\n"
            "移动端支持 iOS、Android 与微信企业微信。\n"
            "价格方面，纯咨询评估免费，实施费用按流程数量与定制程度评估，通常在一万元至五万元之间，按里程碑付款。\n"
            "无论最终是否合作，我们都会把评估报告与改进建议完整交付给您，让您对自身管理数字化现状有清晰认识，这是我们对每一位咨询客户的基本承诺。\n"
            "在方案咨询过程中，我们发现多数企业的问题并不在于缺少工具，而在于流程本身不够清晰：审批节点设置随意、报销标准没有成文、数据散落在不同人手里。因此我们的评估会深入一线，访谈不同岗位的真实操作，把隐形流程显性化，产出的流程图与制度建议书可以直接用于内部管理优化。系统上线后，我们提供三到六个月的陪跑服务，每月复盘系统使用数据，帮助贵司持续优化流程；员工使用问题我们设有专属客服群，工作日快速响应，保证系统真正用起来。\n"
            "我们支持按部门差异配置审批模板，例如销售部门的出差申请与研发部门的采购申请流程可以完全不同，互不干扰；历史审批数据可长期留存并支持导出，满足审计与合规要求。同时提供移动端与电脑端一致的操作体验，管理层出差在外也能随时完成审批，提升决策效率。"
        ),
        "contact_name": "示例买家",
        "contact_phone": "13800000002",
        "attributes": {
            "dev_method": "混合开发",
            "secondary_dev": "是",
            "platform": "跨平台",
            "industry": "企业服务",
            "language": "React Native",
        },
        "poster": BUYER_USERNAME,
        "status": InformationStatus.PENDING,
        "is_top": False,
        "view_count": 0,
        "age_days": 0,
        "reject_reason": None,
    },
    {
        "title": "库存进销存管理软件，支持多仓库与权限配置",
        "category": "software",
        "price": "6,800 元起",
        "content": (
            "为商贸公司、批发商与小型仓储团队提供进销存管理软件定制，把采购、销售、库存、财务与报表整合到一个系统里，替代 Excel 手工记账，解决账实不符、库存积压与对账困难的痛点。\n"
            "系统核心功能包括：\n"
            "一、基础资料，商品档案支持多规格、多单位、条码管理，往来单位（供应商与客户）资料统一维护，支持信用额度设置；\n"
            "二、采购管理，采购订单、入库单、采购退货全程联动，自动更新库存与应付账款，支持按订单分批到货与缺货提醒；\n"
            "三、销售管理，销售订单、出库单、销售退货与销售收款一体处理，支持整单折扣与抹零，开单即可看到实时库存与毛利；\n"
            "四、库存管理，支持多仓库、多库位管理，库存调拨、盘点、报损报溢都有单据留痕，库存低于预警线自动提醒补货，批次与保质期管理适合食品与医药类商品；\n"
            "五、财务结算，应收应付台账清晰，收付款登记后自动核销单据，支持月结对账与账龄分析；\n"
            "六、报表中心，库存日报、进销存汇总、毛利分析、滞销品排行、往来对账单等常用报表一键生成，全部支持导出 Excel；\n"
            "七、权限配置，按岗位设置菜单权限、数据权限与单据审核权限，老板可以设置采购不看成本、仓管只能操作本仓库等细粒度规则。\n"
            "系统采用 B/S 架构，浏览器登录即可使用，局域网或公网部署均可，支持 Windows、Linux 服务器，数据每日自动备份。\n"
            "实施流程为需求调研、基础配置、数据导入、员工培训与试运行辅导，历史库存与往来余额我们可以协助导入，上线首月提供一对一答疑。\n"
            "价格方面，单仓基础版 6,800 元起，多仓库与多门店版按模块评估，含一年内免费功能优化；\n"
            "源码交付方案另议，适合需要二次集成的企业。\n"
            "我们已在服装批发、建材五金、食品配送等行业落地多个案例，可安排演示账号供您先行体验，满意后再启动实施。\n"
            "我们特别强调数据的准确性，因为进销存的每一笔单据都会影响库存与资金，因此系统对关键操作设有二次确认与权限校验，盘点采用「锁定库存—录入实盘—差异审核」三步流程，避免误操作导致账实不符；所有单据支持反审核与红冲，错误可追溯可修正。系统上线后，我们提供首月一对一顾问服务，协助梳理期初数据、定价策略与安全库存，让系统与您的经营方式深度磨合；后续每月提供数据备份检查与性能巡检。我们还支持与电子秤、扫码枪、小票打印机等硬件对接，也可与电商平台订单同步，减少重复录入。\n"
            "系统还提供客户信用账期管理与销售提成核算，帮助商贸企业控制应收风险、激励业务团队；数据看板支持按年、按月、按商品维度逐级钻取，老板出差在外也能随时掌握经营脉搏；所有报表支持定时发送到指定邮箱，管理层无需登录即可获取经营日报。我们提供演示环境，您可以上传部分真实数据先行试用，确认符合业务习惯后再正式实施。"
        ),
        "contact_name": "周女士",
        "contact_phone": "13800000004",
        "attributes": {
            "language": "Python",
            "platform": "Web",
            "deliverable": "定制开发",
            "function": "采购销售、库存预警、盘点报表和权限管理",
        },
        "poster": SELLER3_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 278,
        "age_days": 4,
        "reject_reason": None,
    },
    {
        "title": "实验室预约排班系统，可私有化部署",
        "category": "software",
        "price": "12,000 元起",
        "content": (
            "面向高校实验室、科研院所、检测机构与共享设备中心提供实验室预约排班系统，解决设备使用冲突、人工排班繁琐、使用记录不完整等管理难题，可私有化部署到单位内网，满足科研数据不出校、不出院的安全要求。\n"
            "系统主要包含以下模块：\n"
            "一、设备管理，登记仪器设备的类型、型号、存放地点、收费标准与维护周期，支持设备分组与权限分级，贵重设备可设置必须管理员审批后才能使用；\n"
            "二、预约管理，用户可按设备、日期与时段发起预约，系统自动进行时间冲突校验，同一设备同一时段只允许一个预约生效，支持预约排队、候补自动递补与逾期释放；\n"
            "三、排班与审批，实验室管理员可设置设备开放时间、维护窗口与可预约人群，预约申请支持自动通过或人工审核两种模式，紧急实验可走加急通道；\n"
            "四、使用记录，预约到点后自动生成使用记录，支持扫码签到签退，实际使用时长与预约时长差异自动记录，便于统计设备利用率；\n"
            "五、计费与统计，按设备费率与使用时长自动计算费用，支持内部结算与对账，设备利用率、热门时段、用户使用排行等统计报表一键生成；\n"
            "六、消息提醒，预约成功、审批结果、临期提醒与设备维护通知通过站内信、短信或邮件发送，减少人工通知成本。\n"
            "系统采用 B/S 架构，兼容 Windows 与 Linux 服务器，数据库支持 PostgreSQL 与 MySQL，浏览器即可访问，无需安装客户端；\n"
            "部署完成后提供管理员与普通用户两套培训，并配套操作手册与故障排查文档。\n"
            "我们还可以根据您的管理规范做定制，例如与校园统一身份认证对接、门禁系统联动、计费与财务系统对接等。\n"
            "实施周期一般为两到四周，包含需求确认、环境部署、数据初始化与试运行辅导；\n"
            "报价 12,000 元起，具体按设备数量与定制功能评估，高校与科研机构可提供合同与发票，并支持先部署试用再付款的分期方案。\n"
            "欢迎科研管理人员联系我们获取演示环境，也欢迎分享您现有的管理痛点，我们会给出针对性的功能清单与实施建议。\n"
            "针对科研场景的特殊性，我们支持灵活的策略配置：例如课题组账号可批量预约、收费项目可走内部结算、特定设备可设置培训合格后才能预约；数据权限上，使用记录仅本人与管理员可见，涉及科研数据的操作全程审计。系统上线后提供一年的免费维护，包含功能优化与安全补丁；我们还会根据实际使用情况回访，调整时段划分与审批规则，让预约机制与实验室的真实作息匹配，减少管理员维护负担，让系统真正成为科研管理的好帮手。\n"
            "系统采用模块化设计，未来扩展门禁联动、智能电源控制或经费卡结算时无需重建系统；同时提供完善的备份与恢复方案，数据安全有保障，管理员可放心长期使用。我们也提供同类单位的部署案例参考，帮助您理解系统的实际使用效果与日常管理方式。"
        ),
        "contact_name": "陈工",
        "contact_phone": "13800000001",
        "attributes": {
            "language": "Java",
            "platform": "Linux",
            "deliverable": "源码",
            "function": "设备预约、审批、排班、使用记录和数据导出",
        },
        "poster": SELLER_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 132,
        "age_days": 8,
        "reject_reason": None,
    },
    {
        "title": "旧版桌面工具迁移 Web 管理后台服务",
        "category": "software",
        "price": "面议",
        "content": (
            "针对仍在使用老旧桌面工具、单机版软件或 Excel 管理业务的团队，提供向 Web 管理后台迁移的服务，让业务数据集中管理、多人协同办公、随时随地访问。\n"
            "常见场景包括：\n"
            "旧版单机进销存换成浏览器版、Access 或 FoxPro 数据库的老系统改造、手工 Excel 台账升级为在线管理系统、以及厂商停止维护的软件被迫替换等。\n"
            "我们首先对现有系统进行全面评估：\n"
            "盘点功能清单、梳理业务单据与字段、检查数据完整性与脏数据比例、确认迁移范围与优先级，评估报告免费提供，明确哪些功能保留、哪些优化、哪些砍掉，让您对改造投入心中有数。\n"
            "迁移过程分为数据迁移、功能重构与并行验证三个阶段：\n"
            "数据迁移阶段编写脚本将历史数据清洗并导入新库，支持增量同步直至切换日，确保数据不丢不重；\n"
            "功能重构阶段按现有业务流程重新实现核心功能，并补充旧系统缺失的审批流、日志留痕与权限控制；\n"
            "并行验证阶段新旧系统同时运行一段时间，逐项核对业务结果一致后再正式停用旧系统，最大限度降低切换风险。\n"
            "技术选型上，我们根据团队规模与维护能力选择合适的技术栈，常见组合包括 Python + FastAPI、Vue + TypeScript 与 PostgreSQL，前端适配手机浏览器，管理者在外也能审批与查看报表。\n"
            "交付内容包括系统源码、部署文档、数据字典与操作培训，旧系统数据全部迁移到新系统后仍会保留原始备份，方便随时追溯。\n"
            "价格根据系统复杂度与数据量评估，简单工具迁移一般在两万元以内，中型业务系统在五万元左右，我们会在评估后给出详细报价与排期；\n"
            "如果您只想要初步报价，提供旧系统的功能截图与使用人数即可，我们会在一到两个工作日内给出估算范围。\n"
            "迁移不是把旧界面搬进浏览器，而是借机把流程梳理清楚，这正是我们最擅长的部分，欢迎需要系统升级的团队先来聊一聊现状与目标。\n"
            "迁移过程中最容易出问题的是业务规则丢失，例如旧系统里那些「约定俗成」的折扣逻辑、特殊单据处理方式，往往只存在于操作人员的脑子里。我们会通过操作访谈把这些隐性规则逐条记录下来，形成业务规则清单，在开发与验收环节逐项核对，确保新系统完全覆盖旧系统的行为，而不是简单照搬界面。交付后我们提供一个月免费并行期支持，操作人员遇到差异可随时反馈，我们按优先级排期修复，确保切换过程平稳过渡，业务一天都不停。\n"
            "我们会在迁移前对现有数据进行完整备份，并在迁移结束后再次校验，任何一步都有核对记录；整个过程中您随时可以查看进度，掌握每个阶段的完成情况，做到心中有数。迁移完成后，我们会提交数据迁移报告与验收清单，双方确认无误后再结束项目，确保交付质量经得起检验。"
        ),
        "contact_name": "示例买家",
        "contact_phone": "13800000002",
        "attributes": {
            "language": "TypeScript",
            "platform": "Web",
            "deliverable": "定制开发",
            "function": "旧系统评估、数据迁移和后台重构",
        },
        "poster": BUYER_USERNAME,
        "status": InformationStatus.REJECTED,
        "is_top": False,
        "view_count": 0,
        "age_days": 7,
        "reject_reason": "请补充可验证的服务范围和交付说明后重新提交。",
    },
    {
        "title": "响应式企业官网建设，含后台内容管理",
        "category": "website",
        "price": "3,500 元起",
        "content": (
            "为企业建设适配手机、平板与电脑的品牌官网，一套网站全端自适应展示，并配套可视化内容管理后台，让运营人员自己就能更新内容，不再依赖开发改页面。\n"
            "标准官网包含首页、关于我们、产品与服务、案例展示、新闻动态、加入我们、联系我们等页面，页面结构可根据企业业务自由组合。\n"
            "首页设计上注重品牌调性传达与转化引导，包含品牌主视觉 Banner、核心优势区、产品展示区、客户案例区、合作伙伴区与联系入口，支持多组 Banner 轮播与视频展示；\n"
            "产品与服务页面支持分类导航与图文详情，可以展示产品规格、应用场景与下载资料；\n"
            "新闻动态支持图文发布、分类归档与搜索，方便持续输出行业内容提升搜索引擎收录。\n"
            "内容管理后台提供所见即所得编辑器，支持图文混排、表格、视频嵌入与附件上传，栏目、菜单、轮播图、友情链接均可后台配置；\n"
            "同时内置留言表单、询盘邮箱通知、访问统计与 SEO 基础设置，您可以自行设置每页的标题、关键词与描述。\n"
            "开发采用前后端分离架构，后端可选 Django、Node.js 或 WordPress 等方案，按您的维护习惯与后续扩展需求推荐；\n"
            "全站启用 HTTPS 加密，后台支持多管理员分权，操作有日志可查。\n"
            "交付流程为：\n"
            "需求沟通与内容盘点、设计稿确认（免费修改两轮）、前端开发与后台搭建、内容录入与功能测试、域名解析与上线部署、SEO 收录提交与使用培训，整体周期一般两到四周。\n"
            "价格方面，标准企业官网 3,500 元起，含五到八个页面与内容管理后台；\n"
            "页面数量较多或需要商城、会员、多语言等高级功能时按模块评估，域名与服务器可代为采购管理，费用实报实销。\n"
            "我们提供一年免费技术维护，包括安全补丁、备份检查与故障处理，日常内容更新由贵司运营人员通过后台自助完成，不需要额外支付开发费用。\n"
            "欢迎提供您的行业、参考网站与预算，我们会给出设计方案与报价。\n"
            "官网是企业线上形象的门面，我们会根据行业特性设计内容结构：制造企业突出产能与质量体系，服务企业突出案例与团队，电商品牌突出产品与活动。上线前我们会进行全终端测试，覆盖主流手机、平板与电脑分辨率，确保展示效果一致；同时完成 SEO 基础配置与百度、必应收录提交，让官网尽快被搜索引擎收录。交付后提供一年免费技术维护，包括安全更新、数据备份与故障处理，日常内容由贵司运营人员自助维护，我们提供视频教程与操作手册，确保交接顺畅，任何同事都能快速上手。\n"
            "对于需要在线咨询与访客留资的企业，我们可以集成在线客服、表单收集与 CRM 线索推送，让官网成为持续获客的入口；同时支持多语言版本扩展，为企业国际化布局预留空间。我们也会在上线后一个月内回访，根据访问数据给出内容优化建议，让官网持续发挥价值。"
        ),
        "contact_name": "林先生",
        "contact_phone": "13800000003",
        "attributes": {
            "site_type": "企业官网",
            "responsive": "是",
            "backend": "Django",
            "deliverable": "源码",
        },
        "poster": SELLER2_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": True,
        "view_count": 422,
        "age_days": 1,
        "reject_reason": None,
    },
    {
        "title": "品牌活动营销落地页设计与开发",
        "category": "website",
        "price": "1,500 元起",
        "content": (
            "为品牌推广、新品发布、促销活动、课程招生与展会报名等场景提供营销落地页的设计与开发服务，帮助您把每一分推广预算都花在转化上。\n"
            "一个合格的落地页不是把活动信息罗列出来，而是围绕「吸引—信任—行动」的逻辑组织内容，我们按此方法论为客户打造页面：\n"
            "首屏用有冲击力的主视觉与一句话卖点抓住注意力，紧接着展示活动亮点与产品价值，中间插入真实用户评价与数据背书增强信任，最后用清晰的行动按钮引导报名、留资或购买，全程控制页面长度与信息密度，避免用户流失。\n"
            "技术上，我们开发的落地页支持三端适配，移动端优先优化加载速度与点击区域，首屏加载控制在三秒以内；\n"
            "支持接入微信登录、短信验证、表单留资、在线支付与优惠券发放，收集到的线索实时推送到企业微信、邮箱或 CRM 系统；\n"
            "页面支持埋点统计，转化路径中的每一步都有数据可查，我们还会根据数据反馈帮您调整文案与按钮位置，进行 A/B 版本对比，持续提升转化率。\n"
            "除单页开发外，我们还可以提供成套的活动配套：\n"
            "H5 活动页面、小程序活动页、微信公众号图文模板、海报设计以及活动数据大屏，保证线上线下物料视觉统一。\n"
            "设计开发流程为：\n"
            "需求沟通与参考收集、设计稿提案（免费修改两轮）、前端开发与动效实现、功能联调与兼容性测试、上线部署与数据验证，常规单页三到七个工作日交付，紧急活动可加急排期。\n"
            "价格方面，标准营销落地页 1,500 元起，含页面设计与开发、表单与数据后台；\n"
            "含支付、抽奖、拼团等互动功能的页面按复杂度评估；\n"
            "老客户与批量页面合作享有优惠。\n"
            "我们服务过教育、美业、电商、会展等行业客户，可提供同类案例供参考，也欢迎您把目标渠道与活动玩法告诉我们，我们会先给出页面结构与转化设计思路，认可后再进入制作，避免做出来不对路的情况。\n"
            "营销落地页的效果离不开数据验证，我们会在页面上预埋转化跟踪代码，统计浏览量、按钮点击、表单提交与支付转化等关键指标，并在交付后一周内提供数据复盘报告，指出可以优化的环节；如果您需要，我们还可以基于数据做文案与配色的 A/B 测试，用真实数据说话，而不是拍脑袋改版。对于投放类页面，我们尤其重视加载速度与首屏转化，图片会做压缩与懒加载处理，移动端点击区域按拇指热区设计。紧急情况下我们支持当天出稿、48 小时上线的加急服务，为您的活动节点保驾护航。\n"
            "我们还可以把落地页与投放账户联动，提供承接优化建议，例如页面首屏与广告语的一致性、按钮文案与优惠力度的匹配等，让广告点击后的转化率更高；同时支持按设备、按渠道分别设置展示版本，精细化运营每一个流量入口。活动结束后，我们提供页面归档与数据总结，为下一轮活动积累经验素材。"
        ),
        "contact_name": "周女士",
        "contact_phone": "13800000004",
        "attributes": {
            "site_type": "营销落地页",
            "responsive": "是",
            "backend": "无",
            "deliverable": "成品",
        },
        "poster": SELLER3_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 205,
        "age_days": 3,
        "reject_reason": None,
    },
    {
        "title": "社区门户网站建设与栏目改版咨询",
        "category": "website",
        "price": "预约沟通",
        "content": (
            "为社区、行业协会、产业园区与社团组织提供门户网站的信息架构梳理、栏目改版与内容迁移咨询服务，帮助组织把杂乱的官网整理成信息清晰、维护省力、群众好用的服务平台。\n"
            "我们的咨询从三个层面展开：\n"
            "一、信息架构梳理，对现有网站的全部栏目、页面与内容进行盘点，按用户视角重新规划栏目树，明确每个栏目的定位、内容来源与更新频率，删除长期空置的僵尸栏目，合并内容重叠的模块，让访客三步之内能找到目标信息；\n"
            "二、内容策略建议，根据组织类型与受众特征，给出栏目内容的选题方向、更新节奏与写作规范，例如社区门户应优先保障通知公告、办事指南与民生服务的时效性，协会门户则应突出行业资讯、会员动态与政策解读；\n"
            "三、改版实施指导，在信息架构确定后，我们会输出页面原型与功能清单，指导内部团队或配合开发团队完成新版建设，并在上线前组织内容迁移，把旧站有价值的内容按新结构归位，避免改版后内容丢失或错位。\n"
            "咨询过程采用工作坊加访谈的形式：\n"
            "先由我们梳理现状并绘制架构图，再组织相关方评审，逐栏目确认去向，最终输出改版方案书，包含新栏目树、页面清单、功能需求、内容迁移计划与实施排期，方案书直接可作为招标或开发的需求依据。\n"
            "如果您希望连开发一起委托，我们也可以承接实施：\n"
            "基于成熟 CMS 或定制开发实现新门户，支持信息公开、在线办事入口、会员管理、互动留言与移动端自适应，并培训内部运营人员维护。\n"
            "咨询费用按组织规模与站点复杂度评估，单次咨询评估通常在一万元以内，改版实施另行报价；\n"
            "对高校、社区与公益组织，我们提供公益价格，先电话沟通确认需求，再预约线上面谈。\n"
            "我们相信，门户网站的价值不在于页面多漂亮，而在于信息找得到、更新跟得上、运营有人管，这正是我们咨询服务想帮您解决的问题。\n"
            "门户网站改版最怕的是「新版上线、旧内容丢失」，我们在咨询与实施中会先建立完整的内容台账，逐条登记栏目、链接与重要程度，迁移完成后逐条核对，确保一份内容都不丢；对已失效的链接我们会主动发现并给出处理建议。咨询结束后，如果由我们继续实施，方案书中的架构会直接转化为新站栏目，避免设计与实施脱节；即使您选择其他供应商，方案书也完全可以作为招标与开发依据，不会浪费。我们承诺在方案书交付后一个月内免费解答实施过程中的架构疑问，让您的改版少走弯路。\n"
            "我们还提供改版后的运营赋能服务，包括栏目负责人培训、内容规范模板与更新节奏建议，帮助组织建立可持续的内容运营机制，避免改版之后又回到无人更新的老路；对公益组织、社区与高校，我们提供优惠价格，让更多组织能够用得起专业的架构咨询。整个过程中所有交付文档均电子化归档，随时可查，方便工作交接与审计留存。"
        ),
        "contact_name": "示例买家",
        "contact_phone": "13800000002",
        "attributes": {
            "site_type": "门户网站",
            "responsive": "是",
            "backend": "Node.js",
            "deliverable": "定制开发",
        },
        "poster": BUYER_USERNAME,
        "status": InformationStatus.REJECTED,
        "is_top": False,
        "view_count": 0,
        "age_days": 9,
        "reject_reason": "标题包含不明确的推广描述，请明确具体服务内容后提交。",
    },
    {
        "title": "智慧社区物业报修缴费小程序，支持多小区多物业",
        "category": "mini_program",
        "price": "15,000 元起",
        "content": (
            "为物业公司与社区服务商提供智慧社区小程序开发，覆盖业主端、物业端与公司管理端，把报修、缴费、投诉、公告、访客登记等高频事务搬到线上，减少前台电话量与线下跑腿，提升业主满意度。\n"
            "业主端功能包括：\n"
            "一键报修，拍照上传问题描述，选择报修类型与预约时段，维修进度全程可见，完成后在线评价；\n"
            "物业缴费，支持物业费、停车费、水电公摊费在线缴纳，账单自动生成并推送提醒，缴费记录与票据随时可查；\n"
            "投诉建议，业主意见直达物业负责人，处理结果回访确认；\n"
            "公告通知，停水停电、电梯检修、社区活动第一时间推送；\n"
            "访客与门禁，业主可提前登记访客或生成访客二维码，配合门禁系统使用；\n"
            "邻里互助，支持二手置换、拼车、失物招领等社区互动栏目。\n"
            "物业端功能包括：\n"
            "工单池与派单，报修工单自动分派给对应工种，超时未处理自动升级提醒；\n"
            "收费管理，账单生成、催缴提醒、缴费核销与欠费统计；\n"
            "设备台账，电梯、水泵、配电房等设备的巡检记录与维保到期提醒；\n"
            "员工绩效，按工单完成率、响应时长与业主评价自动生成考核数据。\n"
            "公司管理端提供多小区隔离与汇总报表，各小区独立核算，总部可查看整体收缴率、报修及时率与投诉率等运营指标。\n"
            "安全与合规方面，业主个人信息加密存储，缴费对接微信支付商户号，财务对账报表自动生成，支持导出 Excel 与对接财务软件。\n"
            "实施流程为需求调研、原型确认、开发联调、数据初始化（导入楼栋、房屋、业主与设备信息）、上线培训与试运行，试点小区运行稳定后再逐步推广到其他小区。\n"
            "价格按小区数量与功能范围评估，单小区版本 15,000 元起，多小区版本按授权数量报价，支持分期部署；\n"
            "同时提供运营指导，帮助物业制定线上化推广方案，提升业主激活率。\n"
            "我们已在多个城市的住宅小区与产业园区落地，可提供演示环境与案例讲解，欢迎物业经理与社区数字化负责人联系咨询。\n"
            "物业行业人员流动性大，系统能否快速上手非常关键，因此我们把操作界面做得极简，业主端核心操作控制在三步以内，物业端工单处理一键完成；同时提供完整的培训材料与视频教程，新员工可自助学习。数据安全方面，业主手机号、房屋信息等敏感数据加密存储，导出需管理员二次授权，操作留痕可审计。上线后我们提供一年的运维服务，包括云资源监控、数据备份与功能优化，重大节假日（如台风天报修高峰）提供应急保障，确保系统在关键时候靠得住，让业主对物业服务更有信心。\n"
            "我们支持物业费账单的批量生成与自动催缴，业主缴费后电子票据即时开具，财务月底自动生成应收报表；缴费高峰期系统自动扩容，避免卡顿影响业主体验。同时提供业主满意度调查功能，物业可定期收集反馈并持续改进服务，让社区运营更有温度。"
        ),
        "contact_name": "陈工",
        "contact_phone": "13800000001",
        "attributes": {
            "dev_method": "原生开发",
            "secondary_dev": "是",
            "industry": "物业服务",
            "language": "TypeScript",
            "database": "MySQL",
        },
        "poster": SELLER_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 118,
        "age_days": 2,
        "reject_reason": None,
    },
    {
        "title": "校园二手交易与失物招领小程序开发",
        "category": "mini_program",
        "price": "9,999 元起",
        "content": (
            "面向高校、中学与封闭园区提供二手交易与失物招领小程序，打造真实可信的校内循环经济平台，帮助学生处理闲置物品、找回丢失物品，也帮助学校活跃社区氛围。\n"
            "二手交易模块：\n"
            "学生实名认证后即可发布闲置商品，支持拍照、定价、描述与校区定位，发布前可设置「面交」或「校内快递」两种交易方式；\n"
            "浏览端支持分类筛选、关键词搜索、按价格与发布时间排序，商品详情展示成色说明与实拍图，买家可与卖家站内私信沟通，确认后线下交付或线上担保交易；\n"
            "评价体系让买卖双方互相打分，违规账号由管理员处理，保障交易诚信；\n"
            "针对校园场景还支持按宿舍楼、教学楼设置取货点，以及毕业季批量出清专区。\n"
            "失物招领模块：\n"
            "拾到物品的同学拍照登记，系统按物品类型、地点与时间自动匹配疑似失物，失主认领后双方线下交接，交接时需管理员或宿管见证确认，避免冒领；\n"
            "长期无人认领的物品自动进入捐赠公示。\n"
            "运营后台支持商品审核、敏感词过滤、违规处理、数据看板与公告发布，学校老师或学生会干部即可管理，无需技术人员。\n"
            "技术方案采用微信原生小程序加云端数据库，实名认证对接微信授权与学号核验两种方式，满足校园安全管理要求；\n"
            "用户隐私数据加密保存，仅交易双方可见联系方式。\n"
            "部署流程为：\n"
            "需求确认、界面定制、功能配置、管理员培训与试运营陪跑，上线时我们协助完成校园推广（地推物料设计、宿舍群文案、开屏活动），帮助平台在首周积累首批用户与商品。\n"
            "价格 9,999 元起，含小程序端、管理后台与一年技术维护，多校区版本按校区数评估；\n"
            "我们还可根据学校要求增加校园集市活动页、积分兑换等定制功能。\n"
            "欢迎高校就业办、学生会与后勤部门联系，我们会先安排演示，确认功能符合校园管理规范后再推进合作。\n"
            "校园场景的用户习惯与公域平台差异很大，学生更信任本校同学，也更依赖社群传播，因此我们在产品设计上强化了「同校优先」：默认只展示同校信息，支持按宿舍区筛选，交易提醒可通过模板消息直达；同时提供班级群与宿舍群的一键分享入口，方便转播扩散。为了保障平台氛围，系统内置敏感词过滤、匿名举报与人工审核机制，违规商品快速下架；数据统计可看到每日发布量、成交率与热门品类，帮助运营者了解学生需求，策划集市活动。我们还提供开学季、毕业季的活动运营方案，让平台在关键节点获得更多关注与使用。\n"
            "系统支持与校园一卡通或企业微信对接，学生可用学号直接登录，无需额外注册，降低使用门槛；运营数据大屏可投放在食堂与宿舍楼公共屏，展示平台动态，扩大影响力；模板消息与订阅消息双通道提醒，重要通知不再遗漏。我们还提供平台运营规范文档与安全应急预案，帮助学校妥善处理交易纠纷与违规内容，让平台行稳致远；同时提供意见反馈入口，学生使用中的问题直达运营团队，持续改进体验。"
        ),
        "contact_name": "林先生",
        "contact_phone": "13800000003",
        "attributes": {
            "dev_method": "模板开发",
            "secondary_dev": "是",
            "industry": "教育校园",
            "language": "JavaScript",
            "database": "PostgreSQL",
        },
        "poster": SELLER2_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 143,
        "age_days": 4,
        "reject_reason": None,
    },
    {
        "title": "宠物医院预约就诊与档案管理 APP 开发",
        "category": "app",
        "price": "25,000 元起",
        "content": (
            "为宠物医院、连锁诊所与宠物服务中心提供预约就诊与档案管理 APP 开发，帮助医生与前台把挂号、候诊、病历、检查、开药与回访串联成完整闭环，减少前台手工登记压力，让宠主就诊体验更顺畅。\n"
            "宠物主端功能：\n"
            "在线预约，按医生、科室与时段预约挂号，支持初诊复诊区分与加号申请，到店前可在线填写宠物基本信息；\n"
            "电子病历，就诊记录、检查报告、处方与疫苗记录云端留存，换医生换医院都能快速调阅；\n"
            "就诊提醒，预约成功、候诊叫号、取药提醒与复诊提醒自动推送；\n"
            "在线咨询，常见问题智能答复，复杂问题转接医生；\n"
            "服务商城，支持疫苗套餐、驱虫药、处方粮与洗护服务的在线购买与核销；\n"
            "会员体系，积分、储值、会员价与生日关怀一键管理。\n"
            "医生端功能：\n"
            "接诊工作台，查看当日号源与候诊队列，一键叫号；\n"
            "病历录入，模板化录入症状、诊断与医嘱，支持图片影像上传；\n"
            "处方开立，药品库存联动，库存不足自动预警；\n"
            "随访任务，术后回访、慢性病复诊提醒按计划自动生成。\n"
            "医院管理端功能：\n"
            "号源与排班管理、收费与结算、库存与采购、经营报表（接诊量、客单价、药品毛利）、多分院数据汇总与员工绩效。\n"
            "系统特点在于「病历档案跨设备共享」，X 光片、B 超影像与化验单电子化归档，杜绝纸质档案丢失；\n"
            "数据本地化部署可选，满足医院数据安全要求。\n"
            "开发流程为需求访谈、流程梳理、原型确认、开发测试、数据迁移与上线培训，宠物主端与医生端分别提供使用培训，试运行期安排专人驻场答疑。\n"
            "报价 25,000 元起，含双端 APP、管理后台与一年质保，分院授权与私有化部署另议；\n"
            "老客户系统升级与功能扩展按工时优惠计费。\n"
            "我们服务过多家宠物诊疗机构，可先安排演示系统体验核心流程，也可以直接上门沟通，为您输出需求清单与报价方案。\n"
            "宠物诊疗行业对病历的完整性与连续性要求很高，我们的系统在病历管理上做了深入设计：支持标准化病历模板、检查报告影像上传、医嘱与复诊计划关联，慢性病患宠还能自动生成用药提醒与复诊倒计时，帮助医生与宠主共同管理健康；转诊时病历可一键授权共享，避免重复检查。系统同时支持连锁医院分院数据隔离与总部汇总，分院独立核算、总部统一运营。上线后我们提供驻场培训与试运行支持，前台、医生、护士分批培训，确保每位员工都会用；后续按季度回访，根据医院实际运营调整功能细节，持续陪伴医院成长。\n"
            "我们支持与主流宠物医保平台对接，符合条件的诊疗费用可实现线上直付或快速报销，减少宠主垫付负担，提升医院口碑；同时提供经营日报，接诊量、客单价、药占比等指标每日推送。数据全程加密存储，定期自动备份，医院信息科或委托运维均可轻松管理，让您省心省力。"
        ),
        "contact_name": "周女士",
        "contact_phone": "13800000004",
        "attributes": {
            "dev_method": "混合开发",
            "secondary_dev": "是",
            "platform": "跨平台",
            "industry": "宠物医疗",
            "language": "Flutter",
        },
        "poster": SELLER3_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 87,
        "age_days": 6,
        "reject_reason": None,
    },
    {
        "title": "连锁门店巡店打卡与整改跟踪 APP 开发",
        "category": "app",
        "price": "18,000 元起",
        "content": (
            "为连锁零售、餐饮、便利店与品牌加盟体系提供巡店管理 APP 开发，把总部对门店的巡检、评分、整改与复查搬到线上，替代纸质检查表与微信群汇报，让督导巡店有标准、有记录、有闭环。\n"
            "巡店员端功能：\n"
            "任务与路线，总部下发巡店任务与检查模板，系统按区域智能排路线，巡店员按计划执行；\n"
            "现场检查，按检查项逐项打分拍照，支持水印照片、视频取证与问题定位标注，检查项涵盖卫生、陈列、服务、安全、库存等维度，模板可随时调整；\n"
            "问题上报，发现问题一键生成整改单，自动指定责任人并设定整改期限；\n"
            "离线可用，门店地下室等无网络环境先本地保存，恢复信号后自动上传。\n"
            "门店端功能：\n"
            "整改任务接收与处理，店员上传整改后照片与说明，逾期自动升级给店长与区域经理；\n"
            "自查打卡，门店按总部要求完成每日自查并提交，结果计入门店考核。\n"
            "总部管理端功能：\n"
            "检查模板库，不同业态可配置不同检查表；\n"
            "巡店数据看板，门店得分排名、问题类型分布、整改完成率实时统计；\n"
            "预警机制，连续低分门店、超期未整改门店自动标红提醒；\n"
            "人员管理，督导、店长、店员分级授权，操作全程留痕；\n"
            "报表导出，月度巡店报告一键生成，支持对接企业微信与钉钉消息。\n"
            "系统设计上强调「发现问题必须闭环」，每个问题的生命周期（发现—指派—整改—复查—销号）都可追踪，避免检查走过场。\n"
            "技术架构采用 Flutter 跨平台开发，适配 iOS 与 Android，后台基于 Python 与 MySQL 构建，支持云端部署或私有化部署；\n"
            "照片存储使用对象存储服务，访问速度有保障。\n"
            "实施周期约四到六周，包括检查模板梳理、系统配置、人员培训与试点推广，试点门店验证后再全面铺开。\n"
            "报价 18,000 元起，按巡店员账号数与门店数量评估，总部加五十家门店以内通常不超过五万元；\n"
            "我们提供演示账号，可先用您的真实检查表配置一版试看效果，满意后再签约，确保系统贴合您的管理标准而不是让管理迁就系统。\n"
            "巡店系统的价值最终体现在执行力上，因此我们把「整改闭环」作为核心设计：问题从发现到销号全程留痕，整改超时自动逐级升级，复查不通过自动回到待整改状态，总部领导可以随时查看每家门店的问题处理进度；同时支持按周期自动生成巡店计划与检查任务，减少督导手工安排的工作量。我们还会帮您把检查标准梳理成可执行的检查表，把文字要求变成逐项打分的清单，让不同督导巡出的结果口径一致，数据可比，巡店结论真正经得起推敲。\n"
            "系统还支持与门店监控、POS 或点餐系统对接，巡店结果可与实际经营数据交叉验证，例如卫生评分与差评率、陈列评分与销量之间的关系，让管理动作更有依据。所有巡店数据自动归档，历史记录可随时查询，支持按区域、按门店、按督导多维度分析，考核公平透明。"
        ),
        "contact_name": "陈工",
        "contact_phone": "13800000001",
        "attributes": {
            "dev_method": "原生开发",
            "secondary_dev": "否",
            "platform": "Android",
            "industry": "连锁零售",
            "language": "Kotlin",
        },
        "poster": SELLER_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 75,
        "age_days": 7,
        "reject_reason": None,
    },
    {
        "title": "中小学校排课选课与成绩管理系统",
        "category": "software",
        "price": "20,000 元起",
        "content": (
            "面向中小学、职业高中与培训机构提供排课选课与成绩管理系统，解决教务排课冲突、学生选课拥挤、成绩统计手工核算等常见问题，让教务老师从繁琐表格中解放出来，让家长学生随时掌握学习动态。\n"
            "系统功能包括：\n"
            "一、基础数据管理，年级、班级、教室、教师、课程、作息时间统一维护，支持走班制与行政班并存；\n"
            "二、智能排课，根据教师任课、教室容量、课程节次与硬性限制条件自动生成课表，支持手动微调与调课留痕，排课结果自动检查冲突并给出提示；\n"
            "三、学生选课，支持必修、选修与社团课程选课，可按志愿排序与名额抽签，选课结果实时公示，未选满课程自动开放补选；\n"
            "四、成绩管理，支持成绩录入、多次考试对比、科目权重设置、及格率优秀率统计与班级年级排名，成绩单与学情分析报告一键生成，支持家长端查询并设置成绩推送权限；\n"
            "五、考勤与请假，课堂考勤、病事假审批与课时统计联动，考勤异常自动提醒班主任；\n"
            "六、家校互通，家长通过微信小程序查看课表、成绩、作业与通知，教师发布作业与班级公告，沟通记录完整可查。\n"
            "系统采用 Web 加微信小程序架构，电脑端给教务与教师使用，小程序端给家长学生使用，数据实时同步；\n"
            "部署支持学校机房私有化部署，数据留在校内，也可部署在云服务器。\n"
            "实施服务包括：\n"
            "需求调研、数据初始化（导入教师、班级、教室与课表）、教职工分批培训、试运行与正式启用，学期初排课高峰期提供专人值守支持；\n"
            "交付源码与部署文档，提供一年免费维护与功能优化。\n"
            "报价 20,000 元起，按学校规模（班级数、教师数）与定制需求评估，教育局多校版本可整体洽谈；\n"
            "我们已为多所中小学提供过教务数字化服务，可安排演示，也欢迎教务主任直接联系我们，我们愿意先免费梳理贵校的排课规则与特殊要求，评估系统能否满足后再确定合作方式。\n"
            "教务管理系统的核心是稳定与易用，我们尤其重视排课算法的实用性：除了教室、教师、班级等硬性约束，还支持教师调休、连堂课偏好、课间间隔等软性条件，排出的课表兼顾合理性与人性化；手动调整时系统实时提示冲突，调课记录可追溯。成绩管理支持与现有学籍系统对接，避免重复录入；家长端小程序覆盖查询课表、成绩、作业与通知的核心场景，无需下载安装。我们提供学期初的驻场支持，排课高峰期安排专人值守，问题现场解决；交付源码与文档，学校可长期自主维护，不依赖单一供应商。\n"
            "系统支持与微信企业号、学校公众号对接，通知与作业信息直达家长手机；数据采用角色分级查看，家长只能看到本班信息，教师可跨班管理，教务拥有全部权限，安全可控。我们提供数据迁移服务，历史成绩与课表可批量导入，切换系统不影响教学工作，平稳过渡。"
        ),
        "contact_name": "林先生",
        "contact_phone": "13800000003",
        "attributes": {
            "language": "Java",
            "platform": "Web",
            "deliverable": "源码",
            "function": "智能排课、学生选课、成绩统计和家校互通",
        },
        "poster": SELLER2_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 109,
        "age_days": 3,
        "reject_reason": None,
    },
    {
        "title": "会员储值收银与进销存一体化管理系统",
        "category": "software",
        "price": "10,000 元起",
        "content": (
            "为美容美发、足浴养生、健身房、餐饮与零售门店提供「会员储值 + 收银 + 进销存」一体化管理系统，一套系统管住钱、货、客三件事，避免多个软件数据不通、对账对不上的问题。\n"
            "会员模块：\n"
            "支持开卡、储值、积分、次卡、折扣等级与生日营销，会员消费自动累计积分与升级，储值余额变动短信与微信同步提醒，支持会员跨店通用与门店独立核算；\n"
            "收银模块：\n"
            "支持商品扫码收银、服务项目开单、整单折扣、抹零、挂单与退货退款，收银员交班自动对账，支持现金、微信、支付宝、银行卡与储值余额混合支付，小票打印格式可定制；\n"
            "进销存模块：\n"
            "商品与服务项目库存管理，采购入库、领料出库、盘点调拨全程留痕，库存不足自动提醒，按门店设置最低库存线与安全库存，批次效期管理适合食品化妆品行业；\n"
            "营销模块：\n"
            "优惠券、团购核销、拼团秒杀、会员日与短信群发，活动效果按新增会员数、核销数与连带消费统计；\n"
            "报表模块：\n"
            "营业日报、商品销售排行、会员消费分析、储值余额表、应收账款与经营利润表，老板手机端即可查看实时经营数据。\n"
            "系统支持平板、收银机与手机多端使用，单店模式即开即用，连锁模式支持多门店数据汇总与配送调拨。\n"
            "数据安全方面，系统每日自动备份，操作日志完整可查，员工权限可精确到功能按钮；\n"
            "对接能力开放，支持对接美团、抖音团购核销，以及微信小程序会员商城。\n"
            "实施流程为需求沟通、基础资料导入、员工培训、试运行与正式上线，开业或活动大促前可安排驻店支持；\n"
            "提供全年电话与远程服务，工作日四小时内响应。\n"
            "报价 10,000 元起，单店标准版含收银、会员与库存三大模块，连锁版本按门店数与功能评估，硬件（收银机、小票机、扫码枪）可代为采购，费用实报实销。\n"
            "欢迎门店经营者预约远程演示，我们会根据您的业态与门店数量给出方案与报价，也可以先提供现有经营数据让系统试算报表，直观感受系统价值后再决定合作。\n"
            "门店系统最怕「数据搬家」，我们在实施时提供完善的数据迁移服务：现有会员名单、储值余额、积分与次卡可批量导入，迁移前后余额核对一致才确认完成，老会员权益不受影响；系统还支持与新店开业的营销节奏配合，例如开业储值活动、老带新奖励等，活动模板开箱即用。硬件方面我们提供一站式配套，收银机、小票机、扫码枪、钱箱等设备代购并上门安装调试，开箱即用；联网采用断网保护设计，网络异常时本地照常收银，网络恢复后自动同步，保障营业不中断，让您用得放心。\n"
            "系统还提供员工提成与绩效核算，收银员业绩、服务项目提成自动计算，工资表一键生成；同时支持多门店间调拨与总部集中采购，连锁管理更加规范高效。我们提供 7×12 小时技术支持，营业时间遇到的问题随时有人响应，确保门店经营不受影响。"
        ),
        "contact_name": "周女士",
        "contact_phone": "13800000004",
        "attributes": {
            "language": "Python",
            "platform": "Windows",
            "deliverable": "成品",
            "function": "会员储值、收银结算、库存管理和营销报表",
        },
        "poster": SELLER3_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 167,
        "age_days": 5,
        "reject_reason": None,
    },
    {
        "title": "外贸企业多语言独立站建设与 SEO 优化",
        "category": "website",
        "price": "8,000 元起",
        "content": (
            "为外贸企业提供多语言独立站建设服务，帮助企业摆脱对平台店铺与询盘邮箱的依赖，建立自有品牌官网，沉淀客户数据，并通过 SEO 持续获取海外自然流量。\n"
            "独立站相比平台店铺的优势在于：\n"
            "品牌形象自主可控、客户数据归企业所有、询盘直接触达、营销工具不受平台限制，长期来看获客成本更低。\n"
            "我们建设的独立站支持中英西法俄阿等多语言，语种可按目标市场自由扩展，每个语种独立 URL 结构与内容管理，方便搜索引擎分语种收录。\n"
            "网站结构按外贸询盘转化设计：\n"
            "首页突出工厂实力与核心优势，产品页展示规格参数、高清图片与可下载资料，案例页呈现合作客户与验厂报告，资质页陈列认证证书，联系页集成询盘表单、WhatsApp、Skype 与邮件多通道；\n"
            "询盘表单自动过滤垃圾询盘，新询盘实时推送邮件与微信提醒，确保第一时间跟进。\n"
            "SEO 优化是我们服务的一大特色：\n"
            "上线即完成基础 SEO 配置，包括关键词调研、标题与描述编写、站点地图提交、结构化数据标记与速度优化；\n"
            "后续按月提供关键词排名报告与优化建议，帮助网站逐步获得谷歌自然流量。\n"
            "技术选型上，推荐 WordPress 加多语言插件方案，生态成熟、维护成本低，运营人员通过后台即可更新产品与文章；\n"
            "对性能要求高的企业可选择前后端分离的定制方案。\n"
            "服务器推荐香港或海外节点，海外访问速度快，我们可代购服务器与域名并负责环境配置。\n"
            "交付流程为：\n"
            "需求与目标市场分析、关键词与竞品调研、站点架构与设计、多语言内容录入（企业提供文案，我们可协助翻译）、测试上线与收录提交，周期通常三到六周。\n"
            "报价 8,000 元起，含网站建设、基础 SEO 配置与半年技术维护；\n"
            "内容翻译、深度 SEO 服务与广告投放代运营单独报价。\n"
            "我们服务过机械、家居、电子、服装等出口行业客户，可提供案例与询盘数据参考，欢迎外贸企业联系。\n"
            "外贸独立站的效果取决于细节：我们会在建站前与您沟通目标市场与客户画像，据此确定语种优先级与关键词策略；产品资料方面，我们可以协助整理产品参数表、拍摄建议与英文文案优化，让页面真正符合海外采购者的阅读习惯。上线后我们提供三个月的 SEO 陪跑，每月输出关键词排名报告与优化动作清单，帮助网站快速获得自然流量；询盘功能支持邮件、WhatsApp 多通道汇总与跟进提醒，确保每条询盘都不遗漏。我们还提供海外服务器选型建议与 CDN 加速配置，保障海外访问速度，让海外客户打开网站不再卡顿。\n"
            "我们还提供社媒运营的基础支持，帮助把产品内容同步到 Facebook、LinkedIn 等平台，配合独立站形成流量矩阵；同时提供询盘质量分析与跟进话术建议，提高转化率，让每一分建站投入都产生回报。"
        ),
        "contact_name": "林先生",
        "contact_phone": "13800000003",
        "attributes": {
            "site_type": "企业官网",
            "responsive": "是",
            "backend": "WordPress",
            "deliverable": "成品",
        },
        "poster": SELLER2_USERNAME,
        "status": InformationStatus.PENDING,
        "is_top": False,
        "view_count": 0,
        "age_days": 0,
        "reject_reason": None,
    },
    {
        "title": "行业协会信息门户与会员管理系统建设",
        "category": "website",
        "price": "30,000 元起",
        "content": (
            "为行业协会、商会、学会与行业联盟提供信息门户与会员管理一体化系统，把官网内容发布、会员入会退会、会费缴纳、活动报名与会员服务整合到一个平台，提升协会秘书处的工作效率与会员服务体验。\n"
            "信息门户部分：\n"
            "支持行业资讯、政策法规、通知公告、会员风采、专家智库、标准下载等栏目灵活配置，支持文章、图片、视频与附件等多种内容形式，重要通知支持置顶与到期自动下线；\n"
            "前台展示适配电脑与手机，支持按行业分类检索，满足会员与公众的不同浏览需求。\n"
            "会员管理部分：\n"
            "会员在线申请入会，填写企业资料并上传营业执照等附件，秘书处审核通过后自动生成会员编号与电子会员证；\n"
            "会费管理支持按年度在线缴纳，发票信息在线登记，缴费状态自动更新，欠费会员自动提醒；\n"
            "会员名录按行业、地区、等级分类展示，支持会员企业自助维护企业信息与产品介绍；\n"
            "活动管理支持活动发布、在线报名、签到核销与活动相册，报名数据实时统计；\n"
            "投票调研支持议案表决、评优评先投票与行业问卷调研，结果自动汇总；\n"
            "会员服务提供行业报告下载、供需对接信息发布与专属优惠资讯。\n"
            "系统后台按秘书处岗位配置权限，会长、秘书长、工作人员分级管理，操作留痕，数据支持导出备份。\n"
            "技术架构采用成熟的 CMS 加会员系统组合，稳定可靠且后续维护成本低，支持部署在云服务器或协会自有机房；\n"
            "提供微信小程序版会员服务入口，会员用手机即可完成查询与报名。\n"
            "实施服务包括需求调研、栏目与表单配置、历史会员数据导入、秘书处培训、试运行与正式上线，上线后提供一年运维支持与内容更新指导。\n"
            "报价 30,000 元起，按会员规模与功能模块评估，老会员续费与功能扩展享受优惠；\n"
            "对预算有限的新建协会，我们提供轻量版方案，先上线核心的信息发布与会员登记功能，后续按需扩展。\n"
            "欢迎协会秘书长与办公室负责人联系我们，安排演示并为您提供定制方案。\n"
            "协会系统的使用群体以秘书处工作人员与会员单位为主，我们在设计上遵循「简单、稳定、可传承」的原则：常用操作后台可视化配置，工作人员流动后新人也能快速接手；数据均支持导出备份，不绑定单一供应商，协会对自身数据完全可控。实施过程中，我们会先与秘书处梳理组织架构、会员分类与收费规则，再逐项配置，历史会员数据迁移做到不重不漏；上线后提供一年运维支持，并协助秘书处制定内容更新与会员服务规范，让平台持续产生价值，而不是上线后逐渐沉寂。\n"
            "我们支持与微信公众号、小程序联动，协会动态一键同步分发，会员在微信中即可完成信息获取与业务办理；同时提供年度运营报告，帮助秘书处向理事会呈现平台使用成效，争取更多资源支持。后续功能扩展按模块报价，已有数据全程保留，不因升级造成任何损失。"
        ),
        "contact_name": "周女士",
        "contact_phone": "13800000004",
        "attributes": {
            "site_type": "门户网站",
            "responsive": "是",
            "backend": "Django",
            "deliverable": "定制开发",
        },
        "poster": SELLER3_USERNAME,
        "status": InformationStatus.APPROVED,
        "is_top": False,
        "view_count": 93,
        "age_days": 8,
        "reject_reason": None,
    },
]


def _compliance_information_catalog() -> list[ComplianceInformationSeed]:
    catalog: list[ComplianceInformationSeed] = []
    for item in INFORMATION_POSTS:
        if item["title"] == COMPLIANCE_INFORMATION_POST["title"]:
            catalog.append(
                {
                    "title": COMPLIANCE_INFORMATION_POST["title"],
                    "category": COMPLIANCE_INFORMATION_POST["category"],
                    "price": COMPLIANCE_INFORMATION_POST["price"],
                    "content": COMPLIANCE_INFORMATION_POST["content"],
                    "contact_name": COMPLIANCE_INFORMATION_POST["contact_name"],
                    "contact_phone": COMPLIANCE_INFORMATION_POST["contact_phone"],
                    "attributes": dict(COMPLIANCE_INFORMATION_POST["attributes"]),
                }
            )
            continue
        catalog.append(
            {
                "title": item["title"],
                "category": item["category"],
                "price": item["price"],
                "content": item["content"],
                "contact_name": COMPLIANCE_PUBLISHER_REAL_NAME,
                "contact_phone": COMPLIANCE_PUBLISHER_PHONE,
                "attributes": dict(item["attributes"]),
            }
        )
    return catalog


def _starting_price_fen(price: str) -> int | None:
    match = re.search(r"([\d,]+)\s*元", price)
    if match is None:
        return None
    return int(match.group(1).replace(",", "")) * 100


def _compliance_goods_catalog() -> list[GoodsSeed]:
    goods = list(COMPLIANCE_GOODS)
    for index, item in enumerate(_compliance_information_catalog(), start=1):
        price_fen = _starting_price_fen(item["price"])
        if price_fen is None:
            continue
        is_website = item["category"] == "website"
        goods.append(
            {
                "slug": f"information-service-{index:02d}",
                "category": "网站建设" if is_website else "软件开发",
                "name": item["title"],
                "fallback_image": (
                    COMPLIANCE_WEBSITE_IMAGE_URL
                    if is_website
                    else COMPLIANCE_SOFTWARE_IMAGE_URL
                ),
                "original_price_fen": None,
                "detail": (
                    f"{item['content']}\n\n"
                    "本商品由同名信息发布内容生成，信息发布原文仍在信息发布频道独立保留。"
                    "页面价格为基础方案参考价，具体功能、交付周期、验收标准与最终金额以双方"
                    "确认的需求清单及订单约定为准。"
                ),
                "skus": [
                    {
                        "sku_code": f"HDDG-INFO-{index:02d}",
                        "specs": {
                            "服务类型": "网站建设" if is_website else "软件开发",
                            "服务方案": "基础方案",
                        },
                        "price_fen": price_fen,
                        "stock": 10,
                    }
                ],
            }
        )
    return goods


def _merchant_a_goods_catalog() -> list[GoodsSeed]:
    """商家 A 的完整目录：整改服务商品及原商城普通商品。"""
    legacy_goods = [
        item for item in GOODS if item["category"] not in RESTRICTED_CATEGORY_NAMES
    ]
    return [*_compliance_goods_catalog(), *legacy_goods]


# 演示店铺配置：每个店铺由独立卖家账号持有（后端约束「一用户一家店」）。
# category 字段对应 GOODS 中每个商品的 item["category"]，用于把商品分配到各店铺。
SHOPS: list[dict] = [
    {
        "username": SELLER_USERNAME,
        "password": SELLER_PASSWORD,
        "email": SELLER_EMAIL,
        "phone": SELLER_PHONE,
        "name": "示例优选旗舰店",
        "description": "官方演示店铺：主营数码家电，覆盖手机通讯与电脑办公商品，全部为测试数据。",
        "categories": {"手机通讯", "电脑办公"},
    },
    {
        "username": SELLER2_USERNAME,
        "password": SELLER2_PASSWORD,
        "email": SELLER2_EMAIL,
        "phone": SELLER2_PHONE,
        "name": "示例生活优选店",
        "description": "官方演示店铺：主营家居日用、杯壶水具与休闲食品，全部为测试数据。",
        "categories": {"家居日用", "杯壶水具", "休闲零食"},
    },
    {
        "username": SELLER3_USERNAME,
        "password": SELLER3_PASSWORD,
        "email": SELLER3_EMAIL,
        "phone": SELLER3_PHONE,
        "name": "示例运动服饰店",
        "description": "官方演示店铺：主营服装鞋包与运动户外商品，全部为测试数据。",
        "categories": {"男装", "女装", "运动鞋", "户外装备"},
    },
]

ASSET_URLS: dict[str, list[str]] = {
    "mechanical-keyboard": [
        "https://fstc.kispace.cn/i/1e33eb265a170d578076da3fe80411b1.webp"
    ],
    "running-shoes": [
        "https://fstc.kispace.cn/i/0c3381c8bd4fb92c86140e52914f3cff.webp"
    ],
    "mixed-nuts": ["https://fstc.kispace.cn/i/048da7cfa11df26648773a77a07e86a9.webp"],
    "mens-overshirt": [
        "https://fstc.kispace.cn/i/2187e6b1f57ea24941264fa4e1e432ac.webp"
    ],
    "camping-chair": [
        "https://fstc.kispace.cn/i/9bc120ffb33d52929487b6f8b42973a7.webp"
    ],
    "commuter-backpack": [
        "https://fstc.kispace.cn/i/1316d4890c8d3e1cb35c09d98f1760bb.webp"
    ],
    "wireless-earbuds": [
        "https://fstc.kispace.cn/i/71bf95293f6fc9eaeb152d27d5d8bf3b.webp"
    ],
    "vacuum-bottle": [
        "https://fstc.kispace.cn/i/1905b0b11c9859f0eb838c9b4a911c25.webp"
    ],
    "smart-watch": ["https://fstc.kispace.cn/i/5c65c0e113fd2c4668d864d2a56ff8d8.webp"],
    "laptop-stand": ["https://fstc.kispace.cn/i/cc89b971fde5da1bc473c6e9c8a02462.webp"],
    "womens-cardigan": [
        "https://fstc.kispace.cn/i/97113047d38e9fcc55902b25513793c5.webp"
    ],
    "desk-lamp": ["https://fstc.kispace.cn/i/c85979cca46e69c6bb7640546fb8fe88.webp"],
    "garment-steamer": [
        "https://fstc.kispace.cn/i/0c8300030f857b04a25e136f56c099a1.webp"
    ],
    "open-ear-earbuds": [
        "https://fstc.kispace.cn/i/01b765638a193ca35f9705500b4221b4.webp"
    ],
    "magnetic-power-bank": [
        "https://fstc.kispace.cn/i/de42c99da812b5ef969961009d69fdbb.webp"
    ],
    "usb-c-hub": ["https://fstc.kispace.cn/i/9b1b6844beaf921d35dceee805abf520.webp"],
    "scented-candle": [
        "https://fstc.kispace.cn/i/ce5a17fb0f204507dab9995917749fc9.webp"
    ],
    "lunch-tote": ["https://fstc.kispace.cn/i/54df066a8c27e5b6283b8e344ef2fd05.webp"],
    "travel-umbrella": [
        "https://fstc.kispace.cn/i/6b69a8a34765a51910eeb71290154e47.webp"
    ],
    "coffee-grinder": [
        "https://fstc.kispace.cn/i/740a12ef54fa057cecafc666bce70ffb.webp"
    ],
    "knit-throw": ["https://fstc.kispace.cn/i/e835f154589f0d071317d95e565576ac.webp"],
    "crossbody-bag": [
        "https://fstc.kispace.cn/i/60d843c70d4aaa40236532f033db9e84.webp"
    ],
    "cotton-tshirt": [
        "https://fstc.kispace.cn/i/dbbc219f4fb95d59e4f25f63cd3fe486.webp"
    ],
    "yoga-leggings": [
        "https://fstc.kispace.cn/i/7518e6ddddfe8ca934f25a337aaf27f2.webp"
    ],
    "sports-bottle": [
        "https://fstc.kispace.cn/i/346254336cc0787cf95e13982c499f92.webp"
    ],
    "foam-roller": ["https://fstc.kispace.cn/i/c1aeb59c87e872e6760faf4900d003e4.webp"],
    "bluetooth-speaker": [
        "https://fstc.kispace.cn/i/0041a82074eb5f48ab8059ce8e26ef75.webp"
    ],
    "carry-on-suitcase": [
        "https://fstc.kispace.cn/i/9f5d67ba4391cbfbaf4dc49a2ce6656c.webp"
    ],
    "lint-remover": ["https://fstc.kispace.cn/i/fc5c92b3d35596fbc7d8a2eec7b701bd.webp"],
    "ceramic-bowls": [
        "https://fstc.kispace.cn/i/d8e61f41a63066dae140d2a85ed1c8f2.webp"
    ],
    "kitchen-towels": [
        "https://fstc.kispace.cn/i/a103bbb246331f12eed21e7e46aaabec.webp"
    ],
    "precision-screwdriver": [
        "https://fstc.kispace.cn/i/a449495100834b1a81aa4234326f9361.webp"
    ],
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
    phone: str | None,
    role: str,
    display_name: str | None = None,
) -> User:
    user_dao = UserDAO(db)
    user = user_dao.get_by_username(username)
    if user is None:
        matches = {
            candidate.id: candidate
            for candidate in (
                user_dao.get_by_email(email),
                user_dao.get_by_phone(phone) if phone else None,
            )
            if candidate is not None
        }
        if len(matches) > 1:
            raise RuntimeError(
                f"Seed 账号「{username}」的邮箱和手机号分别属于不同用户"
            )
        user = next(iter(matches.values()), None)
        if user is not None:
            if not user.username.startswith("user_") or user.role != UserRole.USER:
                raise RuntimeError(
                    f"Seed 账号「{username}」的邮箱或手机号已被其他正式账号占用"
                )
            user.username = username
            user.email = email
            user.phone = phone
            user.name = display_name or username
            user.set_password(password)
            print(f"  已将实名注册账号归并为整改账号「{username}」")
        else:
            user = User(
                username=username,
                email=email,
                phone=phone,
                name=display_name or username,
                role=UserRole(role),
            )
            user.set_password(password)
            db.add(user)
        db.flush()
    elif display_name:
        user.name = display_name
    return user


def _ensure_compliance_audit_event(
    db,
    *,
    actor: User,
    action: str,
    action_label: str,
    resource_type: str,
    resource_id: int,
    target_summary: str,
    detail: dict[str, object] | None = None,
) -> None:
    actor_identifier = "seed_mall.operator_confirmed"
    existing = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.action == action,
            AuditEvent.resource_type == resource_type,
            AuditEvent.resource_id == str(resource_id),
            AuditEvent.actor_identifier == actor_identifier,
        )
        .first()
    )
    if existing is not None:
        return
    audit_service.create_event(
        db,
        outcome="success",
        action=action,
        action_label=action_label,
        priority="high",
        method="SEED",
        path="scripts/seed_mall.py",
        path_template="scripts/seed_mall.py",
        http_status_code=200,
        actor_user_id=actor.id,
        actor_username=actor.username,
        actor_role=actor.role.value,
        actor_identifier=actor_identifier,
        resource_type=resource_type,
        resource_id=resource_id,
        target_summary=target_summary,
        user_agent="seed_mall compliance workflow (operator confirmed)",
        detail={"source": "operator_confirmed_seed", **(detail or {})},
    )


def _ingest_compliance_asset(
    db,
    *,
    owner: User,
    purpose: str,
    source_path: Path,
) -> str:
    path = source_path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"合规材料文件不存在：{path}")
    suffix = path.suffix.lower()
    if suffix not in file_transactions.COMPLIANCE_EXTENSIONS:
        raise ValueError(f"合规材料格式不支持：{path.name}")
    size_bytes = path.stat().st_size
    if size_bytes > global_config.files.max_upload_bytes:
        raise ValueError(f"合规材料超过上传大小限制：{path.name}")

    storage = get_file_storage()
    if not isinstance(storage, LocalFileStorage):
        raise ValueError("非本地文件存储请通过网站页面上传合规材料")

    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    identity = f"{owner.id}:{purpose}:{suffix}:{digest.hexdigest()}"
    asset_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    storage_key = f"file-assets/{asset_id}{suffix}"
    with path.open("rb") as source:
        actual_size = storage.write_from_file(storage_key, source, size_bytes)
    if actual_size != size_bytes:
        raise ValueError(f"合规材料写入不完整：{path.name}")

    now = datetime.now(timezone.utc)
    asset = db.get(FileAsset, asset_id)
    if asset is None:
        asset = FileAsset(
            id=asset_id,
            created_by_user_id=owner.id,
            storage_driver=storage.driver,
            storage_key=storage_key,
            original_filename=path.name,
            content_type=mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            size_bytes=size_bytes,
            status=file_transactions.STATUS_AVAILABLE,
            scan_status="not_requested",
            upload_expires_at=now,
            uploaded_at=now,
        )
        db.add(asset)
    elif asset.created_by_user_id != owner.id or asset.storage_key != storage_key:
        raise ValueError(f"合规材料资产冲突：{path.name}")
    db.flush()
    return asset.id


def _ensure_compliance_shop_application(
    db,
    merchant: User,
    inputs: ComplianceApplicationInputs,
) -> Shop | None:
    existing = ShopDAO(db).get_by_owner(merchant.id)
    if existing is not None:
        return existing
    if inputs.merchant_business_license_path is None:
        return None
    if not auth_transactions.current_acceptance_status(db, merchant.id)[
        "all_current_accepted"
    ]:
        print("  商家资质未提交：请先用账号「hddg」登录并确认用户协议与隐私政策")
        return None

    assert inputs.merchant_identity_front_path is not None
    assert inputs.merchant_identity_back_path is not None
    assert inputs.merchant_identity_number is not None
    assert inputs.merchant_applicant_name is not None
    business_license_asset_id = _ingest_compliance_asset(
        db,
        owner=merchant,
        purpose="merchant_business_license",
        source_path=inputs.merchant_business_license_path,
    )
    identity_front_asset_id = _ingest_compliance_asset(
        db,
        owner=merchant,
        purpose="merchant_identity_front",
        source_path=inputs.merchant_identity_front_path,
    )
    identity_back_asset_id = _ingest_compliance_asset(
        db,
        owner=merchant,
        purpose="merchant_identity_back",
        source_path=inputs.merchant_identity_back_path,
    )
    authorization_asset_id = None
    if inputs.merchant_authorization_path is not None:
        authorization_asset_id = _ingest_compliance_asset(
            db,
            owner=merchant,
            purpose="merchant_authorization",
            source_path=inputs.merchant_authorization_path,
        )
    principal = _principal_for_seller(
        merchant, username=merchant.username, email=merchant.email
    )
    shop = service.apply_shop(
        db,
        principal,
        {
            "name": COMPLIANCE_SHOP_NAME,
            "description": COMPLIANCE_SHOP_DESCRIPTION,
            "avatar": "/mall/shop-avatar.svg",
            "real_name": inputs.merchant_applicant_name,
            "identity_number": inputs.merchant_identity_number,
            "business_license_asset_id": business_license_asset_id,
            "identity_front_asset_id": identity_front_asset_id,
            "identity_back_asset_id": identity_back_asset_id,
            "legal_entity_name": COMPLIANCE_MERCHANT_ENTITY_NAME,
            "unified_social_credit_code": COMPLIANCE_MERCHANT_CREDIT_CODE,
            "legal_representative": COMPLIANCE_MERCHANT_LEGAL_REPRESENTATIVE,
            "registered_address": COMPLIANCE_MERCHANT_REGISTERED_ADDRESS,
            "business_address": inputs.merchant_business_address
            or COMPLIANCE_MERCHANT_REGISTERED_ADDRESS,
            "contact_phone": inputs.merchant_contact_phone
            or COMPLIANCE_MERCHANT_DEFAULT_CONTACT_PHONE,
            "business_license_valid_until": inputs.merchant_license_valid_until,
            "business_license_long_term": inputs.merchant_license_long_term,
            "special_license_not_required": True,
        },
        client_ip=None,
        user_agent="seed_mall compliance application",
    )
    if authorization_asset_id is not None:
        file_transactions.attach_asset_reference(
            db,
            asset_id=authorization_asset_id,
            resource_type="shop_qualification",
            resource_id=shop.id,
            purpose="authorization_letter",
        )
    print("  已提交真实商家资质，等待管理员人工预审")
    return shop


def _ensure_publisher_verification_application(
    db,
    publisher: User,
    inputs: ComplianceApplicationInputs,
) -> PublisherVerification | None:
    current = _current_publisher_verification(db, publisher)
    if current is not None:
        return current
    pending = (
        db.query(PublisherVerification)
        .filter(
            PublisherVerification.user_id == publisher.id,
            PublisherVerification.status == PublisherVerificationStatus.PENDING,
        )
        .order_by(PublisherVerification.id.desc())
        .first()
    )
    if pending is not None:
        return pending
    if inputs.publisher_identity_front_path is None:
        return None
    if not auth_transactions.current_acceptance_status(db, publisher.id)[
        "all_current_accepted"
    ]:
        print("  实名申请未提交：请先用账号「互动递归」登录并确认用户协议与隐私政策")
        return None

    assert inputs.publisher_identity_back_path is not None
    assert inputs.publisher_identity_number is not None
    front_asset_id = _ingest_compliance_asset(
        db,
        owner=publisher,
        purpose="publisher_identity_front",
        source_path=inputs.publisher_identity_front_path,
    )
    back_asset_id = _ingest_compliance_asset(
        db,
        owner=publisher,
        purpose="publisher_identity_back",
        source_path=inputs.publisher_identity_back_path,
    )
    verification = information_service.submit_verification(
        db,
        publisher.id,
        {
            "real_name": COMPLIANCE_PUBLISHER_REAL_NAME,
            "document_type": "resident_identity_card",
            "document_number": inputs.publisher_identity_number,
            "document_front_asset_id": front_asset_id,
            "document_back_asset_id": back_asset_id,
            "document_valid_until": inputs.publisher_document_valid_until,
            "document_long_term": inputs.publisher_document_long_term,
        },
    )
    print("  已提交真实发布者实名申请，等待管理员人工审核")
    return verification


def _ensure_categories(
    db, categories: list[tuple[str, str | None, int]] = CATEGORIES
) -> dict[str, int]:
    dao = CategoryDAO(db)
    category_map: dict[str, int] = {}

    for name, parent_name, sort in categories:
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
                requires_special_license=name in RESTRICTED_CATEGORY_NAMES,
            )
        else:
            existing.sort = sort
            existing.requires_special_license = name in RESTRICTED_CATEGORY_NAMES
        category_map[name] = existing.id

    return category_map


def _ensure_demo_shop(db, seller: User, *, name: str, description: str) -> Shop:
    dao = ShopDAO(db)
    shop = dao.get_by_owner(seller.id)
    if shop is None:
        shop = dao.create(
            owner_user_id=seller.id,
            name=name,
            description=description,
            avatar="/mall/shop-avatar.svg",
        )
    else:
        shop.name = name
        shop.description = description
        shop.avatar = "/mall/shop-avatar.svg"

    now = service._utcnow()
    shop.special_license_not_required = True
    shop.business_license_long_term = True

    review = (
        db.get(ShopQualificationReview, shop.last_qualification_review_id)
        if shop.last_qualification_review_id is not None
        else None
    )
    valid_until = (
        service._qualification_review_valid_until(shop, review)
        if review is not None and review.result == "preapproved"
        else None
    )
    if valid_until is None or valid_until <= now:
        reviewer = next(
            (
                user
                for user in UserDAO(db).list_all()
                if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
            ),
            None,
        )
        if reviewer is None:
            raise RuntimeError("缺少管理员账号，无法生成商城演示资质审核记录")

        evidence_asset = db.get(FileAsset, SEED_QUALIFICATION_EVIDENCE_ASSET_ID)
        if evidence_asset is None:
            evidence_asset = FileAsset(
                id=SEED_QUALIFICATION_EVIDENCE_ASSET_ID,
                created_by_user_id=reviewer.id,
                storage_driver=global_config.files.storage_driver,
                storage_key=(f"file-assets/{SEED_QUALIFICATION_EVIDENCE_ASSET_ID}.png"),
                original_filename="商城演示数据资质核验占位文件.png",
                content_type="image/png",
                size_bytes=1,
                status="available",
                scan_status="not_requested",
                upload_expires_at=now,
                uploaded_at=now,
            )
            db.add(evidence_asset)
            db.flush()

        checklist = {
            "entity_name_matches": True,
            "credit_code_matches": True,
            "legal_representative_matches": True,
            "registration_status_valid": True,
            "registered_address_matches": True,
            "business_scope_matches": True,
            "special_license_scope_allowed": True,
        }
        review = ShopQualificationReview(
            shop_id=shop.id,
            result="preapproved",
            verification_source="商城演示数据初始化（非真实企业核验）",
            checked_at=now,
            reviewer_user_id=reviewer.id,
            evidence_asset_id=evidence_asset.id,
            registration_status="存续（演示数据）",
            checklist=checklist,
            note="仅用于本地开发和自动化测试，不代表真实企业资质核验结果。",
        )
        db.add(review)
        db.flush()
        file_transactions.attach_asset_reference(
            db,
            asset_id=evidence_asset.id,
            resource_type="shop_qualification_review",
            resource_id=review.id,
            purpose="enterprise_registry_evidence",
        )
        valid_until = service._qualification_review_valid_until(shop, review)

    assert review is not None
    assert valid_until is not None
    shop.status = ShopStatus.APPROVED
    shop.onboarding_stage = ShopOnboardingStage.APPROVED.value
    shop.reject_reason = None
    shop.closed_at = None
    shop.approved_at = shop.approved_at or now
    shop.last_qualification_review_id = review.id
    shop.last_qualification_checked_at = review.checked_at
    shop.registration_status = review.registration_status
    shop.qualification_valid_until = valid_until

    wallet = WalletDAO(db).get_or_create(shop.id)
    shop.deposit_fen = mall_config.default_deposit_fen
    wallet.deposit_fen = mall_config.default_deposit_fen
    return shop


def _principal_for_seller(
    seller: User, *, username: str, email: str
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=seller.id,
        username=username,
        role=UserRole.USER.value,
        email=email,
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
    db,
    *,
    seller: User,
    shop_id: int,
    category_map: dict[str, int],
    assets: dict[str, list[str]],
    goods: list[GoodsSeed],
    seed_sales: bool = True,
) -> list[Goods]:
    principal = _principal_for_seller(
        seller, username=seller.username, email=seller.email
    )
    goods_dao = GoodsDAO(db)
    seeded_goods: list[Goods] = []
    seeded_goods_ids: set[int] = set()

    for index, item in enumerate(goods, start=1):
        payload = _goods_payload(item, category_map, assets)
        existing = _find_seed_goods(goods_dao, shop_id=shop_id, item=item)
        if existing is None:
            goods_obj = service.create_goods(db, principal, payload)
            action = "创建"
        else:
            goods_obj = service.update_goods(db, principal, existing.id, payload)
            action = "更新"

        goods_obj.status = GoodsStatus.ON
        if seed_sales:
            goods_obj.sales = max(goods_obj.sales, index * 37)
        else:
            goods_obj.sales = 0
        seeded_goods.append(goods_obj)
        seeded_goods_ids.add(goods_obj.id)
        print(f"  商品已{action}：{goods_obj.name}（{len(payload['images'])} 张图片）")

    # 删除本脚本早先错误创建的同名重复演示商品。只作用于当前店铺，且仅清理目录中的精确名称。
    for item in goods:
        duplicates = goods_dao.list_for_shop(
            shop_id=shop_id,
            status=None,
            keyword=item["name"],
            page=1,
            page_size=50,
        )[0]
        for goods_obj in duplicates:
            if goods_obj.name == item["name"] and goods_obj.id not in seeded_goods_ids:
                service.delete_goods(db, principal, goods_obj.id)
                print(f"  已清理重复演示商品：{goods_obj.name}")

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


def _seed_information_posts(db) -> None:
    """创建覆盖信息发布各分类及审核状态的可重复演示数据。"""
    users = {
        username: UserDAO(db).get_by_username(username)
        for username in {post["poster"] for post in INFORMATION_POSTS}
    }
    now = datetime.now(timezone.utc)
    dao = InformationPostDAO(db)
    created_count = 0
    updated_count = 0

    for item in INFORMATION_POSTS:
        poster = users[item["poster"]]
        if poster is None:
            raise RuntimeError(f"信息发布种子用户不存在：{item['poster']}")
        post = (
            db.query(InformationPost)
            .filter(
                InformationPost.title == item["title"],
                InformationPost.poster_user_id == poster.id,
            )
            .first()
        )
        if post is None:
            post = dao.create(
                title=item["title"],
                category=item["category"],
                content=item["content"],
                contact_name=item["contact_name"],
                contact_phone=item["contact_phone"],
                poster_user_id=poster.id,
                price=item["price"],
                attributes=item["attributes"],
            )
            created_count += 1
        else:
            post.category = item["category"]
            post.price = item["price"]
            post.content = item["content"]
            post.contact_name = item["contact_name"]
            post.contact_phone = item["contact_phone"]
            post.attributes = item["attributes"]
            updated_count += 1

        created_at = now - timedelta(days=item["age_days"])
        post.status = item["status"]
        post.reject_reason = item["reject_reason"]
        post.is_top = item["is_top"]
        post.view_count = item["view_count"]
        post.created_at = created_at
        post.updated_at = created_at
        post.approved_at = (
            created_at if item["status"] == InformationStatus.APPROVED else None
        )

    db.flush()
    print(f"  信息发布已创建 {created_count} 条、更新 {updated_count} 条演示记录")


def _current_publisher_verification(
    db, publisher: User
) -> PublisherVerification | None:
    rows = (
        db.query(PublisherVerification)
        .filter(PublisherVerification.user_id == publisher.id)
        .order_by(
            PublisherVerification.submitted_at.desc(),
            PublisherVerification.id.desc(),
        )
        .all()
    )
    return next(
        (
            row
            for row in rows
            if information_service.is_verification_currently_valid(row)
        ),
        None,
    )


def _ensure_compliance_information_posts(
    db, publisher: User
) -> list[InformationPost]:
    verification = _current_publisher_verification(db, publisher)
    if verification is None:
        print(
            "  信息发布暂未创建：请先用账号「互动递归」提交实名材料，"
            "并由管理员在后台审核通过"
        )
        return []

    posts: list[InformationPost] = []
    created_count = 0
    updated_count = 0
    for item in _compliance_information_catalog():
        post = (
            db.query(InformationPost)
            .filter(
                InformationPost.title == item["title"],
                InformationPost.poster_user_id == publisher.id,
            )
            .first()
        )
        if post is None:
            post = InformationPostDAO(db).create(
                title=item["title"],
                category=item["category"],
                content=item["content"],
                contact_name=item["contact_name"],
                contact_phone=item["contact_phone"],
                poster_user_id=publisher.id,
                price=item["price"],
                attributes=item["attributes"],
                publisher_verification_id=verification.id,
            )
            created_count += 1
        else:
            post.category = item["category"]
            post.price = item["price"]
            post.content = item["content"]
            post.contact_name = item["contact_name"]
            post.contact_phone = item["contact_phone"]
            post.attributes = item["attributes"]
            post.publisher_verification_id = verification.id
            updated_count += 1
        posts.append(post)
    db.flush()
    print(
        f"  信息发布已创建 {created_count} 条、更新 {updated_count} 条；"
        "全部保留为独立信息"
    )
    return posts


def _ensure_compliance_buyer(db) -> User:
    return _ensure_user(
        db,
        username=BUYER_USERNAME,
        password=BUYER_PASSWORD,
        email=BUYER_EMAIL,
        phone=BUYER_PHONE,
        role="user",
        display_name="整改测试买家",
    )


def _accept_current_documents_for_seeded_user(db, user: User) -> None:
    status = auth_transactions.current_acceptance_status(db, user.id)
    if status["all_current_accepted"]:
        return
    auth_transactions.record_user_acceptances(
        db,
        user_id=user.id,
        user_agreement_version=status["user_agreement_version"],
        privacy_policy_version=status["privacy_policy_version"],
        client_ip=None,
        user_agent="seed_mall compliance setup (operator confirmed)",
    )
    print(f"  账号「{user.username}」已确认当前用户协议与隐私政策")


def _compliance_seed_reviewer(db) -> User:
    reviewer = next(
        (
            user
            for user in UserDAO(db).list_all()
            if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
        ),
        None,
    )
    if reviewer is None:
        raise RuntimeError("缺少管理员账号，无法完成整改 Seed 审核流程")
    return reviewer


def _complete_seeded_publisher_verification(
    db, publisher: User, *, reviewer: User
) -> PublisherVerification | None:
    verification = _current_publisher_verification(db, publisher)
    if verification is not None:
        return verification
    verification = (
        db.query(PublisherVerification)
        .filter(
            PublisherVerification.user_id == publisher.id,
            PublisherVerification.status == PublisherVerificationStatus.PENDING,
        )
        .order_by(
            PublisherVerification.submitted_at.desc(),
            PublisherVerification.id.desc(),
        )
        .first()
    )
    if verification is None:
        return None
    information_service.review_verification(
        db,
        verification.id,
        approved=True,
        reject_reason=None,
        reviewer_user_id=reviewer.id,
    )
    print("  已自动通过发布者实名认证")
    return verification


def _complete_seeded_shop_onboarding(
    db,
    merchant: User,
    inputs: ComplianceApplicationInputs,
    *,
    reviewer: User,
) -> Shop | None:
    shop = ShopDAO(db).get_by_owner(merchant.id)
    if shop is None:
        return None
    if shop.onboarding_stage == ShopOnboardingStage.QUALIFICATION_SUBMITTED.value:
        if inputs.merchant_business_license_path is None:
            print("  商家自动审核尚未完成：请带营业执照参数重新运行 Seed")
            return shop
        evidence_asset_id = _ingest_compliance_asset(
            db,
            owner=reviewer,
            purpose="merchant_registry_review_evidence",
            source_path=inputs.merchant_business_license_path,
        )
        service.admin_review_shop(
            db,
            shop.id,
            payload={
                "approved": True,
                "evidence_asset_id": evidence_asset_id,
                "verification_source": "整改 Seed：平台负责人已确认企业登记及资质信息",
                "registration_status": "存续",
                "entity_name_matches": True,
                "credit_code_matches": True,
                "legal_representative_matches": True,
                "registration_status_valid": True,
                "registered_address_matches": True,
                "business_scope_matches": True,
                "special_license_scope_allowed": True,
                "note": "平台负责人执行整改 Seed，并确认该商家资质审核通过。",
                "reject_reason": None,
            },
            handler_user_id=reviewer.id,
        )
        print("  已自动通过商家资质预审并生成电子协议")

    if shop.onboarding_stage == ShopOnboardingStage.AGREEMENT_GENERATED.value:
        agreement = service.admin_get_shop_agreement(db, shop.id)
        service.merchant_accept_shop_agreement(
            db,
            _principal_for_seller(
                merchant,
                username=merchant.username,
                email=merchant.email,
            ),
            {
                "agreement_number": agreement.agreement_number,
                "document_version": agreement.document_version,
                "draft_content_sha256": agreement.draft_content_sha256,
                "confirmed": True,
            },
            client_ip=None,
            user_agent="seed_mall compliance workflow (operator confirmed)",
        )
        print("  已自动完成商家电子协议签署与归档")

    if shop.onboarding_stage == ShopOnboardingStage.AGREEMENT_ARCHIVED.value:
        service.admin_approve_shop(db, shop.id)
        print("  已自动完成商家最终审核并开通店铺")
    return shop


def _seed_compliance(
    db,
    *,
    assets: dict[str, list[str]],
    application_inputs: ComplianceApplicationInputs | None = None,
    auto_complete_compliance_workflow: bool = True,
) -> None:
    category_map = _ensure_categories(db, MERCHANT_A_CATEGORIES)
    _ensure_compliance_buyer(db)
    merchant = _ensure_user(
        db,
        username=COMPLIANCE_MERCHANT_USERNAME,
        password=COMPLIANCE_MERCHANT_PASSWORD,
        email=COMPLIANCE_MERCHANT_EMAIL,
        phone=None,
        role="user",
        display_name=COMPLIANCE_MERCHANT_NAME,
    )
    publisher = _ensure_user(
        db,
        username=COMPLIANCE_PUBLISHER_USERNAME,
        password=COMPLIANCE_PUBLISHER_PASSWORD,
        email=COMPLIANCE_PUBLISHER_EMAIL,
        phone=COMPLIANCE_PUBLISHER_PHONE,
        role="user",
        display_name=COMPLIANCE_PUBLISHER_REAL_NAME,
    )

    inputs = application_inputs or ComplianceApplicationInputs()
    if auto_complete_compliance_workflow:
        if inputs.merchant_business_license_path is not None:
            _accept_current_documents_for_seeded_user(db, merchant)
        if inputs.publisher_identity_front_path is not None:
            _accept_current_documents_for_seeded_user(db, publisher)
    _ensure_compliance_shop_application(db, merchant, inputs)
    _ensure_publisher_verification_application(db, publisher, inputs)

    reviewer = None
    if auto_complete_compliance_workflow and (
        ShopDAO(db).get_by_owner(merchant.id) is not None
        or db.query(PublisherVerification)
        .filter(PublisherVerification.user_id == publisher.id)
        .first()
        is not None
    ):
        reviewer = _compliance_seed_reviewer(db)
        _complete_seeded_publisher_verification(
            db,
            publisher,
            reviewer=reviewer,
        )
        _complete_seeded_shop_onboarding(
            db,
            merchant,
            inputs,
            reviewer=reviewer,
        )

    shop = ShopDAO(db).get_by_owner(merchant.id)
    goods_list: list[Goods] = []
    if shop is None:
        print(
            "  商家商品暂未创建：请先用账号「hddg」提交真实企业资质，"
            "完成平台预审、在线签约和最终审核"
        )
    elif not service.is_shop_operational(shop):
        print(
            f"  店铺「{shop.name}」尚未完成最终审核，暂不上架商品；"
            f"当前阶段：{shop.onboarding_stage}"
        )
    else:
        shop.name = COMPLIANCE_SHOP_NAME
        shop.description = COMPLIANCE_SHOP_DESCRIPTION
        shop.avatar = "/mall/shop-avatar.svg"
        goods_list = _seed_goods(
            db,
            seller=merchant,
            shop_id=shop.id,
            category_map=category_map,
            assets={**ASSET_URLS, **COMPLIANCE_ASSET_URLS, **assets},
            goods=_merchant_a_goods_catalog(),
            seed_sales=False,
        )
        print(
            f"  店铺「{shop.name}」已就绪：{len(goods_list)} 个在售商品"
            "（含原商城普通商品）"
        )

    posts = _ensure_compliance_information_posts(db, publisher)
    posts_requiring_review = [
        post for post in posts if post.status != InformationStatus.APPROVED
    ]
    if auto_complete_compliance_workflow and posts_requiring_review:
        reviewer = reviewer or _compliance_seed_reviewer(db)
        for post in posts_requiring_review:
            information_service.admin_review(
                db,
                post.id,
                approved=True,
                reject_reason=None,
                reviewer_user_id=reviewer.id,
            )
        print(f"  已自动通过 {len(posts_requiring_review)} 条信息发布审核")
    if auto_complete_compliance_workflow and reviewer is not None:
        verification = _current_publisher_verification(db, publisher)
        if verification is not None:
            _ensure_compliance_audit_event(
                db,
                actor=reviewer,
                action="information.publisher_verification.review",
                action_label="审核发布者实名",
                resource_type="publisher_verification",
                resource_id=verification.id,
                target_summary=f"发布者 {publisher.username}（{verification.real_name}）",
                detail={"approved": True},
            )
        if shop is not None and shop.platform_verified:
            _ensure_compliance_audit_event(
                db,
                actor=reviewer,
                action="mall.shop.qualification.pre_review",
                action_label="商家资质预审",
                resource_type="shop",
                resource_id=shop.id,
                target_summary=f"店铺 {shop.name}",
                detail={"approved": True},
            )
            agreement = (
                db.query(ShopAgreement)
                .filter(ShopAgreement.shop_id == shop.id)
                .order_by(ShopAgreement.id.desc())
                .first()
            )
            if agreement is not None and agreement.merchant_signed_at is not None:
                _ensure_compliance_audit_event(
                    db,
                    actor=merchant,
                    action="mall.shop.agreement.accept",
                    action_label="商家确认电子协议",
                    resource_type="shop_agreement",
                    resource_id=agreement.id,
                    target_summary=f"协议 {agreement.agreement_number}",
                    detail={"signature_mode": agreement.signature_mode},
                )
            if shop.status == ShopStatus.APPROVED:
                _ensure_compliance_audit_event(
                    db,
                    actor=reviewer,
                    action="mall.shop.approve",
                    action_label="商家最终审核通过",
                    resource_type="shop",
                    resource_id=shop.id,
                    target_summary=f"店铺 {shop.name}",
                    detail={"approved": True},
                )
        for post in posts:
            if post.status == InformationStatus.APPROVED:
                _ensure_compliance_audit_event(
                    db,
                    actor=reviewer,
                    action="information.post.review",
                    action_label="审核信息发布",
                    resource_type="information",
                    resource_id=post.id,
                    target_summary=post.title,
                    detail={"approved": True},
                )
    print("整改取证种子数据已准备。")
    print("  商家账号：hddg（密码仅在首次创建账号时设置）")
    print("  发布者账号：互动递归（密码仅在首次创建账号时设置）")
    print("  普通测试账号：buyer（密码仅在首次创建账号时设置）")
    print(f"  已上架商品：{len(goods_list)}")
    print(f"  已准备信息发布：{len(posts)}")
    if auto_complete_compliance_workflow:
        print("  已按 Seed 确认自动执行可完成的审核、签约、开店及信息发布流程")
    else:
        print("  审核、签约、最终开店及信息发布审核必须在网站后台人工完成")


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
        if eval_dao.list_by_goods(goods.id, page=1, page_size=1)[1]:
            continue
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


def _seed_demo(db, *, assets: dict[str, list[str]]) -> None:
    category_map = _ensure_categories(db)
    buyer = _ensure_buyer(db)

    for shop_cfg in SHOPS:
        seller = _ensure_user(
            db,
            username=shop_cfg["username"],
            password=shop_cfg["password"],
            email=shop_cfg["email"],
            phone=shop_cfg["phone"],
            role="user",
        )
        shop = _ensure_demo_shop(
            db, seller, name=shop_cfg["name"], description=shop_cfg["description"]
        )
        shop_goods = [
            item
            for item in GOODS
            if item["category"] in shop_cfg["categories"]
            and item["category"] not in RESTRICTED_CATEGORY_NAMES
        ]
        goods_list = _seed_goods(
            db,
            seller=seller,
            shop_id=shop.id,
            category_map=category_map,
            assets=assets,
            goods=shop_goods,
        )
        _seed_evaluations(db, buyer=buyer, shop=shop, goods_list=goods_list)
        print(f"  店铺「{shop.name}」已就绪：{len(goods_list)} 个在售商品")

    _seed_information_posts(db)
    total_goods = sum(
        1
        for item in GOODS
        if item["category"] in {c for s in SHOPS for c in s["categories"]}
    )
    print("种子数据就绪。")
    print(f"  店铺数量：{len(SHOPS)}")
    print(f"  商品数量：{total_goods}")
    print(f"  信息发布数量：{len(INFORMATION_POSTS)}")
    if assets:
        print(f"  KiVault 图片清单：{len(assets)} 个商品")
    else:
        print("  商品图片：当前使用本地占位图")


def _reset(db) -> None:
    db.execute(
        text(
            "UPDATE mall_shops SET current_agreement_id = NULL, "
            "last_qualification_review_id = NULL"
        )
    )
    db.execute(
        text(
            "DELETE FROM file_asset_references "
            "WHERE resource_type IN "
            "('shop_agreement', 'shop_qualification', 'shop_qualification_review')"
        )
    )
    tables = [
        "information_posts",
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
        "shop_agreements",
        "shop_qualification_reviews",
        "mall_shops",
        "mall_categories",
    ]
    for table in tables:
        db.execute(text(f'DELETE FROM "{table}"'))
    print("已清空商城数据。")


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须使用 YYYY-MM-DD 格式") from exc


def _masked_input_from_terminal(terminal: TextIO, prompt: str) -> str:
    descriptor = terminal.fileno()
    original_attributes = termios.tcgetattr(descriptor)
    masked_attributes = list(original_attributes)
    masked_attributes[6] = list(original_attributes[6])
    masked_attributes[3] &= ~(termios.ECHO | termios.ICANON)
    masked_attributes[6][termios.VMIN] = 1
    masked_attributes[6][termios.VTIME] = 0
    characters: list[str] = []

    terminal.write(prompt)
    terminal.flush()
    termios.tcsetattr(descriptor, termios.TCSAFLUSH, masked_attributes)
    try:
        while True:
            character = terminal.read(1)
            if character in {"\r", "\n"}:
                break
            if character in {"\b", "\x7f"}:
                if characters:
                    characters.pop()
                    terminal.write("\b \b")
                    terminal.flush()
                continue
            if character == "\x04":
                if not characters:
                    raise EOFError
                break
            if not character or ord(character) < 32:
                continue
            characters.append(character)
            terminal.write("*")
            terminal.flush()
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, original_attributes)
        terminal.write("\n")
        terminal.flush()
    return "".join(characters)


def _masked_input(prompt: str) -> str:
    try:
        with Path("/dev/tty").open("r+", encoding="utf-8") as terminal:
            return _masked_input_from_terminal(terminal, prompt)
    except (OSError, termios.error):
        return getpass.getpass(prompt)


def _application_inputs_from_args(
    args: argparse.Namespace,
) -> ComplianceApplicationInputs:
    merchant_paths = (
        args.merchant_business_license,
        args.merchant_id_front,
        args.merchant_id_back,
    )
    merchant_requested = any(path is not None for path in merchant_paths)
    if merchant_requested and not all(path is not None for path in merchant_paths):
        raise SystemExit("提交商家资质时必须同时提供营业执照和负责人身份证正反面")
    if merchant_requested and not args.merchant_applicant_name:
        raise SystemExit("提交商家资质时必须提供 --merchant-applicant-name")
    if args.merchant_authorization is not None and not merchant_requested:
        raise SystemExit("授权委托书必须与完整商家资质材料一起提交")
    if (
        merchant_requested
        and args.merchant_applicant_name != COMPLIANCE_MERCHANT_LEGAL_REPRESENTATIVE
        and args.merchant_authorization is None
    ):
        raise SystemExit(
            "商家负责人不是营业执照法定代表人时，必须提供 --merchant-authorization"
        )
    if merchant_requested and not (
        args.merchant_license_long_term or args.merchant_license_valid_until
    ):
        raise SystemExit(
            "请提供 --merchant-license-valid-until，或确认 --merchant-license-long-term"
        )

    publisher_paths = (args.publisher_id_front, args.publisher_id_back)
    publisher_requested = any(path is not None for path in publisher_paths)
    if publisher_requested and not all(path is not None for path in publisher_paths):
        raise SystemExit("提交发布者实名时必须同时提供身份证正反面")
    if publisher_requested and not (
        args.publisher_id_long_term or args.publisher_id_valid_until
    ):
        raise SystemExit(
            "请提供 --publisher-id-valid-until，或确认 --publisher-id-long-term"
        )

    merchant_identity_number = None
    if merchant_requested:
        merchant_identity_number = os.getenv("MALL_SEED_MERCHANT_ID_NUMBER")
        if not merchant_identity_number:
            merchant_identity_number = _masked_input(
                "商家负责人身份证号码（输入以 * 显示）："
            ).strip()
        if not merchant_identity_number:
            raise SystemExit("商家负责人身份证号码不能为空")

    publisher_identity_number = None
    if publisher_requested:
        publisher_identity_number = os.getenv("MALL_SEED_PUBLISHER_ID_NUMBER")
        if not publisher_identity_number:
            publisher_identity_number = _masked_input(
                "信息发布者身份证号码（输入以 * 显示）："
            ).strip()
        if not publisher_identity_number:
            raise SystemExit("信息发布者身份证号码不能为空")

    return ComplianceApplicationInputs(
        merchant_business_license_path=args.merchant_business_license,
        merchant_identity_front_path=args.merchant_id_front,
        merchant_identity_back_path=args.merchant_id_back,
        merchant_authorization_path=args.merchant_authorization,
        merchant_identity_number=merchant_identity_number,
        merchant_applicant_name=args.merchant_applicant_name,
        merchant_business_address=args.merchant_business_address,
        merchant_contact_phone=args.merchant_contact_phone,
        merchant_license_valid_until=args.merchant_license_valid_until,
        merchant_license_long_term=args.merchant_license_long_term,
        publisher_identity_front_path=args.publisher_id_front,
        publisher_identity_back_path=args.publisher_id_back,
        publisher_identity_number=publisher_identity_number,
        publisher_document_valid_until=args.publisher_id_valid_until,
        publisher_document_long_term=args.publisher_id_long_term,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="商城种子数据")
    parser.add_argument(
        "--profile",
        choices=("compliance", "demo"),
        default="compliance",
        help="compliance 准备整改取证数据；demo 生成开发演示数据",
    )
    parser.add_argument("--reset", action="store_true", help="先清空商城数据再填充")
    parser.add_argument(
        "--confirm-production",
        default="",
        metavar="DOMAIN",
        help="生产环境必须明确填写目标域名；当前仅接受 hemu.site",
    )
    parser.add_argument(
        "--auto-accept-current-legal-documents",
        action="store_true",
        help=(
            "兼容旧调用；整改 Seed 传入真实材料后已默认自动确认协议并完成流程"
        ),
    )
    parser.add_argument("--merchant-business-license", type=Path)
    parser.add_argument("--merchant-id-front", type=Path)
    parser.add_argument("--merchant-id-back", type=Path)
    parser.add_argument("--merchant-authorization", type=Path)
    parser.add_argument("--merchant-applicant-name")
    parser.add_argument(
        "--merchant-business-address",
        default=COMPLIANCE_MERCHANT_REGISTERED_ADDRESS,
    )
    parser.add_argument(
        "--merchant-contact-phone",
        default=COMPLIANCE_MERCHANT_DEFAULT_CONTACT_PHONE,
    )
    merchant_validity = parser.add_mutually_exclusive_group()
    merchant_validity.add_argument("--merchant-license-valid-until", type=_iso_date)
    merchant_validity.add_argument("--merchant-license-long-term", action="store_true")
    parser.add_argument("--publisher-id-front", type=Path)
    parser.add_argument("--publisher-id-back", type=Path)
    publisher_validity = parser.add_mutually_exclusive_group()
    publisher_validity.add_argument("--publisher-id-valid-until", type=_iso_date)
    publisher_validity.add_argument("--publisher-id-long-term", action="store_true")
    args = parser.parse_args()

    is_development = global_config.app.env in {"dev", "test"}
    if args.profile == "demo" and not is_development:
        raise SystemExit("商城演示数据仅允许在 dev/test 环境运行")
    if not is_development and args.confirm_production != "hemu.site":
        raise SystemExit(
            "生产环境运行整改种子前必须添加 --confirm-production hemu.site"
        )
    application_inputs = _application_inputs_from_args(args)

    def _job(db) -> None:
        if args.reset:
            _reset(db)
        if args.profile == "demo":
            _seed_demo(db, assets=ASSET_URLS)
        else:
            _seed_compliance(
                db,
                assets={},
                application_inputs=application_inputs,
            )

    run_in_new_session(_job)


if __name__ == "__main__":
    main()
