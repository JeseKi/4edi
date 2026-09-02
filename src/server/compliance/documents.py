"""读取、渲染并校验仓库内版本化法律文档。"""

from __future__ import annotations

from pathlib import Path

from src.server.settings_sources import PROJECT_ROOT

from .config import compliance_config

DOCUMENT_TYPES = ("user_agreement", "privacy_policy", "merchant_agreement")
_TITLES = {
    "user_agreement": "用户服务协议",
    "privacy_policy": "隐私政策",
    "merchant_agreement": "商家入驻协议",
}
_DOCUMENT_ROOT = PROJECT_ROOT / "legal_documents"


def current_document_versions() -> dict[str, str]:
    return {
        "user_agreement": compliance_config.user_agreement_version,
        "privacy_policy": compliance_config.privacy_policy_version,
        "merchant_agreement": compliance_config.merchant_agreement_version,
    }


def public_site_config() -> dict[str, str | bool]:
    config = compliance_config
    return {
        "site_name": config.site_name,
        "legal_entity_name": config.legal_entity_name,
        "registered_address": config.registered_address,
        "service_email": config.service_email,
        "icp_record_number": config.icp_record_number,
        "configuration_complete": _public_fields_complete(),
    }


def _public_fields_complete() -> bool:
    config = compliance_config
    return all(
        value.strip()
        for value in (
            config.site_name,
            config.legal_entity_name,
            config.legal_entity_credit_code,
            config.registered_address,
            config.service_email,
            config.icp_record_number,
        )
    )


def _document_path(document_type: str, version: str) -> Path:
    if document_type not in DOCUMENT_TYPES:
        raise KeyError("未知协议类型")
    if not version or "/" in version or "\\" in version or ".." in version:
        raise KeyError("协议版本无效")
    return _DOCUMENT_ROOT / document_type / f"{version}.md"


def get_legal_document(document_type: str, version: str | None = None) -> dict:
    versions = current_document_versions()
    resolved_version = version or versions.get(document_type)
    if resolved_version is None:
        raise KeyError("未知协议类型")
    path = _document_path(document_type, resolved_version)
    if not path.is_file():
        raise KeyError("协议版本不存在")
    content = path.read_text(encoding="utf-8")
    replacements = {
        "{{site_name}}": compliance_config.site_name,
        "{{legal_entity_name}}": compliance_config.legal_entity_name,
        "{{registered_address}}": compliance_config.registered_address or "（待部署配置）",
        "{{service_email}}": compliance_config.service_email or "（待部署配置）",
        "{{icp_record_number}}": compliance_config.icp_record_number,
        "{{version}}": resolved_version,
    }
    for key, value in replacements.items():
        content = content.replace(key, value)
    return {
        "document_type": document_type,
        "title": _TITLES[document_type],
        "version": resolved_version,
        "effective_at": resolved_version,
        "is_current": resolved_version == versions[document_type],
        "content_markdown": content,
    }


def list_legal_documents() -> list[dict]:
    return [get_legal_document(document_type) for document_type in DOCUMENT_TYPES]


def validate_compliance_readiness(*, app_env: str, enabled_features: set[str] | frozenset[str]) -> None:
    if app_env != "prod" or not ({"mall", "information"} & set(enabled_features)):
        return
    failures: list[str] = []
    if not _public_fields_complete():
        failures.append("网站主体名称、统一社会信用代码、地址、客服邮箱和备案号必须完整")
    if not compliance_config.legal_documents_approved:
        failures.append("三份法律文档尚未标记为已完成法务确认")
    if compliance_config.sensitive_data_encryption_key == "dev-compliance-key-change-me":
        failures.append("COMPLIANCE_ENCRYPTION_KEY 必须使用生产独立密钥")
    for document_type, version in current_document_versions().items():
        if not _document_path(document_type, version).is_file():
            failures.append(f"缺少 {document_type} 版本 {version}")
    if failures:
        raise ValueError("生产合规配置不完整：" + "；".join(failures))
