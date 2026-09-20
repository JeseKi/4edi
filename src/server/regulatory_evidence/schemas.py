from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.server.information.models import InformationStatus
from src.server.information.schemas import PublisherVerificationOut
from src.server.mall.models import ShopStatus

EvidenceType = Literal["publisher_verification", "shop_qualification"]


class EvidenceLinkCreateIn(BaseModel):
    evidence_type: EvidenceType
    resource_id: int = Field(..., ge=1)


class EvidenceLinkOut(BaseModel):
    id: int
    evidence_type: EvidenceType
    resource_id: int
    token_hint: str
    created_by_user_id: int
    created_at: datetime
    revoked_at: datetime | None
    last_accessed_at: datetime | None
    access_count: int

    model_config = {"from_attributes": True}


class EvidenceLinkCreatedOut(EvidenceLinkOut):
    token: str
    share_path: str


class RegulatoryInformationPostOut(BaseModel):
    id: int
    title: str
    category: str
    category_name: str
    price: str | None
    content: str
    attributes: dict[str, str] | None
    contact_name: str
    contact_phone: str | None
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    status: InformationStatus
    reject_reason: str | None


class RegulatoryPublisherEvidenceOut(BaseModel):
    verification: PublisherVerificationOut
    posts: list[RegulatoryInformationPostOut]


class RegulatoryShopOut(BaseModel):
    id: int
    owner_user_id: int
    name: str
    real_name: str | None
    identity_number_masked: str | None
    business_license_asset_id: str | None
    identity_front_asset_id: str | None
    identity_back_asset_id: str | None
    legal_entity_name: str | None
    unified_social_credit_code: str | None
    legal_representative: str | None
    registered_address: str | None
    business_address: str | None
    business_license_valid_until: date | None
    business_license_long_term: bool
    last_qualification_checked_at: datetime | None
    qualification_valid_until: datetime | None
    registration_status: str | None
    status: ShopStatus
    approved_at: datetime | None


class RegulatoryShopReviewOut(BaseModel):
    id: int
    result: str
    verification_source: str
    checked_at: datetime
    reviewer_user_id: int
    registration_status: str
    reject_reason: str | None


class RegulatoryShopEvidenceOut(BaseModel):
    shop: RegulatoryShopOut
    qualification_reviews: list[RegulatoryShopReviewOut]


class RegulatoryEvidenceOut(BaseModel):
    evidence_type: EvidenceType
    publisher_verification: RegulatoryPublisherEvidenceOut | None = None
    shop_qualification: RegulatoryShopEvidenceOut | None = None
