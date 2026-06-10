"""
Tests for SettingsService.

Covers: get_all_settings, set_setting (type detection), delete_setting,
        set_sms_template (validation), get_escalation_config,
        set_escalation_config, is_escalation_weekly_enabled,
        set_escalation_weekly_enabled

WHO-43 (Task 0.5, TDD red phase) extends this file with 3 tests for
transparent encrypt/decrypt when value_type="encrypted" — see
TestEncryptedSettings at the bottom of this module.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.services.settings_service import SettingsService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def service(db_session):
    return SettingsService(db_session)


class TestGetAllSettings:

    def test_empty_db_returns_empty_dict(self, service):
        result = service.get_all_settings()
        assert isinstance(result, dict)

    def test_returns_all_settings_after_set(self, service):
        service.set_setting("test_key", "test_value")
        result = service.get_all_settings()
        assert "test_key" in result


class TestSetSettingTypeDetection:

    def test_bool_value_detected_as_bool(self, service):
        service.set_setting("flag", True)
        # Verify it round-trips correctly
        result = service.get_all_settings()
        assert result.get("flag") is True

    def test_int_value_detected_as_int(self, service):
        service.set_setting("count", 42)
        result = service.get_all_settings()
        assert result.get("count") == 42

    def test_float_value_detected_as_float(self, service):
        service.set_setting("ratio", 1.5)
        result = service.get_all_settings()
        assert result.get("ratio") == 1.5

    def test_string_value_detected_as_str(self, service):
        service.set_setting("name", "Alice")
        result = service.get_all_settings()
        assert result.get("name") == "Alice"


class TestDeleteSetting:

    def test_delete_existing_setting_returns_true(self, service):
        service.set_setting("to_delete", "value")
        assert service.delete_setting("to_delete") is True

    def test_delete_nonexistent_setting_returns_false(self, service):
        assert service.delete_setting("does_not_exist") is False


class TestSetSmsTemplate:

    def test_empty_template_raises_value_error(self, service):
        with pytest.raises(ValueError, match="cannot be empty"):
            service.set_sms_template("")

    def test_whitespace_only_raises_value_error(self, service):
        with pytest.raises(ValueError, match="cannot be empty"):
            service.set_sms_template("   ")

    def test_valid_template_saves(self, service):
        template = "Hi {name}, your shift starts at {start_time}."
        result = service.set_sms_template(template)
        assert result is not None


class TestGetEscalationConfig:

    def test_returns_dict_with_defaults(self, service):
        config = service.get_escalation_config()
        assert "enabled" in config
        assert config["enabled"] is False
        assert config["primary_name"] is None
        assert config["secondary_name"] is None


class TestSetEscalationConfig:

    def test_sets_enabled_flag(self, service):
        service.set_escalation_config(enabled=True)
        config = service.get_escalation_config()
        assert config["enabled"] is True

    def test_sets_primary_contact(self, service):
        service.set_escalation_config(
            enabled=True,
            primary_name="Alice",
            primary_phone="+15551111111"
        )
        config = service.get_escalation_config()
        assert config["primary_name"] == "Alice"
        assert config["primary_phone"] == "+15551111111"

    def test_sets_secondary_contact(self, service):
        service.set_escalation_config(
            enabled=True,
            secondary_name="Bob",
            secondary_phone="+15552222222"
        )
        config = service.get_escalation_config()
        assert config["secondary_name"] == "Bob"
        assert config["secondary_phone"] == "+15552222222"

    def test_returns_updated_settings_dict(self, service):
        result = service.set_escalation_config(
            enabled=True,
            primary_name="Alice",
            primary_phone="+15551111111",
            secondary_name="Bob",
            secondary_phone="+15552222222"
        )
        assert "enabled" in result
        assert "primary_name" in result
        assert "primary_phone" in result
        assert "secondary_name" in result
        assert "secondary_phone" in result


class TestEscalationDigestFlags:
    """WOF-10: per-contact weekly-digest opt-in flags on the escalation config.

    Defaults are True so existing escalation contacts keep receiving the
    Monday digest after the migration (AC: preserve current behavior).
    """

    def test_digest_flags_default_true(self, service):
        config = service.get_escalation_config()
        assert config["primary_weekly_digest"] is True
        assert config["secondary_weekly_digest"] is True

    def test_primary_opt_out_round_trips(self, service):
        service.set_escalation_config(enabled=True, primary_weekly_digest=False)
        config = service.get_escalation_config()
        assert config["primary_weekly_digest"] is False
        # Secondary is independent and untouched
        assert config["secondary_weekly_digest"] is True

    def test_flags_are_independent(self, service):
        service.set_escalation_config(
            enabled=True,
            primary_weekly_digest=True,
            secondary_weekly_digest=False
        )
        config = service.get_escalation_config()
        assert config["primary_weekly_digest"] is True
        assert config["secondary_weekly_digest"] is False


class TestSettingsRepr:

    def test_settings_repr(self, service):
        setting = service.set_setting("repr_key", "repr_value")
        result = repr(setting)
        assert "Settings" in result
        assert "repr_key" in result


class TestEscalationWeekly:

    def test_default_is_disabled(self, service):
        assert service.is_escalation_weekly_enabled() is False

    def test_enable_weekly_summary(self, service):
        service.set_escalation_weekly_enabled(True)
        assert service.is_escalation_weekly_enabled() is True

    def test_disable_weekly_summary(self, service):
        service.set_escalation_weekly_enabled(True)
        service.set_escalation_weekly_enabled(False)
        assert service.is_escalation_weekly_enabled() is False


# ===========================================================================
# WHO-43 — Encrypted value_type integration (TDD red phase)
# ===========================================================================
#
# These tests pin the contract for design.md §Component 2:
#   - set_setting(key, value, value_type="encrypted") encrypts before persist
#   - get_setting(key) transparently decrypts encrypted-type rows
#   - Decrypt failures return None (graceful) and log a warning
#
# They will fail until Task 3 wires SecretsService into SettingsService.

class TestEncryptedSettings:
    """Covers REQ-2 AC 1, AC 5; REQ-6 AC 3 (graceful decrypt failure)."""

    def test_set_setting_with_encrypted_type_persists_ciphertext_not_plaintext(
        self, service, monkeypatch
    ):
        """Covers REQ-2 AC 1.

        When value_type='encrypted', the persisted row's `value` column
        MUST hold ciphertext (not plaintext). Round-tripping the ciphertext
        through Fernet must yield back the original plaintext.
        """
        # Use monkeypatch (auto-cleanup) and reset the cached Fernet so this
        # test does not leak state into / inherit state from siblings.
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-settings-encrypt")  # gitleaks:allow (test-only fake key)
        import src.services.secrets_service as _ss
        monkeypatch.setattr(_ss, "_fernet_singleton", None, raising=False)

        plaintext = "AC1234567890abcdef-twilio-token-secret-value"

        service.set_setting(
            "twilio_auth_token",
            plaintext,
            value_type="encrypted",
            description="Twilio Auth Token (encrypted at rest)"
        )

        # Read the row directly via the repository so we bypass any
        # transparent decrypt that get_setting may apply.
        row = service.repository.get_by_key("twilio_auth_token")
        assert row is not None
        assert row.value_type == "encrypted"
        assert row.value != plaintext, (
            "Persisted value must be ciphertext, not plaintext"
        )

        # Ciphertext should round-trip via the SecretsService's Fernet.
        from src.services.secrets_service import SecretsService
        decrypted = SecretsService().decrypt(row.value)
        assert decrypted == plaintext

    def test_get_setting_with_encrypted_type_returns_decrypted_plaintext(
        self, service, monkeypatch
    ):
        """Covers REQ-2 AC 1, AC 3 (round-trip via the service)."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-settings-decrypt")  # gitleaks:allow (test-only fake key)
        import src.services.secrets_service as _ss
        monkeypatch.setattr(_ss, "_fernet_singleton", None, raising=False)

        plaintext = "another-twilio-token-9876543210abcdef"

        # Encrypt directly via SecretsService and persist the ciphertext
        # via the repository, simulating a row that was previously written
        # by the encrypted-aware set_setting path.
        from src.services.secrets_service import SecretsService
        ciphertext = SecretsService().encrypt(plaintext)
        service.repository.set_value(
            "twilio_auth_token",
            ciphertext,
            "encrypted",
            "Twilio token under test",
        )

        result = service.get_setting("twilio_auth_token")
        assert result is not None
        assert result.value == plaintext, (
            "get_setting should transparently decrypt encrypted rows"
        )

    def test_get_setting_with_encrypted_type_returns_none_when_decryption_fails(
        self, service, caplog, monkeypatch
    ):
        """Covers REQ-2 AC 5, REQ-6 AC 3 (graceful decrypt failure).

        When the stored ciphertext cannot be decrypted (corruption, key
        rotation, etc.), get_setting MUST return None and log a warning,
        NOT propagate the exception.
        """
        import logging
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-bad-ciphertext")  # gitleaks:allow (test-only fake key)
        import src.services.secrets_service as _ss
        monkeypatch.setattr(_ss, "_fernet_singleton", None, raising=False)

        # Persist a deliberately invalid ciphertext via the repository.
        service.repository.set_value(
            "twilio_auth_token",
            "this-is-not-a-valid-fernet-token-garbage",
            "encrypted",
            "Corrupt ciphertext under test",
        )

        with caplog.at_level(logging.WARNING):
            result = service.get_setting("twilio_auth_token")

        assert result is None, (
            "get_setting must return None when decryption fails, "
            "not raise — callers fall through to env-var fallback"
        )
        # A warning-level log line should mention the decrypt failure.
        warning_messages = [
            rec.getMessage().lower() for rec in caplog.records
            if rec.levelno >= logging.WARNING
        ]
        assert any(
            "decrypt" in m or "encrypted" in m or "twilio_auth_token" in m
            for m in warning_messages
        ), (
            "Decrypt failure should produce a warning log line. "
            f"Got: {warning_messages}"
        )
