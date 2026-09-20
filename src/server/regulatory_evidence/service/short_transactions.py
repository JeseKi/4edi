from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.server.files.models import FileAsset
from src.server.files.service.short_transactions import FileAssetSnapshot
from src.server.information import service as information_service
from src.server.information.models import PublisherVerification
from src.server.mall import service as mall_service
from src.server.mall.models import Shop
from src.server.mall.schemas import (
    ShopOut,
    ShopQualificationReviewOut,
)

from ..models import RegulatoryEvidenceLink

PUBLISHER_VERIFICATION = "publisher_verification"
SHOP_QUALIFICATION = "shop_qualification"
EVIDENCE_TYPES = frozenset({PUBLISHER_VERIFICATION, SHOP_QUALIFICATION})
TOKEN_LENGTH = 32
_TOKEN_ALPHABET = string.ascii_letters + string.digits


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_token() -> str:
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def _assert_resource_exists(db: Session, evidence_type: str, resource_id: int) -> None:
    if evidence_type == PUBLISHER_VERIFICATION:
        resource = db.get(PublisherVerification, resource_id)
    elif evidence_type == SHOP_QUALIFICATION:
        resource = db.get(Shop, resource_id)
    else:
        raise HTTPException(status_code=422, detail="不支持的监管取证类型")
    if resource is None:
        raise HTTPException(status_code=404, detail="取证记录不存在")


def create_link(
    db: Session,
    *,
    evidence_type: str,
    resource_id: int,
    created_by_user_id: int,
) -> tuple[RegulatoryEvidenceLink, str]:
    _assert_resource_exists(db, evidence_type, resource_id)
    while True:
        token = _new_token()
        digest = _token_hash(token)
        exists = (
            db.query(RegulatoryEvidenceLink.id)
            .filter(RegulatoryEvidenceLink.token_hash == digest)
            .first()
        )
        if exists is None:
            break
    link = RegulatoryEvidenceLink(
        token_hash=digest,
        token_hint=token[-6:],
        evidence_type=evidence_type,
        resource_id=resource_id,
        created_by_user_id=created_by_user_id,
    )
    db.add(link)
    db.flush()
    return link, token


def list_links(
    db: Session, *, evidence_type: str, resource_id: int
) -> list[RegulatoryEvidenceLink]:
    if evidence_type not in EVIDENCE_TYPES:
        raise HTTPException(status_code=422, detail="不支持的监管取证类型")
    return (
        db.query(RegulatoryEvidenceLink)
        .filter(
            RegulatoryEvidenceLink.evidence_type == evidence_type,
            RegulatoryEvidenceLink.resource_id == resource_id,
        )
        .order_by(
            RegulatoryEvidenceLink.created_at.desc(),
            RegulatoryEvidenceLink.id.desc(),
        )
        .all()
    )


def revoke_link(db: Session, link_id: int) -> RegulatoryEvidenceLink:
    link = db.get(RegulatoryEvidenceLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="监管核验链接不存在")
    if link.revoked_at is None:
        link.revoked_at = _utcnow()
        db.flush()
    return link


def _resolve_active_link(db: Session, token: str) -> RegulatoryEvidenceLink:
    if len(token) != TOKEN_LENGTH or any(ch not in _TOKEN_ALPHABET for ch in token):
        raise HTTPException(status_code=404, detail="监管核验链接不存在或已失效")
    link = (
        db.query(RegulatoryEvidenceLink)
        .filter(RegulatoryEvidenceLink.token_hash == _token_hash(token))
        .first()
    )
    if link is None or link.revoked_at is not None:
        raise HTTPException(status_code=404, detail="监管核验链接不存在或已失效")
    return link


def get_evidence_payload(db: Session, token: str) -> dict:
    link = _resolve_active_link(db, token)
    if link.evidence_type == PUBLISHER_VERIFICATION:
        evidence = information_service.get_verification_evidence(
            db, link.resource_id
        )
        for post in evidence["posts"]:
            post["contact_phone"] = information_service.mask_phone(
                post.get("contact_phone")
            )
        payload = {
            "evidence_type": PUBLISHER_VERIFICATION,
            "publisher_verification": evidence,
            "shop_qualification": None,
        }
    elif link.evidence_type == SHOP_QUALIFICATION:
        shop, reviews = mall_service.admin_shop_detail(db, link.resource_id)
        payload = {
            "evidence_type": SHOP_QUALIFICATION,
            "publisher_verification": None,
            "shop_qualification": {
                "shop": ShopOut.model_validate(shop),
                "qualification_reviews": [
                    ShopQualificationReviewOut.model_validate(review)
                    for review in reviews
                ],
            },
        }
    else:
        raise HTTPException(status_code=404, detail="监管核验链接不存在或已失效")
    link.last_accessed_at = _utcnow()
    link.access_count += 1
    db.flush()
    return payload


def _allowed_asset_ids(db: Session, link: RegulatoryEvidenceLink) -> set[str]:
    if link.evidence_type == PUBLISHER_VERIFICATION:
        verification = db.get(PublisherVerification, link.resource_id)
        if verification is None:
            return set()
        return {
            asset_id
            for asset_id in (
                verification.document_front_asset_id,
                verification.document_back_asset_id,
            )
            if asset_id
        }
    if link.evidence_type == SHOP_QUALIFICATION:
        shop = db.get(Shop, link.resource_id)
        if shop is None:
            return set()
        return {
            asset_id
            for asset_id in (
                shop.business_license_asset_id,
                shop.identity_front_asset_id,
                shop.identity_back_asset_id,
            )
            if asset_id
        }
    return set()


def get_evidence_asset_snapshot(
    db: Session, token: str, asset_id: str
) -> FileAssetSnapshot:
    link = _resolve_active_link(db, token)
    if asset_id not in _allowed_asset_ids(db, link):
        raise HTTPException(status_code=404, detail="材料不存在")
    asset = db.get(FileAsset, asset_id)
    if asset is None or asset.status != "available":
        raise HTTPException(status_code=404, detail="材料不存在")
    return FileAssetSnapshot(
        id=asset.id,
        storage_key=asset.storage_key,
        storage_driver=asset.storage_driver,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        status=asset.status,
    )
