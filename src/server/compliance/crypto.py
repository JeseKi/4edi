"""使用 AES-GCM 加密需要留存但不应明文保存的字段。"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
import hashlib
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import compliance_config

_VERSION = "v1"
_AAD = b"4edi-compliance-sensitive-value-v1"


def _key() -> bytes:
    return hashlib.sha256(
        compliance_config.sensitive_data_encryption_key.encode("utf-8")
    ).digest()


def encrypt_sensitive_value(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("敏感字段不能为空")
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, normalized.encode("utf-8"), _AAD)
    return f"{_VERSION}:{urlsafe_b64encode(nonce + ciphertext).decode('ascii')}"


def decrypt_sensitive_value(value: str) -> str:
    try:
        version, encoded = value.split(":", maxsplit=1)
        payload = urlsafe_b64decode(encoded.encode("ascii"))
        if version != _VERSION or len(payload) <= 12:
            raise ValueError
        return AESGCM(_key()).decrypt(payload[:12], payload[12:], _AAD).decode("utf-8")
    except Exception as exc:
        raise ValueError("敏感字段解密失败") from exc
