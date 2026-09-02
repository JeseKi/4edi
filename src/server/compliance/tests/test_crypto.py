from __future__ import annotations

import pytest

from src.server.compliance.crypto import decrypt_sensitive_value, encrypt_sensitive_value


def test_sensitive_value_round_trip_does_not_store_plaintext() -> None:
    plaintext = "110101199001011234"
    encrypted = encrypt_sensitive_value(plaintext)

    assert encrypted.startswith("v1:")
    assert plaintext not in encrypted
    assert decrypt_sensitive_value(encrypted) == plaintext


def test_sensitive_value_rejects_tampering() -> None:
    encrypted = encrypt_sensitive_value("secret")
    replacement = "A" if encrypted[-1] != "A" else "B"

    with pytest.raises(ValueError, match="敏感字段解密失败"):
        decrypt_sensitive_value(encrypted[:-1] + replacement)
