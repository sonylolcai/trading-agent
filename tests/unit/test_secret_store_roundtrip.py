"""Unit tests for SecretStore encrypt/decrypt round-trip (task 3.3)."""
from __future__ import annotations
import sys
import pytest
from pa_agent.security.secret_store import SecretStore, mask_secret


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeFernet:
    """Deterministic fake Fernet: prepend 'FERNET:' to plaintext."""
    def encrypt(self, data: bytes) -> bytes:
        return b"FERNET:" + data
    def decrypt(self, token: bytes) -> bytes:
        if not token.startswith(b"FERNET:"):
            raise Exception("bad token")
        return token[7:]


@pytest.fixture()
def fernet_branch(monkeypatch, tmp_path):
    """Force the Fernet branch and use a tmp key path."""
    import pa_agent.security.secret_store as ss
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(ss, "_FERNET_KEY_PATH", tmp_path / "secret.key")
    # Patch _get_fernet to return our fake
    monkeypatch.setattr(ss, "_get_fernet", lambda: _FakeFernet())
    yield


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_fernet_round_trip(fernet_branch):
    """encrypt → decrypt returns original string."""
    original = "sk-test-abcdefgh"
    ct = SecretStore.encrypt(original)
    assert ct != original
    assert SecretStore.decrypt(ct) == original


def test_fernet_empty_string(fernet_branch):
    """Empty string encrypts to '' and decrypts to ''."""
    assert SecretStore.encrypt("") == ""
    assert SecretStore.decrypt("") == ""


def test_fernet_invalid_ciphertext_raises(fernet_branch):
    """Garbage ciphertext raises ValueError."""
    with pytest.raises(ValueError, match="invalid ciphertext"):
        SecretStore.decrypt("not-valid-base64!!!")


def test_dpapi_branch_monkeypatched(monkeypatch):
    """DPAPI branch dispatches to _encrypt_dpapi / _decrypt_dpapi."""
    import pa_agent.security.secret_store as ss
    monkeypatch.setattr(sys, "platform", "win32")

    calls: list[str] = []

    def fake_encrypt(pt: str) -> str:
        calls.append(f"enc:{pt}")
        return f"DPAPI:{pt}"

    def fake_decrypt(ct: str) -> str:
        calls.append(f"dec:{ct}")
        if not ct.startswith("DPAPI:"):
            raise ValueError("invalid ciphertext")
        return ct[6:]

    monkeypatch.setattr(ss, "_encrypt_dpapi", fake_encrypt)
    monkeypatch.setattr(ss, "_decrypt_dpapi", fake_decrypt)

    ct = SecretStore.encrypt("hello")
    assert ct == "DPAPI:hello"
    assert SecretStore.decrypt(ct) == "hello"
    assert calls == ["enc:hello", "dec:DPAPI:hello"]
