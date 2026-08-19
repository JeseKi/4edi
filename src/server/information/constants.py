# -*- coding: utf-8 -*-
"""信息发布分类元数据。

分类沿用参考站 https://ljmzj.cn/information/ 的四大类；
``attributes`` 为各分类的发布表单字段定义（属性表在详情页渲染）。
"""

from __future__ import annotations

from typing import Any

#: 分类 key -> 元数据；attributes 中 type 缺省为 "select"。
INFORMATION_CATEGORIES: dict[str, dict[str, Any]] = {
    "mini_program": {
        "name": "小程序开发",
        "attributes": [
            {"key": "dev_method", "label": "开发方式", "type": "select",
             "options": ["原生开发", "混合开发", "模板开发"]},
            {"key": "secondary_dev", "label": "是否二次开发", "type": "select",
             "options": ["是", "否"]},
            {"key": "industry", "label": "适用行业", "type": "text"},
            {"key": "language", "label": "开发语言", "type": "text"},
            {"key": "database", "label": "数据库", "type": "text"},
        ],
    },
    "app": {
        "name": "APP开发",
        "attributes": [
            {"key": "dev_method", "label": "开发方式", "type": "select",
             "options": ["原生开发", "混合开发"]},
            {"key": "secondary_dev", "label": "是否二次开发", "type": "select",
             "options": ["是", "否"]},
            {"key": "platform", "label": "支持平台", "type": "select",
             "options": ["iOS", "Android", "跨平台"]},
            {"key": "industry", "label": "适用行业", "type": "text"},
            {"key": "language", "label": "开发语言", "type": "text"},
        ],
    },
    "software": {
        "name": "软件开发",
        "attributes": [
            {"key": "language", "label": "开发语言", "type": "text"},
            {"key": "platform", "label": "系统平台", "type": "select",
             "options": ["Windows", "Linux", "macOS", "Web"]},
            {"key": "deliverable", "label": "交付形式", "type": "select",
             "options": ["源码", "成品", "定制开发"]},
            {"key": "function", "label": "主要功能", "type": "textarea"},
        ],
    },
    "website": {
        "name": "网站建设",
        "attributes": [
            {"key": "site_type", "label": "网站类型", "type": "select",
             "options": ["企业官网", "电商商城", "门户网站", "营销落地页"]},
            {"key": "responsive", "label": "响应式", "type": "select",
             "options": ["是", "否"]},
            {"key": "backend", "label": "后端技术", "type": "text"},
            {"key": "deliverable", "label": "交付形式", "type": "select",
             "options": ["源码", "成品", "定制开发"]},
        ],
    },
}

CATEGORY_KEYS = tuple(INFORMATION_CATEGORIES.keys())


def category_def(key: str) -> dict[str, Any] | None:
    """按 key 返回分类元数据；未知 key 返回 None。"""
    return INFORMATION_CATEGORIES.get(key)


def category_name(key: str) -> str:
    """返回分类中文名；未知 key 原样返回。"""
    info = INFORMATION_CATEGORIES.get(key)
    return info["name"] if info else key
