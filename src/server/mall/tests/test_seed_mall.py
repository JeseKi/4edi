"""商城演示数据初始化回归测试。"""

from __future__ import annotations

from scripts import seed_mall
from src.server.mall.dao import CategoryDAO
from src.server.mall.models import ShopQualificationReview
from src.server.mall.service import short_transactions as mall_service


def test_seed_shop_has_current_qualification_before_goods_are_created(
    test_db_session, init_test_database
):
    seller = seed_mall._ensure_user(
        test_db_session,
        username="seed-regression-seller",
        password="seller123",
        email="seed-regression-seller@example.com",
        phone="13800009999",
        role="user",
    )
    shop = seed_mall._ensure_shop(
        test_db_session,
        seller,
        name="演示资质回归店铺",
        description="验证 Seed 创建商品前已补齐资质审核记录",
    )

    assert shop.platform_verified is True
    assert shop.last_qualification_review_id is not None
    review = test_db_session.get(
        ShopQualificationReview, shop.last_qualification_review_id
    )
    assert review is not None
    assert review.result == "preapproved"

    same_shop = seed_mall._ensure_shop(
        test_db_session,
        seller,
        name="演示资质回归店铺",
        description="验证 Seed 重复执行不会制造重复审核记录",
    )
    assert same_shop.id == shop.id
    assert same_shop.last_qualification_review_id == review.id
    assert (
        test_db_session.query(ShopQualificationReview)
        .filter(ShopQualificationReview.shop_id == shop.id)
        .count()
        == 1
    )

    category = CategoryDAO(test_db_session).create(
        name="演示开放类目",
        parent_id=None,
        sort=0,
        icon=None,
        requires_special_license=False,
    )
    goods = mall_service.create_goods(
        test_db_session,
        seed_mall._principal_for_seller(
            seller, username=seller.username, email=seller.email
        ),
        {
            "category_id": category.id,
            "name": "Seed 资质回归商品",
            "main_image": "/mall/goods-1.svg",
            "images": ["/mall/goods-1.svg"],
            "detail": "用于验证商城演示数据脚本的商品",
            "original_price_fen": 19900,
            "skus": [
                {
                    "sku_code": "SEED-REGRESSION-1",
                    "specs": {"规格": "默认"},
                    "price_fen": 9900,
                    "stock": 10,
                }
            ],
        },
    )

    assert goods.shop_id == shop.id
