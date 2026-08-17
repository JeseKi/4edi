"""商城配置模型与共享配置访问器。"""

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field


class MallConfig(BaseModel):
    order_pay_timeout_minutes: int = Field(
        default=30,
        ge=1,
        le=4320,
        title="订单支付超时分钟数",
        description="未支付订单超过该时长后自动取消并恢复库存。",
    )
    auto_confirm_receipt_days: int = Field(
        default=7,
        ge=1,
        le=90,
        title="自动确认收货天数",
        description="发货后买家未确认收货时，超过该天数自动确认并解冻资金。",
    )
    refund_auto_agree_hours: int = Field(
        default=72,
        ge=1,
        le=720,
        title="退款超时自动同意小时数",
        description="买家提交退款申请后，卖家超过该时长未处理时系统自动同意。",
    )
    default_deposit_fen: int = Field(
        default=1000,
        ge=0,
        title="默认入驻保证金",
        description="店铺审核通过时记入店铺钱包的保证金金额（分）。",
    )
    freight_fen: int = Field(
        default=0,
        ge=0,
        title="默认运费",
        description="订单计算运费时的默认运费金额（分）。",
    )
    payment_mode: Literal["mock", "real"] = Field(
        default="mock",
        title="支付通道",
        description="mock 为本地模拟支付；real 为真实微信支付（需配置商户参数）。",
    )
    wechat_pay_app_id: str = Field(
        default="", title="微信支付 AppID", description="微信支付商户号绑定的应用 AppID。"
    )
    wechat_pay_merchant_id: str = Field(
        default="", title="微信支付商户号", description="微信支付直连商户号。"
    )
    wechat_pay_private_key_path: str = Field(
        default="", title="商户私钥路径", description="商户 API 证书私钥（apiclient_key.pem）路径。"
    )
    wechat_pay_merchant_cert_path: str = Field(
        default="",
        title="商户证书路径",
        description="商户 API 证书（apiclient_cert.pem）路径；为空时使用私钥同目录文件。",
    )
    wechat_pay_platform_cert_dir: str = Field(
        default="",
        title="微信支付平台证书缓存目录",
        description="微信支付平台证书缓存目录；为空时使用商户证书同目录的 platform 子目录。",
    )
    wechat_pay_public_key_path: str = Field(
        default="",
        title="微信支付平台公钥路径",
        description="微信支付平台公钥 PEM 路径；与平台公钥 ID 必须同时配置。",
    )
    wechat_pay_public_key_id: str = Field(
        default="",
        title="微信支付平台公钥 ID",
        description="微信支付平台公钥 ID；与平台公钥路径必须同时配置。",
    )
    wechat_pay_cert_serial_no: str = Field(
        default="", title="商户证书序列号", description="商户 API 证书序列号。"
    )
    wechat_pay_apiv3_key: str = Field(
        default="", title="APIv3 密钥", description="微信支付 APIv3 密钥。"
    )
    wechat_pay_notify_base_url: str = Field(
        default="", title="支付通知基础地址",
        description="微信支付回调公网基础地址，如 https://example.com；为空时使用应用域名。",
    )


if TYPE_CHECKING:
    mall_config: MallConfig


def __getattr__(name: str) -> Any:
    if name == "mall_config":
        from src.server.config import global_config

        return global_config.mall
    raise AttributeError(name)


__all__ = ["MallConfig", "mall_config"]
