"""Tests for at-rest encryption of provider API keys (src/core/crypto.py).

Spec provenance (blueprint Step 2 / security finding #4):
  B1. encrypt_secret output carries the "enc:v1:" prefix.
  B2. decrypt_secret(encrypt_secret(x)) == x.
  B3. Legacy unprefixed plaintext passes through decrypt_secret UNCHANGED.
      This clause is what removes the need for an Alembic data migration —
      if it breaks, every pre-existing stored key becomes unreadable.
  B4. None / empty pass through both functions unchanged.
  B5. encrypt_secret raises ValueError when app_secret is unset or < 32 chars.
  B6. The same plaintext encrypts to DIFFERENT ciphertexts (Fernet random IV),
      both decrypting back to the original — proves encryption, not encoding.
  B7. GET /settings never returns a key value, only *_key_set booleans.
"""

import pytest

import src.core.crypto as crypto_mod
from src.core.config import settings as _settings
from src.core.crypto import decrypt_secret, encrypt_secret

_PLAIN = "sk-ant-api03-not-a-real-key"


def _reset_derived_key() -> None:
    """Clear the module-level derived-key cache so app_secret changes take effect."""
    crypto_mod._derived_key = None


def test_encrypt_secret_carries_version_prefix() -> None:
    """B1 — stored value is tagged with the scheme version."""
    assert encrypt_secret(_PLAIN).startswith("enc:v1:")


def test_encrypt_decrypt_round_trip() -> None:
    """B2 — a key survives a store/load cycle intact."""
    assert decrypt_secret(encrypt_secret(_PLAIN)) == _PLAIN


def test_legacy_plaintext_passes_through_unchanged() -> None:
    """B3 — rows written before encryption existed stay readable."""
    legacy = "sk-legacy-plaintext-value"
    assert not legacy.startswith("enc:v1:")
    assert decrypt_secret(legacy) == legacy


@pytest.mark.parametrize("empty", [None, ""])
def test_empty_values_pass_through_both_directions(empty) -> None:
    """B4 — absent keys are not mangled into ciphertext or errors."""
    assert encrypt_secret(empty) == empty
    assert decrypt_secret(empty) == empty


@pytest.mark.parametrize("bad_secret", ["", "too-short"])
def test_encrypt_requires_strong_app_secret(monkeypatch, bad_secret) -> None:
    """B5 — refuse to encrypt under a weak or absent APP_SECRET."""
    monkeypatch.setattr(_settings, "app_secret", bad_secret)
    _reset_derived_key()
    try:
        with pytest.raises(ValueError):
            encrypt_secret(_PLAIN)
    finally:
        _reset_derived_key()


def test_same_plaintext_yields_distinct_ciphertexts() -> None:
    """B6 — real encryption with a random IV, not deterministic encoding."""
    first = encrypt_secret(_PLAIN)
    second = encrypt_secret(_PLAIN)
    assert first != second, "identical ciphertexts imply encoding, not encryption"
    assert decrypt_secret(first) == _PLAIN
    assert decrypt_secret(second) == _PLAIN


@pytest.mark.asyncio
async def test_settings_endpoint_never_returns_key_values(client) -> None:
    """B7 — the API exposes only set/not-set booleans (security finding #4)."""
    res = await client.put("/settings", json={"anthropic_api_key": _PLAIN})
    assert res.status_code == 200

    body = res.json()
    assert body["anthropic_api_key_set"] is True
    assert "anthropic_api_key" not in body

    got = await client.get("/settings")
    assert got.status_code == 200
    serialised = got.text
    assert _PLAIN not in serialised, "plaintext key leaked in GET /settings body"
    assert "enc:v1:" not in serialised, "ciphertext leaked in GET /settings body"
