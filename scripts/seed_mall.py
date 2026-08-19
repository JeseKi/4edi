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

# 本轮新增的 20 个商品。图片均由 KiVault 公共图床托管，便于演示环境直接访问。
GOODS.extend(
    [
        {"slug": "garment-steamer", "category": "家居日用", "name": "SteamGo 便携手持挂烫机 旅行小型除皱", "fallback_image": "/mall/goods-1.svg", "original_price_fen": 21900, "detail": "轻巧手持设计，预热后可用于衬衫、针织物等日常衣物的快速除皱。可拆卸水箱便于补水，旅行和宿舍收纳更省空间。使用时请保持衣物平整，并避开不耐高温面料。", "skus": [{"sku_code": "SG-CREAM", "specs": {"颜色": "奶油白"}, "price_fen": 15900, "stock": 68}, {"sku_code": "SG-GRAY", "specs": {"颜色": "雾灰"}, "price_fen": 15900, "stock": 56}]},
        {"slug": "open-ear-earbuds", "category": "手机通讯", "name": "OpenBeat 开放式运动蓝牙耳机 低延迟长续航", "fallback_image": "/mall/goods-2.svg", "original_price_fen": 45900, "detail": "开放式耳挂结构让双耳保持环境感知，适合通勤、骑行与轻运动。定向声学单元配合双麦通话降噪，充电盒可提供额外续航。日常防汗防泼溅，运动后请擦干再收纳。", "skus": [{"sku_code": "OB-BLACK", "specs": {"颜色": "曜石黑"}, "price_fen": 32900, "stock": 72}, {"sku_code": "OB-BEIGE", "specs": {"颜色": "沙岩米"}, "price_fen": 33900, "stock": 45}]},
        {"slug": "magnetic-power-bank", "category": "手机通讯", "name": "MagCharge 10000mAh 磁吸无线充电宝 轻薄快充", "fallback_image": "/mall/goods-3.svg", "original_price_fen": 26900, "detail": "10000mAh 容量的轻薄磁吸充电宝，可为兼容设备提供无线充电，也支持 USB-C 有线输出。磨砂铝合金外壳耐日常刮擦，出行前建议为本品充满电。实际可用容量受设备与使用环境影响。", "skus": [{"sku_code": "MC-NAVY", "specs": {"颜色": "深海蓝"}, "price_fen": 19900, "stock": 88}, {"sku_code": "MC-SILVER", "specs": {"颜色": "银灰"}, "price_fen": 19900, "stock": 75}]},
        {"slug": "usb-c-hub", "category": "电脑办公", "name": "DockMini 7 合 1 USB-C 扩展坞 HDMI 读卡器", "fallback_image": "/mall/goods-4.svg", "original_price_fen": 19900, "detail": "为 USB-C 设备扩展 HDMI、USB-A、USB-C 与 SD/microSD 读卡接口的小型扩展坞。铝合金机身便于携带，适合会议投屏和移动办公。请确认设备 USB-C 接口支持所需的视频输出协议。", "skus": [{"sku_code": "DM-GRAY", "specs": {"颜色": "深空灰"}, "price_fen": 13900, "stock": 96}]},
        {"slug": "scented-candle", "category": "家居日用", "name": "暮木香氛蜡烛 180g 岩兰草檀木调", "fallback_image": "/mall/goods-1.svg", "original_price_fen": 15900, "detail": "温暖木质香调香氛蜡烛，陶瓷杯搭配防尘盖，适合卧室、书房与休闲时刻。首次点燃建议使表层蜡充分融化以获得更均匀的燃烧效果。请置于平稳耐热表面并远离儿童和可燃物。", "skus": [{"sku_code": "CANDLE-SANDAL", "specs": {"香型": "岩兰草檀木"}, "price_fen": 10900, "stock": 110}, {"sku_code": "CANDLE-FIG", "specs": {"香型": "无花果绿叶"}, "price_fen": 10900, "stock": 90}]},
        {"slug": "lunch-tote", "category": "家居日用", "name": "FreshDay 加厚保温午餐包 大容量便携饭盒袋", "fallback_image": "/mall/goods-2.svg", "original_price_fen": 9900, "detail": "加厚保温层搭配拉链主仓，可容纳常见饭盒、水果与饮品。外层耐磨易清洁，双提手携带轻松。保温效果受环境与装入食物温度影响，建议与冰袋或保温容器搭配使用。", "skus": [{"sku_code": "FD-SAGE", "specs": {"颜色": "鼠尾草绿"}, "price_fen": 6900, "stock": 150}, {"sku_code": "FD-BEIGE", "specs": {"颜色": "燕麦米"}, "price_fen": 6900, "stock": 130}]},
        {"slug": "travel-umbrella", "category": "户外装备", "name": "WindLite 轻量折叠晴雨伞 防晒防泼水", "fallback_image": "/mall/goods-3.svg", "original_price_fen": 8900, "detail": "轻量三折伞骨结合防泼水伞布，折叠后可放入通勤包侧袋。伞面提供日常遮阳与挡雨能力，遇强风天气请注意使用安全。收伞后建议晾干再放入收纳套。", "skus": [{"sku_code": "WL-BLACK", "specs": {"颜色": "曜石黑"}, "price_fen": 5900, "stock": 180}, {"sku_code": "WL-BLUE", "specs": {"颜色": "雾蓝"}, "price_fen": 5900, "stock": 140}]},
        {"slug": "coffee-grinder", "category": "家居日用", "name": "GrindCraft 手摇咖啡磨豆机 陶瓷芯可调粗细", "fallback_image": "/mall/goods-4.svg", "original_price_fen": 18900, "detail": "不锈钢机身与木质握柄兼具耐用和手感，陶瓷磨芯支持调节研磨粗细，适合手冲、法压等日常冲煮方式。首次使用前请清洁研磨仓，研磨后保持干燥避免水洗磨芯。", "skus": [{"sku_code": "GC-WALNUT", "specs": {"木纹": "胡桃木色"}, "price_fen": 12900, "stock": 64}]},
        {"slug": "knit-throw", "category": "家居日用", "name": "CozyWeave 针织盖毯 130×170cm 柔软保暖", "fallback_image": "/mall/goods-1.svg", "original_price_fen": 19900, "detail": "细密罗纹针织毯，适合沙发午休、空调房与居家阅读。柔软混纺面料有自然垂坠感，简约色调便于融入不同家居风格。建议冷水轻柔洗涤并平铺晾干。", "skus": [{"sku_code": "CW-OAT", "specs": {"颜色": "燕麦色"}, "price_fen": 14900, "stock": 80}, {"sku_code": "CW-GRAY", "specs": {"颜色": "烟灰色"}, "price_fen": 14900, "stock": 70}]},
        {"slug": "crossbody-bag", "category": "女装", "name": "Mellow 半月斜挎包 轻量通勤小方包", "fallback_image": "/mall/goods-2.svg", "original_price_fen": 23900, "detail": "半月轮廓的小巧斜挎包，采用细腻纹理面料与可调节肩带，容纳手机、卡包、钥匙等出门随身物品。内置分隔袋方便收纳，日常清洁请使用微湿软布轻擦。", "skus": [{"sku_code": "MELLOW-NAVY", "specs": {"颜色": "海军蓝"}, "price_fen": 16900, "stock": 76}, {"sku_code": "MELLOW-BROWN", "specs": {"颜色": "焦糖棕"}, "price_fen": 16900, "stock": 66}]},
        {"slug": "cotton-tshirt", "category": "男装", "name": "Everyday 260g 男士重磅纯棉短袖 T 恤", "fallback_image": "/mall/goods-3.svg", "original_price_fen": 12900, "detail": "260g 纯棉面料打造挺括基础版型，圆领与落肩剪裁便于单穿或作内搭。无夸张图案，适合日常通勤与休闲搭配。建议反面冷水洗涤，深浅色分开，避免高温烘干。", "skus": [{"sku_code": "ED-CHARCOAL-M", "specs": {"颜色": "炭灰", "尺码": "M"}, "price_fen": 8900, "stock": 90}, {"sku_code": "ED-CHARCOAL-L", "specs": {"颜色": "炭灰", "尺码": "L"}, "price_fen": 8900, "stock": 100}, {"sku_code": "ED-WHITE-L", "specs": {"颜色": "暖白", "尺码": "L"}, "price_fen": 8900, "stock": 85}]},
        {"slug": "yoga-leggings", "category": "女装", "name": "FlexMove 女士高腰瑜伽裤 弹力速干运动紧身裤", "fallback_image": "/mall/goods-4.svg", "original_price_fen": 17900, "detail": "高腰包裹与四面弹力面料兼顾日常训练的舒适度和活动自由度，面料具备速干特性。适合瑜伽、普拉提和轻度健身，建议使用洗衣袋冷水清洗，不与粗糙衣物混洗。", "skus": [{"sku_code": "FM-PLUM-S", "specs": {"颜色": "梅子紫", "尺码": "S"}, "price_fen": 12900, "stock": 65}, {"sku_code": "FM-PLUM-M", "specs": {"颜色": "梅子紫", "尺码": "M"}, "price_fen": 12900, "stock": 75}]},
        {"slug": "sports-bottle", "category": "户外装备", "name": "HydraLoop 750ml 运动水壶 防漏提环设计", "fallback_image": "/mall/goods-1.svg", "original_price_fen": 7900, "detail": "750ml 大容量运动水壶，旋盖配合硅胶密封圈降低漏水风险，提环方便跑步、徒步和健身携带。宽口便于清洗与放入冰块。首次使用前请充分清洗，不建议盛装高温液体。", "skus": [{"sku_code": "HL-ORANGE", "specs": {"颜色": "活力橙"}, "price_fen": 4900, "stock": 160}, {"sku_code": "HL-TEAL", "specs": {"颜色": "湖水绿"}, "price_fen": 4900, "stock": 140}]},
        {"slug": "foam-roller", "category": "户外装备", "name": "RecoverPro 按摩泡沫轴 33cm 深层放松筋膜", "fallback_image": "/mall/goods-2.svg", "original_price_fen": 10900, "detail": "高密度泡沫材质配合分区纹理，可用于运动前热身和运动后肌肉放松。33cm 长度方便收纳携带，适合腿部、背部等大肌群的自我按摩。请根据自身承受能力循序渐进使用。", "skus": [{"sku_code": "RP-TEAL", "specs": {"颜色": "深青绿"}, "price_fen": 7900, "stock": 98}]},
        {"slug": "bluetooth-speaker", "category": "手机通讯", "name": "PocketSound 迷你蓝牙音箱 户外便携低音增强", "fallback_image": "/mall/goods-3.svg", "original_price_fen": 16900, "detail": "掌心大小的便携蓝牙音箱，织物网罩与圆角机身便于随身携带。支持蓝牙连接和日常防泼溅，可用于桌面听歌、野餐和轻户外场景。实际续航会随音量与内容变化。", "skus": [{"sku_code": "PS-CORAL", "specs": {"颜色": "珊瑚红"}, "price_fen": 11900, "stock": 82}, {"sku_code": "PS-BLUE", "specs": {"颜色": "海盐蓝"}, "price_fen": 11900, "stock": 74}]},
        {"slug": "carry-on-suitcase", "category": "户外装备", "name": "TripShell 20 英寸登机拉杆箱 静音万向轮", "fallback_image": "/mall/goods-4.svg", "original_price_fen": 49900, "detail": "20 英寸硬壳登机箱，分区内里便于整理短途出行衣物，静音万向轮让移动更平稳。铝合金拉杆多档可调，密码锁使用前请阅读说明。不同航空公司的登机尺寸规定可能不同，请提前确认。", "skus": [{"sku_code": "TS-MUSTARD", "specs": {"颜色": "芥末黄"}, "price_fen": 35900, "stock": 42}, {"sku_code": "TS-BLACK", "specs": {"颜色": "曜石黑"}, "price_fen": 35900, "stock": 50}]},
        {"slug": "lint-remover", "category": "家居日用", "name": "CedarCare 实木除毛球器 可重复使用衣物清洁刷", "fallback_image": "/mall/goods-1.svg", "original_price_fen": 6900, "detail": "雪松木手柄搭配金属网面，可清理针织衫、毛呢外套和沙发织物表面的浮毛与毛球。无需电池，可重复使用。建议先在衣物不显眼处测试，并以轻柔单向动作操作。", "skus": [{"sku_code": "CC-CEDAR", "specs": {"材质": "雪松木柄"}, "price_fen": 4500, "stock": 140}]},
        {"slug": "ceramic-bowls", "category": "杯壶水具", "name": "日常白釉陶瓷面碗 2 只装 1100ml", "fallback_image": "/mall/goods-2.svg", "original_price_fen": 11900, "detail": "两只装大容量陶瓷面碗，细砂白釉外观简洁耐看，适合面食、沙拉和汤饭。加厚碗沿握持舒适，可用于日常餐桌。请避免骤冷骤热，清洗时轻拿轻放。", "skus": [{"sku_code": "BOWL-WHITE-2", "specs": {"规格": "1100ml×2"}, "price_fen": 7900, "stock": 120}]},
        {"slug": "kitchen-towels", "category": "家居日用", "name": "BambooSoft 竹纤维厨房抹布 3 条装 吸水不易掉屑", "fallback_image": "/mall/goods-3.svg", "original_price_fen": 5900, "detail": "三色组合厨房抹布，竹纤维混纺织物吸水性好、触感柔软，可用于擦拭台面、餐具和日常清洁。建议首次使用前清洗，使用后及时晾干并定期更换。", "skus": [{"sku_code": "BS-NEUTRAL-3", "specs": {"颜色": "中性色 3 条装"}, "price_fen": 3900, "stock": 220}]},
        {"slug": "precision-screwdriver", "category": "电脑办公", "name": "FixMate 精密螺丝刀套装 24 合 1 磁吸收纳盒", "fallback_image": "/mall/goods-4.svg", "original_price_fen": 13900, "detail": "24 合 1 精密螺丝刀套装，磁吸收纳盒内含常用批头与铝合金手柄，适合眼镜、小型数码设备和玩具的日常维护。拆装电子设备前请先断电，并确认操作不会影响保修。", "skus": [{"sku_code": "FM-24-GRAY", "specs": {"规格": "24 合 1"}, "price_fen": 9900, "stock": 105}]},
    ]
)


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
    "garment-steamer": ["https://fstc.kispace.cn/i/0c8300030f857b04a25e136f56c099a1.webp"],
    "open-ear-earbuds": ["https://fstc.kispace.cn/i/01b765638a193ca35f9705500b4221b4.webp"],
    "magnetic-power-bank": ["https://fstc.kispace.cn/i/de42c99da812b5ef969961009d69fdbb.webp"],
    "usb-c-hub": ["https://fstc.kispace.cn/i/9b1b6844beaf921d35dceee805abf520.webp"],
    "scented-candle": ["https://fstc.kispace.cn/i/ce5a17fb0f204507dab9995917749fc9.webp"],
    "lunch-tote": ["https://fstc.kispace.cn/i/54df066a8c27e5b6283b8e344ef2fd05.webp"],
    "travel-umbrella": ["https://fstc.kispace.cn/i/6b69a8a34765a51910eeb71290154e47.webp"],
    "coffee-grinder": ["https://fstc.kispace.cn/i/740a12ef54fa057cecafc666bce70ffb.webp"],
    "knit-throw": ["https://fstc.kispace.cn/i/e835f154589f0d071317d95e565576ac.webp"],
    "crossbody-bag": ["https://fstc.kispace.cn/i/60d843c70d4aaa40236532f033db9e84.webp"],
    "cotton-tshirt": ["https://fstc.kispace.cn/i/dbbc219f4fb95d59e4f25f63cd3fe486.webp"],
    "yoga-leggings": ["https://fstc.kispace.cn/i/7518e6ddddfe8ca934f25a337aaf27f2.webp"],
    "sports-bottle": ["https://fstc.kispace.cn/i/346254336cc0787cf95e13982c499f92.webp"],
    "foam-roller": ["https://fstc.kispace.cn/i/c1aeb59c87e872e6760faf4900d003e4.webp"],
    "bluetooth-speaker": ["https://fstc.kispace.cn/i/0041a82074eb5f48ab8059ce8e26ef75.webp"],
    "carry-on-suitcase": ["https://fstc.kispace.cn/i/9f5d67ba4391cbfbaf4dc49a2ce6656c.webp"],
    "lint-remover": ["https://fstc.kispace.cn/i/fc5c92b3d35596fbc7d8a2eec7b701bd.webp"],
    "ceramic-bowls": ["https://fstc.kispace.cn/i/d8e61f41a63066dae140d2a85ed1c8f2.webp"],
    "kitchen-towels": ["https://fstc.kispace.cn/i/a103bbb246331f12eed21e7e46aaabec.webp"],
    "precision-screwdriver": ["https://fstc.kispace.cn/i/a449495100834b1a81aa4234326f9361.webp"],
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
