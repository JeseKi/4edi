# -*- coding: utf-8 -*-
"""电商商城 DAO 层。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, case, false, func, or_

from src.server.dao.dao_base import BaseDAO

from .models import (
    Address,
    CartItem,
    Category,
    ChatMessage,
    CouponScope,
    CouponStatus,
    CouponTemplate,
    Evaluation,
    Favorite,
    FavoriteTargetType,
    Footprint,
    Goods,
    GoodsSku,
    Order,
    OrderItem,
    OrderLog,
    Payment,
    Refund,
    Shop,
    UserCoupon,
    UserCouponStatus,
    Wallet,
    WalletLedger,
    WithdrawRequest,
)
from .models import (
    ChatSenderType,
    GoodsStatus,
    OrderStatus,
    RefundStatus,
    ShopStatus,
    WithdrawStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CategoryDAO(BaseDAO):
    def create(self, name: str, *, parent_id: int | None, sort: int, icon: str | None) -> Category:
        exists = (
            self.db_session.query(Category)
            .filter(Category.name == name, Category.parent_id == parent_id)
            .first()
        )
        if exists:
            raise ValueError("同级分类名称已存在")
        level = 1
        if parent_id is not None:
            parent = self.get(parent_id)
            if parent is None:
                raise ValueError("上级分类不存在")
            level = parent.level + 1
        category = Category(name=name, parent_id=parent_id, level=level, sort=sort, icon=icon)
        self.db_session.add(category)
        self.db_session.flush()
        return category

    def get(self, category_id: int) -> Category | None:
        return self.db_session.query(Category).filter(Category.id == category_id).first()

    def list_all(self) -> list[Category]:
        return (
            self.db_session.query(Category)
            .order_by(Category.level.asc(), Category.sort.asc(), Category.id.asc())
            .all()
        )

    def delete(self, category_id: int) -> None:
        self.db_session.query(Category).filter(Category.id == category_id).delete()


class ShopDAO(BaseDAO):
    def create(
        self,
        *,
        owner_user_id: int,
        name: str,
        description: str | None,
        avatar: str | None,
        real_name: str | None = None,
        identity_number: str | None = None,
        business_license_asset_id: str | None = None,
        identity_front_asset_id: str | None = None,
        identity_back_asset_id: str | None = None,
        legal_entity_name: str | None = None,
        unified_social_credit_code: str | None = None,
        unified_social_credit_code_masked: str | None = None,
        legal_representative: str | None = None,
        registered_address: str | None = None,
        business_address: str | None = None,
        contact_phone: str | None = None,
        business_license_valid_until: date | None = None,
        business_license_long_term: bool = False,
        merchant_agreement_version: str | None = None,
        merchant_agreement_asset_id: str | None = None,
        agreement_accepted_at: datetime | None = None,
    ) -> Shop:
        exists = self.db_session.query(Shop).filter(Shop.owner_user_id == owner_user_id).first()
        if exists:
            raise ValueError("每个用户只能申请一家店铺")
        shop = Shop(
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            avatar=avatar,
            real_name=real_name,
            identity_number_encrypted=identity_number,
            identity_number_masked=None,
            business_license_asset_id=business_license_asset_id,
            identity_front_asset_id=identity_front_asset_id,
            identity_back_asset_id=identity_back_asset_id,
            legal_entity_name=legal_entity_name,
            unified_social_credit_code=unified_social_credit_code,
            unified_social_credit_code_masked=unified_social_credit_code_masked,
            legal_representative=legal_representative,
            registered_address=registered_address,
            business_address=business_address,
            contact_phone=contact_phone,
            business_license_valid_until=business_license_valid_until,
            business_license_long_term=business_license_long_term,
            merchant_agreement_version=merchant_agreement_version,
            merchant_agreement_asset_id=merchant_agreement_asset_id,
            agreement_accepted_at=agreement_accepted_at,
            status=ShopStatus.PENDING,
        )
        self.db_session.add(shop)
        self.db_session.flush()
        return shop

    def get(self, shop_id: int) -> Shop | None:
        return self.db_session.query(Shop).filter(Shop.id == shop_id).first()

    def lock(self, shop_id: int) -> Shop | None:
        return (
            self.db_session.query(Shop)
            .filter(Shop.id == shop_id)
            .with_for_update()
            .first()
        )

    def get_by_owner(self, owner_user_id: int) -> Shop | None:
        return (
            self.db_session.query(Shop)
            .filter(Shop.owner_user_id == owner_user_id)
            .first()
        )

    def list(
        self,
        *,
        status: ShopStatus | None = None,
        qualification_state: str | None = None,
        keyword: str | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[Shop], int]:
        query = self.db_session.query(Shop)
        if status is not None:
            query = query.filter(Shop.status == status)
        now = _utcnow()
        if qualification_state == "expired":
            query = query.filter(
                Shop.status == ShopStatus.APPROVED,
                Shop.qualification_valid_until <= now,
            )
        elif qualification_state == "expiring_soon":
            query = query.filter(
                Shop.status == ShopStatus.APPROVED,
                Shop.qualification_valid_until > now,
                Shop.qualification_valid_until <= now + timedelta(days=30),
            )
        if keyword:
            query = query.filter(Shop.name.ilike(f"%{keyword}%"))
        total = query.count()
        shops = (
            query.order_by(Shop.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return shops, total


class GoodsDAO(BaseDAO):
    def create(
        self,
        *,
        shop_id: int,
        category_id: int | None,
        name: str,
        main_image: str,
        images: list[str],
        detail: str | None,
        price_fen: int,
        original_price_fen: int | None,
        stock: int,
    ) -> Goods:
        goods = Goods(
            shop_id=shop_id,
            category_id=category_id,
            name=name,
            main_image=main_image,
            images=images,
            detail=detail,
            price_fen=price_fen,
            original_price_fen=original_price_fen,
            stock=stock,
            status=GoodsStatus.DRAFT,
        )
        self.db_session.add(goods)
        self.db_session.flush()
        return goods

    def get(self, goods_id: int) -> Goods | None:
        return self.db_session.query(Goods).filter(Goods.id == goods_id).first()

    def lock(self, goods_id: int) -> Goods | None:
        return (
            self.db_session.query(Goods)
            .filter(Goods.id == goods_id)
            .with_for_update()
            .first()
        )

    def list_public(
        self,
        *,
        keyword: str | None = None,
        category_id: int | None = None,
        shop_id: int | None = None,
        sort: str = "default",
        page: int,
        page_size: int,
    ) -> tuple[list[Goods], int]:
        now = datetime.now(timezone.utc)
        query = self.db_session.query(Goods).join(Shop, Shop.id == Goods.shop_id).filter(
            Goods.status == GoodsStatus.ON,
            Goods.deleted_at.is_(None),
            Shop.status == ShopStatus.APPROVED,
            Shop.last_qualification_review_id.is_not(None),
            Shop.qualification_valid_until > now,
        )
        if keyword:
            query = query.filter(Goods.name.ilike(f"%{keyword}%"))
        if category_id is not None:
            category = self.db_session.query(Category).filter(Category.id == category_id).first()
            if category is not None:
                ids = [category.id]
                ids.extend(
                    c.id
                    for c in self.db_session.query(Category).filter(Category.parent_id == category.id).all()
                )
                query = query.filter(Goods.category_id.in_(ids))
        if shop_id is not None:
            query = query.filter(Goods.shop_id == shop_id)
        total = query.count()
        if sort == "sales":
            query = query.order_by(Goods.sales.desc(), Goods.id.desc())
        elif sort == "price_asc":
            query = query.order_by(Goods.price_fen.asc(), Goods.id.desc())
        elif sort == "price_desc":
            query = query.order_by(Goods.price_fen.desc(), Goods.id.desc())
        elif sort == "new":
            query = query.order_by(Goods.created_at.desc(), Goods.id.desc())
        else:
            query = query.order_by(Goods.id.desc())
        goods_list = (
            query.offset((page - 1) * page_size).limit(page_size).all()
        )
        return goods_list, total

    def list_for_shop(
        self,
        *,
        shop_id: int,
        status: GoodsStatus | None = None,
        keyword: str | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[Goods], int]:
        query = self.db_session.query(Goods).filter(
            Goods.shop_id == shop_id, Goods.deleted_at.is_(None)
        )
        if status is not None:
            query = query.filter(Goods.status == status)
        if keyword:
            query = query.filter(Goods.name.ilike(f"%{keyword}%"))
        total = query.count()
        goods_list = (
            query.order_by(Goods.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return goods_list, total


class GoodsSkuDAO(BaseDAO):
    def create(
        self,
        *,
        goods_id: int,
        sku_code: str | None,
        specs: dict,
        price_fen: int,
        stock: int,
    ) -> GoodsSku:
        sku = GoodsSku(
            goods_id=goods_id, sku_code=sku_code, specs=specs, price_fen=price_fen, stock=stock
        )
        self.db_session.add(sku)
        self.db_session.flush()
        return sku

    def get(self, sku_id: int) -> GoodsSku | None:
        return self.db_session.query(GoodsSku).filter(GoodsSku.id == sku_id).first()

    def lock(self, sku_id: int) -> GoodsSku | None:
        return (
            self.db_session.query(GoodsSku)
            .filter(GoodsSku.id == sku_id)
            .with_for_update()
            .first()
        )

    def list_by_goods(self, goods_id: int) -> list[GoodsSku]:
        return (
            self.db_session.query(GoodsSku)
            .filter(GoodsSku.goods_id == goods_id)
            .order_by(GoodsSku.id.asc())
            .all()
        )

    def delete_by_goods(self, goods_id: int) -> None:
        self.db_session.query(GoodsSku).filter(GoodsSku.goods_id == goods_id).delete()


class CartItemDAO(BaseDAO):
    def add_or_update(self, *, user_id: int, goods_id: int, sku_id: int, quantity: int) -> CartItem:
        item = (
            self.db_session.query(CartItem)
            .filter(CartItem.user_id == user_id, CartItem.sku_id == sku_id)
            .first()
        )
        if item is not None:
            item.quantity += quantity
            item.selected = True
        else:
            item = CartItem(
                user_id=user_id, goods_id=goods_id, sku_id=sku_id, quantity=quantity
            )
            self.db_session.add(item)
        self.db_session.flush()
        return item

    def get_for_user(self, item_id: int, user_id: int) -> CartItem | None:
        return (
            self.db_session.query(CartItem)
            .filter(CartItem.id == item_id, CartItem.user_id == user_id)
            .first()
        )

    def list_for_user(self, user_id: int) -> list[CartItem]:
        return (
            self.db_session.query(CartItem)
            .filter(CartItem.user_id == user_id)
            .order_by(CartItem.updated_at.desc())
            .all()
        )

    def delete_for_user(self, item_ids: list[int], user_id: int) -> int:
        deleted = (
            self.db_session.query(CartItem)
            .filter(CartItem.id.in_(item_ids), CartItem.user_id == user_id)
            .delete(synchronize_session=False)
        )
        return int(deleted)


class AddressDAO(BaseDAO):
    def create(self, user_id: int, **fields: Any) -> Address:
        address = Address(user_id=user_id, **fields)
        self.db_session.add(address)
        self.db_session.flush()
        return address

    def get_for_user(self, address_id: int, user_id: int) -> Address | None:
        return (
            self.db_session.query(Address)
            .filter(Address.id == address_id, Address.user_id == user_id)
            .first()
        )

    def list_for_user(self, user_id: int) -> list[Address]:
        return (
            self.db_session.query(Address)
            .filter(Address.user_id == user_id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
            .all()
        )

    def clear_default(self, user_id: int) -> None:
        (
            self.db_session.query(Address)
            .filter(Address.user_id == user_id)
            .update({Address.is_default: False}, synchronize_session=False)
        )

    def delete_for_user(self, address_id: int, user_id: int) -> bool:
        deleted = (
            self.db_session.query(Address)
            .filter(Address.id == address_id, Address.user_id == user_id)
            .delete()
        )
        return deleted > 0


class OrderDAO(BaseDAO):
    def create(
        self,
        *,
        order_no: str,
        buyer_id: int,
        shop_id: int,
        goods_amount_fen: int,
        freight_fen: int,
        pay_amount_fen: int,
        receiver_name: str,
        receiver_phone: str,
        receiver_address: str,
        remark: str | None,
    ) -> Order:
        order = Order(
            order_no=order_no,
            buyer_id=buyer_id,
            shop_id=shop_id,
            status=OrderStatus.PENDING_PAYMENT,
            goods_amount_fen=goods_amount_fen,
            freight_fen=freight_fen,
            pay_amount_fen=pay_amount_fen,
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            receiver_address=receiver_address,
            remark=remark,
        )
        self.db_session.add(order)
        self.db_session.flush()
        return order

    def get(self, order_id: int) -> Order | None:
        return self.db_session.query(Order).filter(Order.id == order_id).first()

    def get_by_no(self, order_no: str) -> Order | None:
        return (
            self.db_session.query(Order).filter(Order.order_no == order_no).first()
        )

    def lock_by_no(self, order_no: str) -> Order | None:
        return (
            self.db_session.query(Order)
            .filter(Order.order_no == order_no)
            .with_for_update()
            .first()
        )

    def get_for_buyer(self, order_no: str, buyer_id: int) -> Order | None:
        return (
            self.db_session.query(Order)
            .filter(Order.order_no == order_no, Order.buyer_id == buyer_id)
            .first()
        )

    def get_for_shop(self, order_no: str, shop_id: int) -> Order | None:
        return (
            self.db_session.query(Order)
            .filter(Order.order_no == order_no, Order.shop_id == shop_id)
            .first()
        )

    def list_for_buyer(
        self, buyer_id: int, status: OrderStatus | None, page: int, page_size: int
    ) -> tuple[list[Order], int]:
        query = self.db_session.query(Order).filter(Order.buyer_id == buyer_id)
        if status is not None:
            query = query.filter(Order.status == status)
        total = query.count()
        orders = (
            query.order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return orders, total

    def list_for_shop(
        self, shop_id: int, status: OrderStatus | None, page: int, page_size: int
    ) -> tuple[list[Order], int]:
        query = self.db_session.query(Order).filter(Order.shop_id == shop_id)
        if status is not None:
            query = query.filter(Order.status == status)
        total = query.count()
        orders = (
            query.order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return orders, total

    def list_completed_for_buyer(self, buyer_id: int) -> list[Order]:
        """买家已确认收货的订单（评价入口）。"""
        return (
            self.db_session.query(Order)
            .filter(Order.buyer_id == buyer_id, Order.status == OrderStatus.COMPLETED)
            .order_by(Order.completed_at.desc())
            .all()
        )


class OrderItemDAO(BaseDAO):
    def create_many(
        self,
        *,
        order_id: int,
        goods_id: int,
        sku_id: int,
        goods_name: str,
        goods_image: str,
        sku_specs: dict,
        unit_price_fen: int,
        quantity: int,
        subtotal_fen: int,
    ) -> OrderItem:
        item = OrderItem(
            order_id=order_id,
            goods_id=goods_id,
            sku_id=sku_id,
            goods_name=goods_name,
            goods_image=goods_image,
            sku_specs=sku_specs,
            unit_price_fen=unit_price_fen,
            quantity=quantity,
            subtotal_fen=subtotal_fen,
        )
        self.db_session.add(item)
        self.db_session.flush()
        return item

    def list_by_order(self, order_id: int) -> list[OrderItem]:
        return (
            self.db_session.query(OrderItem)
            .filter(OrderItem.order_id == order_id)
            .order_by(OrderItem.id.asc())
            .all()
        )

    def get(self, order_id: int, item_id: int) -> OrderItem | None:
        return (
            self.db_session.query(OrderItem)
            .filter(OrderItem.id == item_id, OrderItem.order_id == order_id)
            .first()
        )


class EvaluationDAO(BaseDAO):
    def create(
        self,
        *,
        order_id: int,
        order_item_id: int,
        goods_id: int,
        shop_id: int,
        buyer_id: int,
        rating: int,
        content: str,
        images: list,
    ) -> Evaluation:
        evaluation = Evaluation(
            order_id=order_id,
            order_item_id=order_item_id,
            goods_id=goods_id,
            shop_id=shop_id,
            buyer_id=buyer_id,
            rating=rating,
            content=content,
            images=images,
        )
        self.db_session.add(evaluation)
        self.db_session.flush()
        return evaluation

    def get(self, evaluation_id: int) -> Evaluation | None:
        return (
            self.db_session.query(Evaluation)
            .filter(Evaluation.id == evaluation_id)
            .first()
        )

    def get_for_buyer(self, evaluation_id: int, buyer_id: int) -> Evaluation | None:
        return (
            self.db_session.query(Evaluation)
            .filter(Evaluation.id == evaluation_id, Evaluation.buyer_id == buyer_id)
            .first()
        )

    def get_for_shop(self, evaluation_id: int, shop_id: int) -> Evaluation | None:
        return (
            self.db_session.query(Evaluation)
            .filter(Evaluation.id == evaluation_id, Evaluation.shop_id == shop_id)
            .first()
        )

    def get_by_order_item(self, order_id: int, order_item_id: int) -> Evaluation | None:
        return (
            self.db_session.query(Evaluation)
            .filter(
                Evaluation.order_id == order_id,
                Evaluation.order_item_id == order_item_id,
            )
            .first()
        )

    def list_by_order(self, order_id: int) -> list[Evaluation]:
        return (
            self.db_session.query(Evaluation)
            .filter(Evaluation.order_id == order_id)
            .order_by(Evaluation.id.asc())
            .all()
        )

    def list_by_goods(
        self, goods_id: int, page: int, page_size: int
    ) -> tuple[list[Evaluation], int]:
        query = self.db_session.query(Evaluation).filter(Evaluation.goods_id == goods_id)
        total = query.count()
        items = (
            query.order_by(Evaluation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def rating_summary(self, goods_id: int) -> dict:
        row = (
            self.db_session.query(
                func.count(Evaluation.id),
                func.avg(Evaluation.rating),
                func.sum(case((Evaluation.rating >= 4, 1), else_=0)),
            )
            .filter(Evaluation.goods_id == goods_id)
            .one()
        )
        total = int(row[0] or 0)
        avg = float(row[1]) if row[1] is not None else 0.0
        good = int(row[2] or 0)
        good_rate = round(good / total * 100, 1) if total else 0.0
        return {
            "avg_rating": round(avg, 1),
            "rating_count": total,
            "good_rate": good_rate,
        }

    def list_by_buyer(
        self, buyer_id: int, page: int, page_size: int
    ) -> tuple[list[Evaluation], int]:
        query = self.db_session.query(Evaluation).filter(Evaluation.buyer_id == buyer_id)
        total = query.count()
        items = (
            query.order_by(Evaluation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_for_shop(
        self, shop_id: int, page: int, page_size: int
    ) -> tuple[list[Evaluation], int]:
        query = self.db_session.query(Evaluation).filter(Evaluation.shop_id == shop_id)
        total = query.count()
        items = (
            query.order_by(Evaluation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


class OrderLogDAO(BaseDAO):
    def append(self, order_id: int, message: str) -> OrderLog:
        log = OrderLog(order_id=order_id, message=message)
        self.db_session.add(log)
        self.db_session.flush()
        return log

    def list_by_order(self, order_id: int) -> list[OrderLog]:
        return (
            self.db_session.query(OrderLog)
            .filter(OrderLog.order_id == order_id)
            .order_by(OrderLog.id.asc())
            .all()
        )


class WalletDAO(BaseDAO):
    def get(self, shop_id: int) -> Wallet | None:
        return self.db_session.query(Wallet).filter(Wallet.shop_id == shop_id).first()

    def lock(self, shop_id: int) -> Wallet | None:
        return (
            self.db_session.query(Wallet)
            .filter(Wallet.shop_id == shop_id)
            .with_for_update()
            .first()
        )

    def get_or_create(self, shop_id: int) -> Wallet:
        wallet = self.lock(shop_id)
        if wallet is not None:
            return wallet
        wallet = Wallet(shop_id=shop_id)
        self.db_session.add(wallet)
        self.db_session.flush()
        return wallet


class WalletLedgerDAO(BaseDAO):
    def create(
        self,
        *,
        shop_id: int,
        entry_type: Any,
        status: Any,
        amount_fen: int,
        related_no: str | None = None,
        note: str | None = None,
        available_at: datetime | None = None,
    ) -> WalletLedger:
        ledger = WalletLedger(
            shop_id=shop_id,
            entry_type=entry_type,
            status=status,
            amount_fen=amount_fen,
            related_no=related_no,
            note=note,
            available_at=available_at,
        )
        self.db_session.add(ledger)
        self.db_session.flush()
        return ledger

    def list_by_shop(
        self, shop_id: int, page: int, page_size: int
    ) -> tuple[list[WalletLedger], int]:
        query = self.db_session.query(WalletLedger).filter(WalletLedger.shop_id == shop_id)
        total = query.count()
        items = (
            query.order_by(WalletLedger.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


class WithdrawRequestDAO(BaseDAO):
    def create(
        self, *, shop_id: int, withdraw_no: str, amount_fen: int, account_info: dict
    ) -> WithdrawRequest:
        request = WithdrawRequest(
            shop_id=shop_id,
            withdraw_no=withdraw_no,
            amount_fen=amount_fen,
            account_info=account_info,
        )
        self.db_session.add(request)
        self.db_session.flush()
        return request

    def get(self, withdraw_id: int) -> WithdrawRequest | None:
        return (
            self.db_session.query(WithdrawRequest)
            .filter(WithdrawRequest.id == withdraw_id)
            .first()
        )

    def lock(self, withdraw_id: int) -> WithdrawRequest | None:
        return (
            self.db_session.query(WithdrawRequest)
            .filter(WithdrawRequest.id == withdraw_id)
            .with_for_update()
            .first()
        )

    def list_by_shop(
        self, shop_id: int, page: int, page_size: int
    ) -> tuple[list[WithdrawRequest], int]:
        query = self.db_session.query(WithdrawRequest).filter(
            WithdrawRequest.shop_id == shop_id
        )
        total = query.count()
        items = (
            query.order_by(WithdrawRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_all(
        self, status: WithdrawStatus | None, page: int, page_size: int
    ) -> tuple[list[WithdrawRequest], int]:
        query = self.db_session.query(WithdrawRequest)
        if status is not None:
            query = query.filter(WithdrawRequest.status == status)
        total = query.count()
        items = (
            query.order_by(WithdrawRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


class PaymentDAO(BaseDAO):
    def create(
        self,
        *,
        out_trade_no: str,
        order_no: str,
        amount_fen: int,
        channel: str,
        pay_type: str | None,
    ) -> Payment:
        payment = Payment(
            out_trade_no=out_trade_no,
            order_no=order_no,
            amount_fen=amount_fen,
            channel=channel,
            pay_type=pay_type,
        )
        self.db_session.add(payment)
        self.db_session.flush()
        return payment

    def get(self, payment_id: int) -> Payment | None:
        return self.db_session.query(Payment).filter(Payment.id == payment_id).first()

    def lock(self, payment_id: int) -> Payment | None:
        return (
            self.db_session.query(Payment)
            .filter(Payment.id == payment_id)
            .with_for_update()
            .first()
        )

    def get_by_out_trade_no(self, out_trade_no: str) -> Payment | None:
        return (
            self.db_session.query(Payment)
            .filter(Payment.out_trade_no == out_trade_no)
            .first()
        )

    def get_by_order_no(self, order_no: str) -> Payment | None:
        return (
            self.db_session.query(Payment)
            .filter(Payment.order_no == order_no)
            .order_by(Payment.id.desc())
            .first()
        )

    def get_active_by_order_no(self, order_no: str, *, lock: bool = False) -> Payment | None:
        query = self.db_session.query(Payment).filter(
            Payment.order_no == order_no, Payment.is_active.is_(True)
        )
        if lock:
            query = query.with_for_update()
        return query.first()


class ChatMessageDAO(BaseDAO):
    def create(
        self,
        *,
        shop_id: int,
        order_no: str | None,
        sender_type: Any,
        sender_user_id: int | None,
        content: str,
    ) -> ChatMessage:
        message = ChatMessage(
            shop_id=shop_id,
            order_no=order_no,
            sender_type=sender_type,
            sender_user_id=sender_user_id,
            content=content,
        )
        self.db_session.add(message)
        self.db_session.flush()
        return message

    def list_for_shop(
        self, shop_id: int, *, order_no: str | None, after_id: int | None
    ) -> list[ChatMessage]:
        query = self.db_session.query(ChatMessage).filter(ChatMessage.shop_id == shop_id)
        if order_no:
            query = query.filter(ChatMessage.order_no == order_no)
        if after_id is not None:
            query = query.filter(ChatMessage.id > after_id)
        return query.order_by(ChatMessage.id.asc()).limit(200).all()

    def list_for_buyer(
        self, buyer_id: int, shop_id: int, *, order_no: str | None, after_id: int | None
    ) -> list[ChatMessage]:
        participated_order_nos = {
            row[0]
            for row in self.db_session.query(ChatMessage.order_no)
            .filter(
                ChatMessage.sender_user_id == buyer_id,
                ChatMessage.shop_id == shop_id,
            )
            .distinct()
            .all()
        }
        seller_matches = []
        for participated_no in participated_order_nos:
            if participated_no is None:
                seller_matches.append(ChatMessage.order_no.is_(None))
            else:
                seller_matches.append(ChatMessage.order_no == participated_no)
        if seller_matches:
            seller_visible = and_(
                ChatMessage.sender_type == ChatSenderType.SELLER,
                or_(*seller_matches),
            )
        else:
            seller_visible = and_(false())
        query = self.db_session.query(ChatMessage).filter(
            ChatMessage.shop_id == shop_id,
            or_(ChatMessage.sender_user_id == buyer_id, seller_visible),
        )
        if order_no:
            query = query.filter(ChatMessage.order_no == order_no)
        if after_id is not None:
            query = query.filter(ChatMessage.id > after_id)
        return query.order_by(ChatMessage.id.asc()).limit(200).all()

    def list_shop_ids_for_buyer(self, buyer_id: int) -> list[int]:
        rows = (
            self.db_session.query(ChatMessage.shop_id)
            .filter(ChatMessage.sender_user_id == buyer_id)
            .distinct()
            .all()
        )
        return [row[0] for row in rows]

    def count_unread(
        self, shop_id: int, *, owner_user_id: int, order_no: str | None
    ) -> int:
        query = self.db_session.query(func.count(ChatMessage.id)).filter(
            ChatMessage.shop_id == shop_id,
            ChatMessage.sender_type == ChatSenderType.BUYER,
            ChatMessage.read_at.is_(None),
        )
        if order_no:
            query = query.filter(ChatMessage.order_no == order_no)
        return int(query.scalar() or 0)

    def mark_buyer_messages_read(
        self, shop_id: int, *, owner_user_id: int, order_no: str | None, after_id: int | None
    ) -> int:
        query = self.db_session.query(ChatMessage).filter(
            ChatMessage.shop_id == shop_id,
            ChatMessage.sender_type == ChatSenderType.SELLER,
            ChatMessage.read_at.is_(None),
        )
        if order_no:
            query = query.filter(ChatMessage.order_no == order_no)
        if after_id is not None:
            query = query.filter(ChatMessage.id > after_id)
        updated = query.update({ChatMessage.read_at: _utcnow()}, synchronize_session=False)
        return int(updated)

    def mark_shop_messages_read(
        self, shop_id: int, *, owner_user_id: int, order_no: str | None
    ) -> int:
        query = self.db_session.query(ChatMessage).filter(
            ChatMessage.shop_id == shop_id,
            ChatMessage.sender_type == ChatSenderType.BUYER,
            ChatMessage.read_at.is_(None),
        )
        if order_no:
            query = query.filter(ChatMessage.order_no == order_no)
        updated = query.update({ChatMessage.read_at: _utcnow()}, synchronize_session=False)
        return int(updated)


class RefundDAO(BaseDAO):
    def create(
        self,
        *,
        refund_no: str,
        order_no: str,
        shop_id: int,
        buyer_id: int,
        type: Any,
        status: Any,
        order_status_snapshot: Any,
        reason: str,
        description: str | None,
        evidence_images: list,
        amount_fen: int,
    ) -> Refund:
        refund = Refund(
            refund_no=refund_no,
            order_no=order_no,
            shop_id=shop_id,
            buyer_id=buyer_id,
            type=type,
            status=status,
            order_status_snapshot=order_status_snapshot,
            reason=reason,
            description=description,
            evidence_images=evidence_images,
            amount_fen=amount_fen,
        )
        self.db_session.add(refund)
        self.db_session.flush()
        return refund

    def get(self, refund_id: int) -> Refund | None:
        return self.db_session.query(Refund).filter(Refund.id == refund_id).first()

    def lock(self, refund_id: int) -> Refund | None:
        return (
            self.db_session.query(Refund)
            .filter(Refund.id == refund_id)
            .with_for_update()
            .first()
        )

    def get_by_no(self, refund_no: str) -> Refund | None:
        return (
            self.db_session.query(Refund)
            .filter(Refund.refund_no == refund_no)
            .first()
        )

    def lock_by_no(self, refund_no: str) -> Refund | None:
        return (
            self.db_session.query(Refund)
            .filter(Refund.refund_no == refund_no)
            .with_for_update()
            .first()
        )

    def get_for_buyer(self, refund_no: str, buyer_id: int) -> Refund | None:
        return (
            self.db_session.query(Refund)
            .filter(Refund.refund_no == refund_no, Refund.buyer_id == buyer_id)
            .first()
        )

    def get_for_shop(self, refund_no: str, shop_id: int) -> Refund | None:
        return (
            self.db_session.query(Refund)
            .filter(Refund.refund_no == refund_no, Refund.shop_id == shop_id)
            .first()
        )

    def find_active_by_order(self, order_no: str) -> Refund | None:
        """查找订单进行中的退款单（待处理/退货中/退款中）。"""
        return (
            self.db_session.query(Refund)
            .filter(
                Refund.order_no == order_no,
                Refund.status.in_(
                    (RefundStatus.PENDING, RefundStatus.RETURNING, RefundStatus.REFUNDING)
                ),
            )
            .first()
        )

    def list_for_buyer(
        self, buyer_id: int, page: int, page_size: int
    ) -> tuple[list[Refund], int]:
        query = self.db_session.query(Refund).filter(Refund.buyer_id == buyer_id)
        total = query.count()
        items = (
            query.order_by(Refund.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_for_shop(
        self,
        shop_id: int,
        status: RefundStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Refund], int]:
        query = self.db_session.query(Refund).filter(Refund.shop_id == shop_id)
        if status is not None:
            query = query.filter(Refund.status == status)
        total = query.count()
        items = (
            query.order_by(Refund.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_all(
        self, status: RefundStatus | None, page: int, page_size: int
    ) -> tuple[list[Refund], int]:
        query = self.db_session.query(Refund)
        if status is not None:
            query = query.filter(Refund.status == status)
        total = query.count()
        items = (
            query.order_by(Refund.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


class CouponTemplateDAO(BaseDAO):
    def create(
        self,
        *,
        name: str,
        type: Any,
        value_fen: int,
        discount: int,
        min_amount_fen: int,
        scope: Any,
        shop_id: int | None,
        total_count: int,
        per_user_limit: int,
        valid_from: datetime,
        valid_until: datetime,
    ) -> CouponTemplate:
        coupon = CouponTemplate(
            name=name,
            type=type,
            value_fen=value_fen,
            discount=discount,
            min_amount_fen=min_amount_fen,
            scope=scope,
            shop_id=shop_id,
            total_count=total_count,
            per_user_limit=per_user_limit,
            valid_from=valid_from,
            valid_until=valid_until,
            status=CouponStatus.ACTIVE,
        )
        self.db_session.add(coupon)
        self.db_session.flush()
        return coupon

    def get(self, coupon_id: int) -> CouponTemplate | None:
        return (
            self.db_session.query(CouponTemplate)
            .filter(CouponTemplate.id == coupon_id)
            .first()
        )

    def lock(self, coupon_id: int) -> CouponTemplate | None:
        return (
            self.db_session.query(CouponTemplate)
            .filter(CouponTemplate.id == coupon_id)
            .with_for_update()
            .first()
        )

    def get_for_shop(self, coupon_id: int, shop_id: int) -> CouponTemplate | None:
        return (
            self.db_session.query(CouponTemplate)
            .filter(CouponTemplate.id == coupon_id, CouponTemplate.shop_id == shop_id)
            .first()
        )

    def list_available(
        self,
        *,
        scope: CouponScope | None,
        shop_id: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CouponTemplate], int]:
        """领券中心：进行中的有效券（未暂停、未过期、未领完）。"""
        now = _utcnow()
        query = self.db_session.query(CouponTemplate).filter(
            CouponTemplate.status == CouponStatus.ACTIVE,
            CouponTemplate.valid_from <= now,
            CouponTemplate.valid_until > now,
            (CouponTemplate.total_count == 0)
            | (CouponTemplate.received_count < CouponTemplate.total_count),
        )
        if scope is not None:
            query = query.filter(CouponTemplate.scope == scope)
        if shop_id is not None:
            query = query.filter(CouponTemplate.shop_id == shop_id)
        total = query.count()
        items = (
            query.order_by(CouponTemplate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_for_shop(
        self, shop_id: int, page: int, page_size: int
    ) -> tuple[list[CouponTemplate], int]:
        query = self.db_session.query(CouponTemplate).filter(
            CouponTemplate.shop_id == shop_id
        )
        total = query.count()
        items = (
            query.order_by(CouponTemplate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_all(
        self,
        status: CouponStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CouponTemplate], int]:
        query = self.db_session.query(CouponTemplate)
        if status is not None:
            query = query.filter(CouponTemplate.status == status)
        total = query.count()
        items = (
            query.order_by(CouponTemplate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def mark_expired_by_until(self) -> int:
        """把已过有效期的进行中模板置为过期。"""
        updated = (
            self.db_session.query(CouponTemplate)
            .filter(
                CouponTemplate.status.in_((CouponStatus.ACTIVE, CouponStatus.PAUSED)),
                CouponTemplate.valid_until <= _utcnow(),
            )
            .update({CouponTemplate.status: CouponStatus.EXPIRED}, synchronize_session=False)
        )
        return int(updated)


class UserCouponDAO(BaseDAO):
    def create(
        self,
        *,
        user_id: int,
        coupon_id: int,
        expired_at: datetime | None,
    ) -> UserCoupon:
        user_coupon = UserCoupon(
            user_id=user_id,
            coupon_id=coupon_id,
            status=UserCouponStatus.UNUSED,
            expired_at=expired_at,
        )
        self.db_session.add(user_coupon)
        self.db_session.flush()
        return user_coupon

    def get(self, user_coupon_id: int) -> UserCoupon | None:
        return (
            self.db_session.query(UserCoupon)
            .filter(UserCoupon.id == user_coupon_id)
            .first()
        )

    def lock(self, user_coupon_id: int) -> UserCoupon | None:
        return (
            self.db_session.query(UserCoupon)
            .filter(UserCoupon.id == user_coupon_id)
            .with_for_update()
            .first()
        )

    def get_for_user(self, user_id: int, coupon_id: int) -> UserCoupon | None:
        return (
            self.db_session.query(UserCoupon)
            .filter(UserCoupon.user_id == user_id, UserCoupon.coupon_id == coupon_id)
            .first()
        )

    def lock_for_user(self, user_id: int, coupon_id: int) -> UserCoupon | None:
        return (
            self.db_session.query(UserCoupon)
            .filter(UserCoupon.user_id == user_id, UserCoupon.coupon_id == coupon_id)
            .with_for_update()
            .first()
        )

    def count_for_user(self, user_id: int, coupon_id: int) -> int:
        return int(
            self.db_session.query(func.count(UserCoupon.id))
            .filter(UserCoupon.user_id == user_id, UserCoupon.coupon_id == coupon_id)
            .scalar()
            or 0
        )

    def mark_expired(self) -> int:
        """把已过期未使用的用户券置为过期。"""
        updated = (
            self.db_session.query(UserCoupon)
            .filter(
                UserCoupon.status == UserCouponStatus.UNUSED,
                UserCoupon.expired_at.isnot(None),
                UserCoupon.expired_at <= _utcnow(),
            )
            .update({UserCoupon.status: UserCouponStatus.EXPIRED}, synchronize_session=False)
        )
        return int(updated)

    def list_for_user(
        self,
        user_id: int,
        status: UserCouponStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[UserCoupon], int]:
        query = self.db_session.query(UserCoupon).filter(UserCoupon.user_id == user_id)
        if status is not None:
            query = query.filter(UserCoupon.status == status)
        total = query.count()
        items = (
            query.order_by(UserCoupon.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_unused_for_user(self, user_id: int) -> list[UserCoupon]:
        return (
            self.db_session.query(UserCoupon)
            .filter(
                UserCoupon.user_id == user_id,
                UserCoupon.status == UserCouponStatus.UNUSED,
            )
            .order_by(UserCoupon.id.desc())
            .all()
        )


class FavoriteDAO(BaseDAO):
    def create(self, *, user_id: int, target_type: FavoriteTargetType, target_id: int) -> Favorite:
        favorite = Favorite(user_id=user_id, target_type=target_type, target_id=target_id)
        self.db_session.add(favorite)
        self.db_session.flush()
        return favorite

    def get(
        self, user_id: int, target_type: FavoriteTargetType, target_id: int
    ) -> Favorite | None:
        return (
            self.db_session.query(Favorite)
            .filter(
                Favorite.user_id == user_id,
                Favorite.target_type == target_type,
                Favorite.target_id == target_id,
            )
            .first()
        )

    def delete(
        self, user_id: int, target_type: FavoriteTargetType, target_id: int
    ) -> bool:
        deleted = (
            self.db_session.query(Favorite)
            .filter(
                Favorite.user_id == user_id,
                Favorite.target_type == target_type,
                Favorite.target_id == target_id,
            )
            .delete(synchronize_session=False)
        )
        return bool(deleted)

    def list_for_user(
        self,
        user_id: int,
        target_type: FavoriteTargetType | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Favorite], int]:
        query = self.db_session.query(Favorite).filter(Favorite.user_id == user_id)
        if target_type is not None:
            query = query.filter(Favorite.target_type == target_type)
        total = query.count()
        items = (
            query.order_by(Favorite.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total


class FootprintDAO(BaseDAO):
    def upsert(self, *, user_id: int, goods_id: int, shop_id: int) -> Footprint:
        """每用户每商品保留一条记录，重复浏览仅刷新 viewed_at。"""
        footprint = (
            self.db_session.query(Footprint)
            .filter(Footprint.user_id == user_id, Footprint.goods_id == goods_id)
            .first()
        )
        if footprint is None:
            footprint = Footprint(user_id=user_id, goods_id=goods_id, shop_id=shop_id)
            self.db_session.add(footprint)
        else:
            footprint.shop_id = shop_id
            footprint.viewed_at = _utcnow()
        self.db_session.flush()
        return footprint

    def list_for_user(
        self, user_id: int, page: int, page_size: int
    ) -> tuple[list[Footprint], int]:
        query = self.db_session.query(Footprint).filter(Footprint.user_id == user_id)
        total = query.count()
        items = (
            query.order_by(Footprint.viewed_at.desc(), Footprint.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
