"""商城种子数据初始化回归测试。"""

from __future__ import annotations

from datetime import date
import termios

from scripts import seed_mall
from src.server.auth.dao import UserDAO
from src.server.auth.models import LegalAcceptance
from src.server.config import global_config
from src.server.files.models import FileAsset
from src.server.information.models import (
    InformationPost,
    InformationStatus,
    PublisherVerification,
    PublisherVerificationStatus,
)
from src.server.information.tests._compliance_helpers import qualify_user_in_db
from src.server.mall.dao import CategoryDAO
from src.server.mall.models import (
    Goods,
    Shop,
    ShopAgreement,
    ShopAgreementStatus,
    ShopOnboardingStage,
    ShopQualificationReview,
    ShopStatus,
)
from src.server.mall.service import short_transactions as mall_service


class _FakeTerminal:
    def __init__(self, characters: str) -> None:
        self._characters = iter(characters)
        self.output = ""

    def fileno(self) -> int:
        return 42

    def read(self, _size: int) -> str:
        return next(self._characters)

    def write(self, value: str) -> None:
        self.output += value

    def flush(self) -> None:
        pass


def test_masked_terminal_input_echoes_asterisks_and_handles_backspace(monkeypatch):
    terminal = _FakeTerminal("12\x7f3\n")
    original = [0, 0, 0, termios.ECHO | termios.ICANON, 0, 0, [0] * 32]
    applied: list[list] = []
    monkeypatch.setattr(termios, "tcgetattr", lambda _fd: original)
    monkeypatch.setattr(
        termios,
        "tcsetattr",
        lambda _fd, _when, attributes: applied.append(attributes),
    )

    value = seed_mall._masked_input_from_terminal(terminal, "身份证号码：")

    assert value == "13"
    assert terminal.output == "身份证号码：**\b \b*\n"
    assert len(applied) == 2
    assert applied[-1] is original


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
    shop = seed_mall._ensure_demo_shop(
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

    same_shop = seed_mall._ensure_demo_shop(
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


def test_compliance_seed_never_fabricates_reviews_or_public_content(
    test_db_session, init_test_database
):
    seed_mall._seed_compliance(
        test_db_session,
        assets={},
        auto_complete_compliance_workflow=False,
    )

    assert UserDAO(test_db_session).get_by_username("hddg") is not None
    assert UserDAO(test_db_session).get_by_username("互动递归") is not None
    assert UserDAO(test_db_session).get_by_username("buyer") is not None
    assert test_db_session.query(ShopQualificationReview).count() == 0
    assert test_db_session.query(Goods).count() == 0
    assert test_db_session.query(InformationPost).count() == 0


def test_compliance_seed_adds_zero_sales_content_after_manual_approval(
    test_db_session, init_test_database
):
    seed_mall._seed_compliance(
        test_db_session,
        assets={},
        auto_complete_compliance_workflow=False,
    )
    merchant = UserDAO(test_db_session).get_by_username("hddg")
    publisher = UserDAO(test_db_session).get_by_username("互动递归")
    assert merchant is not None
    assert publisher is not None

    review_count_before = test_db_session.query(ShopQualificationReview).count()
    seed_mall._ensure_demo_shop(
        test_db_session,
        merchant,
        name=seed_mall.COMPLIANCE_SHOP_NAME,
        description=seed_mall.COMPLIANCE_SHOP_DESCRIPTION,
    )
    verification = qualify_user_in_db(test_db_session, publisher)

    seed_mall._seed_compliance(
        test_db_session,
        assets={},
        auto_complete_compliance_workflow=False,
    )

    goods = test_db_session.query(Goods).all()
    assert len(goods) == 17
    assert {
        "响应式企业官网建设服务",
        "小程序定制开发服务",
        "杭州本地餐饮小程序开发，支持点餐、会员和配送",
        "行业协会信息门户与会员管理系统建设",
    }.issubset({item.name for item in goods})
    assert all(item.sales == 0 for item in goods)
    posts = test_db_session.query(InformationPost).all()
    assert len(posts) == 20
    assert all(post.status == InformationStatus.PENDING for post in posts)
    assert all(post.publisher_verification_id == verification.id for post in posts)
    assert all(post.poster_user_id == publisher.id for post in posts)
    assert all(post.contact_name == "王勃智" for post in posts)
    assert all(post.contact_phone == "19935644212" for post in posts)
    assert (
        test_db_session.query(ShopQualificationReview).count()
        == review_count_before + 1
    )

    seed_mall._seed_compliance(test_db_session, assets={})

    assert test_db_session.query(Goods).count() == 17
    assert test_db_session.query(InformationPost).count() == 20
    assert all(
        post.status == InformationStatus.APPROVED
        for post in test_db_session.query(InformationPost).all()
    )
    assert (
        test_db_session.query(ShopQualificationReview).count()
        == review_count_before + 1
    )


def test_compliance_runtime_inputs_complete_workflow_and_public_content(
    test_db_session, init_test_database, tmp_path, monkeypatch
):
    monkeypatch.setattr(global_config.files, "local_root", tmp_path / "uploads")
    seed_mall._seed_compliance(test_db_session, assets={})
    merchant = UserDAO(test_db_session).get_by_username("hddg")
    publisher = UserDAO(test_db_session).get_by_username("互动递归")
    assert merchant is not None
    assert publisher is not None

    material_paths = {
        name: tmp_path / f"{name}.jpg"
        for name in (
            "license",
            "merchant-front",
            "merchant-back",
            "publisher-front",
            "publisher-back",
        )
    }
    for name, path in material_paths.items():
        path.write_bytes(f"test material: {name}".encode())

    inputs = seed_mall.ComplianceApplicationInputs(
        merchant_business_license_path=material_paths["license"],
        merchant_identity_front_path=material_paths["merchant-front"],
        merchant_identity_back_path=material_paths["merchant-back"],
        merchant_identity_number="110101199001011234",
        merchant_applicant_name="周子轩",
        merchant_business_address=seed_mall.COMPLIANCE_MERCHANT_REGISTERED_ADDRESS,
        merchant_contact_phone="19935644212",
        merchant_license_long_term=True,
        publisher_identity_front_path=material_paths["publisher-front"],
        publisher_identity_back_path=material_paths["publisher-back"],
        publisher_identity_number="110101199001011234",
        publisher_document_valid_until=date(2035, 1, 1),
    )
    seed_mall._seed_compliance(
        test_db_session,
        assets={},
        application_inputs=inputs,
    )

    shop = test_db_session.query(Shop).one()
    assert shop.status == ShopStatus.APPROVED
    assert shop.onboarding_stage == ShopOnboardingStage.APPROVED.value
    assert shop.legal_entity_name == "杭州互动递归科技有限公司"
    assert shop.unified_social_credit_code == "91330108MAKCCCHP50"
    assert test_db_session.query(ShopQualificationReview).count() == 1
    agreement = test_db_session.query(ShopAgreement).one()
    assert agreement.status == ShopAgreementStatus.ARCHIVED.value
    assert agreement.signature_mode == "online_click"
    assert agreement.merchant_signed_by_user_id == merchant.id
    verification = test_db_session.query(PublisherVerification).one()
    assert verification.status == PublisherVerificationStatus.APPROVED
    assert verification.real_name == "王勃智"
    assert verification.reviewer_user_id is not None
    assert test_db_session.query(FileAsset).count() == 6
    goods = test_db_session.query(Goods).all()
    assert len(goods) == 17
    assert all(item.sales == 0 for item in goods)
    assert all(len(item.images) == 2 for item in goods)
    assert len({item.main_image for item in goods}) == 17
    assert all(
        item.main_image.startswith("https://tuchuang.s3.fstc.kispace.cn/")
        for item in goods
    )
    assert all(
        all(image.endswith(".webp") for image in item.images) for item in goods
    )
    posts = test_db_session.query(InformationPost).all()
    assert len(posts) == 20
    assert all(post.status == InformationStatus.APPROVED for post in posts)
    assert all(post.reviewed_by_user_id is not None for post in posts)
    assert all(post.poster_user_id == publisher.id for post in posts)
    acceptances = test_db_session.query(LegalAcceptance).all()
    assert len(acceptances) == 5
    assert {acceptance.user_id for acceptance in acceptances} == {
        merchant.id,
        publisher.id,
    }
    assert all(acceptance.client_ip is None for acceptance in acceptances)
    assert sum(
        acceptance.user_agent == "seed_mall compliance setup (operator confirmed)"
        for acceptance in acceptances
    ) == 4
    assert sum(
        acceptance.user_agent == "seed_mall compliance workflow (operator confirmed)"
        for acceptance in acceptances
    ) == 1

    seed_mall._seed_compliance(
        test_db_session,
        assets={},
        application_inputs=inputs,
    )
    assert test_db_session.query(Shop).count() == 1
    assert test_db_session.query(PublisherVerification).count() == 1
    assert test_db_session.query(ShopQualificationReview).count() == 1
    assert test_db_session.query(ShopAgreement).count() == 1
    assert test_db_session.query(FileAsset).count() == 6
    assert test_db_session.query(LegalAcceptance).count() == 5
    assert test_db_session.query(Goods).count() == 17
    assert test_db_session.query(InformationPost).count() == 20
