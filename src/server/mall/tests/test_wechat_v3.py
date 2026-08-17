# -*- coding: utf-8 -*-
"""微信支付 APIv3 配置解析测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.server.mall.payment.wechat_v3 import WeChatPayV3Provider


def test_cert_serial_no_falls_back_to_merchant_certificate(tmp_path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(0xABC123)
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    cert_path = tmp_path / "apiclient_cert.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    provider = WeChatPayV3Provider(
        app_id="app-id",
        merchant_id="merchant-id",
        private_key_path=str(tmp_path / "apiclient_key.pem"),
        merchant_cert_path=str(cert_path),
        platform_cert_dir="",
        cert_serial_no="",
        apiv3_key="a" * 32,
    )

    assert provider._resolved_cert_serial_no() == "ABC123"


def test_platform_public_key_bypasses_empty_certificate_cache(tmp_path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_path = tmp_path / "apiclient_key.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_key_path = tmp_path / "pub_key.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    provider = WeChatPayV3Provider(
        app_id="app-id",
        merchant_id="merchant-id",
        private_key_path=str(private_key_path),
        merchant_cert_path="",
        platform_cert_dir=str(tmp_path / "empty-platform"),
        public_key_path=str(public_key_path),
        public_key_id="PUB_KEY_ID_TEST",
        cert_serial_no="merchant-cert-serial",
        apiv3_key="a" * 32,
    )

    assert provider._get_client() is not None
