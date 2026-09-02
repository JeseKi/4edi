"""生成可审计、可打印的商家入驻协议定稿。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import secrets
from typing import Protocol

from src.server.compliance.config import compliance_config
from src.server.compliance.documents import get_legal_document


class AgreementShop(Protocol):
    id: int
    name: str
    legal_entity_name: str | None
    unified_social_credit_code: str | None
    legal_representative: str | None
    registered_address: str | None
    business_address: str | None


@dataclass(frozen=True)
class AgreementSnapshot:
    agreement_number: str
    document_version: str
    content_markdown: str
    draft_content_sha256: str


def _single_line(value: str | None) -> str:
    return " ".join((value or "").split()) or "（未填写）"


def build_agreement_snapshot(shop: AgreementShop) -> AgreementSnapshot:
    document = get_legal_document("merchant_agreement")
    version = str(document["version"])
    agreement_number = (
        f"M-{version.replace('-', '')}-{shop.id:06d}-{secrets.token_hex(3).upper()}"
    )
    signature_page = f"""

---

## 九、协议定稿与签署页

协议编号：{agreement_number}\\
协议版本：{version}\\
店铺名称：{_single_line(shop.name)}

### 甲方（平台）

企业全称：{_single_line(compliance_config.legal_entity_name)}\\
统一社会信用代码：{_single_line(compliance_config.legal_entity_credit_code)}\\
注册地址：{_single_line(compliance_config.registered_address)}\\
客服邮箱：{_single_line(compliance_config.service_email)}

### 乙方（商家）

企业全称：{_single_line(shop.legal_entity_name)}\\
统一社会信用代码：{_single_line(shop.unified_social_credit_code)}\\
法定代表人：{_single_line(shop.legal_representative)}\\
注册地址：{_single_line(shop.registered_address)}\\
实际经营地址：{_single_line(shop.business_address)}

甲方盖章：____________________\\
签署日期：______年____月____日

乙方盖章：____________________\\
法定代表人或授权代表签字：____________________\\
签署日期：______年____月____日

> 本协议以协议编号所对应的完整协议文本及双方最终签署文件为准。未经双方书面确认，任何一方不得擅自增删或修改协议内容。
"""
    content = str(document["content_markdown"]).rstrip() + signature_page
    draft_content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return AgreementSnapshot(
        agreement_number=agreement_number,
        document_version=version,
        content_markdown=content,
        draft_content_sha256=draft_content_sha256,
    )
