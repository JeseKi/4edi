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
    if not compliance_config.legal_entity_credit_code.strip():
        raise ValueError(
            "平台统一社会信用代码未配置，暂不能生成正式商家入驻协议"
        )
    document = get_legal_document("merchant_agreement")
    version = str(document["version"])
    agreement_number = (
        f"M-{version.replace('-', '')}-{shop.id:06d}-{secrets.token_hex(3).upper()}"
    )
    signature_page = f"""

---

## 九、签约主体与电子确认

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

平台将本协议完整文本作为签约要约向乙方展示。乙方已完成实名认证的店主账号阅读完整协议，主动勾选并点击“确认签署电子协议”后，本协议即由双方以电子方式签署、成立并生效。系统将协议编号、版本、完整正文及签约留痕一并归档，双方均可在线查看、打印或保存。
"""
    content = str(document["content_markdown"]).rstrip() + signature_page
    draft_content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return AgreementSnapshot(
        agreement_number=agreement_number,
        document_version=version,
        content_markdown=content,
        draft_content_sha256=draft_content_sha256,
    )
