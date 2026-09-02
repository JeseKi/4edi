"""网站主体与合规策略配置。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field


class ComplianceConfig(BaseModel):
    site_name: str = Field(default="沐泽健康")
    legal_entity_name: str = Field(default="杭州沐泽健康管理有限公司")
    legal_entity_credit_code: str = Field(default="")
    registered_address: str = Field(default="")
    service_email: str = Field(default="")
    icp_record_number: str = Field(default="浙ICP备2026035190号-1")
    user_agreement_version: str = Field(default="2026-09-02")
    privacy_policy_version: str = Field(default="2026-09-02")
    merchant_agreement_version: str = Field(default="2026-09-02")
    legal_documents_approved: bool = Field(default=False)
    sensitive_data_encryption_key: str = Field(
        default="dev-compliance-key-change-me",
        description="实名及商家证件号码加密密钥；生产环境必须覆盖。",
    )
    material_retention_days: int = Field(default=1095, ge=365, le=3650)
    qualification_valid_months: int = Field(default=6, ge=1, le=24)


if TYPE_CHECKING:
    compliance_config: ComplianceConfig


def __getattr__(name: str) -> Any:
    if name == "compliance_config":
        from src.server.config import global_config

        return global_config.compliance
    raise AttributeError(name)


__all__ = ["ComplianceConfig", "compliance_config"]
