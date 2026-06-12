"""
Tests for SecretsService — symmetric encryption primitives.

Covers WHO-43 Requirement 2 (encrypted-at-rest storage) and Requirement 6
(SECRET_KEY required for encryption layer). These tests define the contract
for the not-yet-existent SecretsService class. They are RED-phase TDD tests
written before any production code (Task 0.5 of WHO-43-admin-ui-twilio-credentials).

Contract (per design.md §Component 1):
- Class: SecretsService
- Methods: encrypt(plaintext: str) -> str
           decrypt(ciphertext: str) -> str
           is_available() -> bool
- Custom exception: SecretsConfigurationError raised when SECRET_KEY missing
- Implementation: Fernet + PBKDF2HMAC-SHA256 with hardcoded salt
  b"whoseonfirst-fernet-pbkdf2-salt-v1" and 1.2M iterations, key derived
  from SECRET_KEY env var.

NOTE for implementer (Task 2): The SecretsService is expected to use a
lazy module-level Fernet singleton. These tests do NOT reach into module
internals (e.g. _fernet_singleton). Instead they construct a fresh
SecretsService() per test and rely on monkeypatch.setenv/delenv. If your
implementation caches the Fernet instance in a way that survives env-var
changes between tests in the same process, you may need to expose a reset
hook (e.g. a module-level function `_reset_fernet_singleton()`) and call
it from a fixture here. Do that ONLY if these tests fail post-implementation
because of cache staleness — by default, tests assume each SecretsService()
re-reads SECRET_KEY at the moment of first encrypt/decrypt/is_available.
"""

import pytest

from cryptography.fernet import InvalidToken


# Tests intentionally import from src.services — the import will fail until
# Task 2 creates the module. That's the red-phase signal.


class TestEncryptDecrypt:
    """Round-trip and ciphertext-property tests for encrypt/decrypt."""

    def test_encrypt_decrypt_round_trip(self, monkeypatch):
        """Covers REQ-2 AC 1, REQ-2 AC 5 (round-trip path).

        encrypt(x) followed by decrypt(result) must return the original
        plaintext for a variety of inputs including unicode and edge-length
        strings.
        """
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-pbkdf2-derivation-xyz")  # gitleaks:allow (test-only fake key)

        from src.services.secrets_service import SecretsService

        svc = SecretsService()
        plaintexts = [
            "simple ascii token",
            "AC1234567890abcdef" * 2,  # 36 chars (Twilio token-ish length)
            "x",                       # 1 char
            "uñicøde ••• secret \U0001f512",  # unicode
            "a" * 200,                 # max-length token edge
        ]
        for pt in plaintexts:
            ct = svc.encrypt(pt)
            assert isinstance(ct, str)
            assert ct != pt, f"ciphertext should not equal plaintext for {pt!r}"
            assert svc.decrypt(ct) == pt

    def test_encrypt_returns_different_ciphertext_each_call(self, monkeypatch):
        """Covers REQ-2 AC 1 (Fernet uses random IVs).

        Fernet uses a random IV per call, so the same plaintext encrypted
        twice produces two different ciphertexts. Both must still round-trip.
        """
        monkeypatch.setenv("SECRET_KEY", "stable-secret-key-for-iv-test")  # gitleaks:allow (test-only fake key)

        from src.services.secrets_service import SecretsService

        svc = SecretsService()
        plaintext = "the same plaintext, encrypted twice"
        ct1 = svc.encrypt(plaintext)
        ct2 = svc.encrypt(plaintext)
        assert ct1 != ct2, "Fernet must use a random IV per encrypt call"
        assert svc.decrypt(ct1) == plaintext
        assert svc.decrypt(ct2) == plaintext

    def test_decrypt_invalid_token_raises_on_tampered_ciphertext(self, monkeypatch):
        """Covers REQ-2 AC 5 (tampered ciphertext is detected).

        Fernet authenticates ciphertext via HMAC. Flipping a byte in the
        middle of the token must raise cryptography.fernet.InvalidToken,
        not silently return garbage.
        """
        monkeypatch.setenv("SECRET_KEY", "tamper-detection-key-12345")  # gitleaks:allow (test-only fake key)

        from src.services.secrets_service import SecretsService

        svc = SecretsService()
        ct = svc.encrypt("sensitive payload")
        # Tamper: flip a character in the middle of the ciphertext
        midpoint = len(ct) // 2
        # Pick a swap target that produces a different valid base64 char
        original = ct[midpoint]
        replacement = "A" if original != "A" else "B"
        tampered = ct[:midpoint] + replacement + ct[midpoint + 1:]
        assert tampered != ct

        with pytest.raises(InvalidToken):
            svc.decrypt(tampered)

    def test_decrypt_invalid_token_raises_with_wrong_key(self, monkeypatch):
        """Covers REQ-2 AC 5, REQ-6 AC 4 (key rotation breaks old ciphertexts).

        Encrypt with key A, then change SECRET_KEY to key B and try to
        decrypt — must raise InvalidToken because the derived Fernet key
        differs.
        """
        monkeypatch.setenv("SECRET_KEY", "key-a-for-encryption-only")  # gitleaks:allow (test-only fake key)

        from src.services.secrets_service import SecretsService

        svc_a = SecretsService()
        ct = svc_a.encrypt("payload encrypted under key A")

        # Rotate the key. Construct a new SecretsService — the implementation
        # may cache its Fernet instance via a module singleton, so we need
        # the new key to take effect. If the implementer's lazy-init is
        # genuinely lazy (re-reads env on each call), this just works.
        # Otherwise the test will surface a stale-cache bug, which is
        # exactly what the contract demands the implementer fix.
        monkeypatch.setenv("SECRET_KEY", "key-b-totally-different-key")  # gitleaks:allow (test-only fake key)

        # Force re-init: ask for a fresh service AND, if the implementation
        # keeps a module-level Fernet, reset it. We probe for a reset hook
        # but don't fail the test if it doesn't exist.
        import src.services.secrets_service as ss_mod
        for attr in ("_reset_fernet_singleton", "_fernet_singleton", "_fernet"):
            if hasattr(ss_mod, attr) and callable(getattr(ss_mod, attr, None)):
                getattr(ss_mod, attr)()
                break
            if hasattr(ss_mod, attr):
                # If it's a cached instance attribute, clear it.
                setattr(ss_mod, attr, None)

        svc_b = SecretsService()
        with pytest.raises(InvalidToken):
            svc_b.decrypt(ct)


class TestIsAvailable:
    """Tests for SecretsService.is_available()."""

    def test_is_available_true_when_secret_key_set(self, monkeypatch):
        """Covers REQ-6 AC 1, REQ-6 AC 2 (boot health check)."""
        monkeypatch.setenv("SECRET_KEY", "any-non-empty-key-value-works")  # gitleaks:allow (test-only fake key)

        from src.services.secrets_service import SecretsService

        svc = SecretsService()
        assert svc.is_available() is True

    def test_is_available_false_when_secret_key_missing(self, monkeypatch):
        """Covers REQ-6 AC 1, REQ-6 AC 2 (graceful boot without SECRET_KEY)."""
        monkeypatch.delenv("SECRET_KEY", raising=False)

        # Reset any cached Fernet instance from prior tests.
        import src.services.secrets_service as ss_mod
        for attr in ("_reset_fernet_singleton",):
            if hasattr(ss_mod, attr) and callable(getattr(ss_mod, attr, None)):
                getattr(ss_mod, attr)()
                break
        for attr in ("_fernet_singleton", "_fernet"):
            if hasattr(ss_mod, attr):
                setattr(ss_mod, attr, None)

        from src.services.secrets_service import SecretsService

        svc = SecretsService()
        assert svc.is_available() is False


class TestSecretsConfigurationError:
    """Tests for the custom SecretsConfigurationError exception."""

    def test_encrypt_raises_secrets_configuration_error_when_key_missing(
        self, monkeypatch
    ):
        """Covers REQ-6 AC 1, REQ-6 AC 3 (clear error when SECRET_KEY missing).

        encrypt MUST raise SecretsConfigurationError specifically (NOT a
        generic KeyError, ValueError, or os.environ KeyError). Routes catch
        this and translate to HTTP 500 per design.md §Error Handling.
        """
        monkeypatch.delenv("SECRET_KEY", raising=False)

        # Reset any cached Fernet instance from prior tests.
        import src.services.secrets_service as ss_mod
        for attr in ("_reset_fernet_singleton",):
            if hasattr(ss_mod, attr) and callable(getattr(ss_mod, attr, None)):
                getattr(ss_mod, attr)()
                break
        for attr in ("_fernet_singleton", "_fernet"):
            if hasattr(ss_mod, attr):
                setattr(ss_mod, attr, None)

        from src.services.secrets_service import (
            SecretsService,
            SecretsConfigurationError,
        )

        svc = SecretsService()
        with pytest.raises(SecretsConfigurationError):
            svc.encrypt("any plaintext")
