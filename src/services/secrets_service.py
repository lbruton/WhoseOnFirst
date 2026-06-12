"""
Secrets Service — symmetric encryption primitives for at-rest credential storage.

This module provides Fernet (authenticated symmetric encryption) wrapped
around a key derived from the ``SECRET_KEY`` environment variable via
PBKDF2HMAC-SHA256 (1.2M iterations, fixed salt). It is used by
``SettingsService`` to transparently encrypt/decrypt rows whose
``value_type == "encrypted"`` (e.g. ``twilio_auth_token``).

Design notes (per WHO-43 design.md §Component 1):

* Salt is hardcoded module-level constant ``_SALT``. Salts are not secrets;
  their job is to defeat precomputed rainbow tables. The version suffix
  (``-v1``) reserves room for rotation if the parameters ever change.
* The derived ``Fernet`` instance is a lazy module-level singleton. PBKDF2
  cost is paid once per process; encrypt/decrypt thereafter is microseconds.
* ``SecretsService`` is a thin OO wrapper so callers consume a familiar
  service-layer object. Methods delegate to the module singleton.
* If ``SECRET_KEY`` is unset, ``is_available()`` returns ``False`` quietly,
  but ``encrypt()`` / ``decrypt()`` raise ``SecretsConfigurationError`` so
  callers can distinguish missing-config from cryptographic-failure
  (``cryptography.fernet.InvalidToken``).
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken  # noqa: F401  (re-exported via type hints)
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# LOCKED — do not change. Versioned for future rotation.
_SALT: bytes = b"whoseonfirst-fernet-pbkdf2-salt-v1"

# LOCKED — PBKDF2 iteration count. Do NOT lower for "speed".
_PBKDF2_ITERATIONS: int = 1_200_000

# Lazy module-level singleton. Reset by tests via monkeypatch.setattr.
_fernet_singleton: Optional[Fernet] = None


class SecretsConfigurationError(Exception):
    """
    Raised when ``SECRET_KEY`` env var is missing or empty.

    Distinguishes a missing-config error from a cryptographic failure
    (``cryptography.fernet.InvalidToken``). Routes catch this and translate
    to HTTP 500 with a user-actionable message.
    """


def _derive_key(secret: str) -> bytes:
    """
    Derive a 32-byte URL-safe-base64 Fernet key from ``secret`` via PBKDF2HMAC-SHA256.

    Args:
        secret: The master secret (typically ``os.environ["SECRET_KEY"]``).

    Returns:
        URL-safe base64-encoded 32-byte key suitable for ``Fernet(...)``.
    """
    kdf = PBKDF2HMAC(
        algorithm=SHA256(),
        length=32,
        salt=_SALT,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


def _get_fernet() -> Fernet:
    """
    Return the lazy module-level Fernet singleton, building it on first call.

    Reads ``SECRET_KEY`` from the environment, derives a Fernet key, and
    caches the resulting ``Fernet`` instance for the lifetime of the process.

    Returns:
        The cached ``Fernet`` instance.

    Raises:
        SecretsConfigurationError: If ``SECRET_KEY`` is unset or empty.
    """
    global _fernet_singleton
    if _fernet_singleton is None:
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            raise SecretsConfigurationError(
                "SECRET_KEY environment variable is missing or empty — "
                "cannot derive Fernet key for at-rest encryption."
            )
        _fernet_singleton = Fernet(_derive_key(secret))
    return _fernet_singleton


class SecretsService:
    """
    Symmetric encryption primitives for at-rest credential storage.

    Wraps Fernet (AES-128-CBC + HMAC-SHA256) keyed via PBKDF2HMAC-SHA256
    against the ``SECRET_KEY`` env var. Methods delegate to a lazy
    module-level singleton so PBKDF2 cost is paid once per process.

    Usage:
        svc = SecretsService()
        if svc.is_available():
            ciphertext = svc.encrypt("sensitive value")
            plaintext = svc.decrypt(ciphertext)
    """

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt ``plaintext`` and return URL-safe base64 ciphertext.

        Args:
            plaintext: The string to encrypt.

        Returns:
            Fernet ciphertext as a URL-safe ASCII string suitable for
            persistence in a ``settings.value`` column.

        Raises:
            SecretsConfigurationError: If ``SECRET_KEY`` is unset.
        """
        token = _get_fernet().encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt Fernet ``ciphertext`` and return the original plaintext.

        Args:
            ciphertext: URL-safe base64 Fernet token previously produced
                by :meth:`encrypt`.

        Returns:
            Decrypted plaintext.

        Raises:
            SecretsConfigurationError: If ``SECRET_KEY`` is unset.
            cryptography.fernet.InvalidToken: If the ciphertext is tampered,
                truncated, or was produced under a different ``SECRET_KEY``.
        """
        plaintext = _get_fernet().decrypt(ciphertext.encode("ascii"))
        return plaintext.decode("utf-8")

    def is_available(self) -> bool:
        """
        Return ``True`` if ``SECRET_KEY`` is set and non-empty.

        Side-effect-free probe used by ``SettingsService`` and health
        endpoints to decide whether to attempt encryption at all. Does
        NOT instantiate the Fernet singleton.

        Returns:
            ``True`` if encryption is available; ``False`` otherwise.
        """
        return bool(os.environ.get("SECRET_KEY"))
