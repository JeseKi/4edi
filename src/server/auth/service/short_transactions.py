"""认证模块请求侧短事务：法律文档接受记录与资格判断。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.compliance import current_document_versions

from ..models import LegalAcceptance

_USER_DOCUMENT_TYPES = ("user_agreement", "privacy_policy")


def assert_current_versions(*, user_agreement_version: str, privacy_policy_version: str) -> None:
    current = current_document_versions()
    supplied = {
        "user_agreement": user_agreement_version,
        "privacy_policy": privacy_policy_version,
    }
    stale = [name for name in _USER_DOCUMENT_TYPES if supplied[name] != current[name]]
    if stale:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请阅读并确认当前版本的用户服务协议和隐私政策",
        )


def record_user_acceptances(
    db: Session,
    *,
    user_id: int,
    user_agreement_version: str,
    privacy_policy_version: str,
    client_ip: str | None,
    user_agent: str | None,
) -> None:
    assert_current_versions(
        user_agreement_version=user_agreement_version,
        privacy_policy_version=privacy_policy_version,
    )
    supplied = {
        "user_agreement": user_agreement_version,
        "privacy_policy": privacy_policy_version,
    }
    now = datetime.now(timezone.utc)
    for document_type, document_version in supplied.items():
        exists = (
            db.query(LegalAcceptance.id)
            .filter(
                LegalAcceptance.user_id == user_id,
                LegalAcceptance.document_type == document_type,
                LegalAcceptance.document_version == document_version,
            )
            .first()
        )
        if exists is None:
            db.add(
                LegalAcceptance(
                    user_id=user_id,
                    document_type=document_type,
                    document_version=document_version,
                    accepted_at=now,
                    client_ip=(client_ip or "")[:80] or None,
                    user_agent=(user_agent or "")[:500] or None,
                )
            )
    db.flush()


def current_acceptance_status(db: Session, user_id: int) -> dict:
    current = current_document_versions()
    accepted = {
        row.document_type
        for row in db.query(LegalAcceptance)
        .filter(
            LegalAcceptance.user_id == user_id,
            LegalAcceptance.document_type.in_(_USER_DOCUMENT_TYPES),
        )
        .all()
        if row.document_version == current.get(row.document_type)
    }
    user_accepted = "user_agreement" in accepted
    privacy_accepted = "privacy_policy" in accepted
    return {
        "user_agreement_version": current["user_agreement"],
        "privacy_policy_version": current["privacy_policy"],
        "user_agreement_accepted": user_accepted,
        "privacy_policy_accepted": privacy_accepted,
        "all_current_accepted": user_accepted and privacy_accepted,
    }


def assert_current_user_acceptances(db: Session, user_id: int) -> None:
    if not current_acceptance_status(db, user_id)["all_current_accepted"]:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="请先确认当前版本的用户服务协议和隐私政策",
        )


def record_document_acceptance(
    db: Session,
    *,
    user_id: int,
    document_type: str,
    document_version: str,
    client_ip: str | None,
    user_agent: str | None,
) -> LegalAcceptance:
    current = current_document_versions()
    if document_type not in current or current[document_type] != document_version:
        raise HTTPException(status_code=422, detail="协议版本已更新，请重新阅读")
    acceptance = (
        db.query(LegalAcceptance)
        .filter(
            LegalAcceptance.user_id == user_id,
            LegalAcceptance.document_type == document_type,
            LegalAcceptance.document_version == document_version,
        )
        .first()
    )
    if acceptance is not None:
        return acceptance
    acceptance = LegalAcceptance(
        user_id=user_id,
        document_type=document_type,
        document_version=document_version,
        client_ip=(client_ip or "")[:80] or None,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(acceptance)
    db.flush()
    return acceptance
