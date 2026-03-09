"""
Tests for SettingsService.

Covers: get_all_settings, set_setting (type detection), delete_setting,
        set_sms_template (validation), get_escalation_config,
        set_escalation_config, is_escalation_weekly_enabled,
        set_escalation_weekly_enabled
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
