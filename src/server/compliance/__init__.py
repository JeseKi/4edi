"""合规配置、版本化协议与敏感字段加密。

导出项使用延迟加载，避免系统配置模型导入 ``ComplianceConfig`` 时形成循环依赖。
"""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "ComplianceConfig":
        from .config import ComplianceConfig

        return ComplianceConfig
    if name in {"decrypt_sensitive_value", "encrypt_sensitive_value"}:
        from .crypto import decrypt_sensitive_value, encrypt_sensitive_value

        return {
            "decrypt_sensitive_value": decrypt_sensitive_value,
            "encrypt_sensitive_value": encrypt_sensitive_value,
        }[name]
    if name in {
        "DOCUMENT_TYPES",
        "current_document_versions",
        "get_legal_document",
        "list_legal_documents",
        "public_site_config",
        "validate_compliance_readiness",
    }:
        from . import documents

        return getattr(documents, name)
    raise AttributeError(name)

__all__ = [
    "ComplianceConfig",
    "DOCUMENT_TYPES",
    "current_document_versions",
    "decrypt_sensitive_value",
    "encrypt_sensitive_value",
    "get_legal_document",
    "list_legal_documents",
    "public_site_config",
    "validate_compliance_readiness",
]
