"""
Settings service for business logic.

Manages application settings with type-safe accessors.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from cryptography.fernet import InvalidToken

from ..repositories.settings_repository import SettingsRepository
from ..models.settings import Settings
from .secrets_service import SecretsService, SecretsConfigurationError

logger = logging.getLogger(__name__)


# Setting key constants
AUTO_RENEW_ENABLED = "auto_renew_enabled"
AUTO_RENEW_THRESHOLD_WEEKS = "auto_renew_threshold_weeks"
AUTO_RENEW_WEEKS = "auto_renew_weeks"
SMS_TEMPLATE = "sms_template"
ESCALATION_ENABLED = "escalation_enabled"
ESCALATION_PRIMARY_NAME = "escalation_primary_name"
ESCALATION_PRIMARY_PHONE = "escalation_primary_phone"
ESCALATION_SECONDARY_NAME = "escalation_secondary_name"
ESCALATION_SECONDARY_PHONE = "escalation_secondary_phone"
ESCALATION_WEEKLY_ENABLED = "escalation_weekly_enabled"

# Default SMS template
DEFAULT_SMS_TEMPLATE = """WhoseOnFirst Alert

Hi {name}, you are now on-call starting at {start_time} CST until {end_time} CST.

Your shift lasts {duration}. Thank you for being available!"""


class SettingsService:
    """
    Service for managing application settings.

    Provides business logic for settings management with
    type-safe accessors and defaults.

    Attributes:
        db: Database session
        repository: Settings repository instance
    """

    def __init__(self, db: Session):
        """
        Initialize SettingsService.

        Args:
            db: Database session
        """
        self.db = db
        self.repository = SettingsRepository(db)

    def get_setting(self, key: str) -> Optional[Settings]:
        """
        Get a setting by key.

        For rows with ``value_type == "encrypted"``, the stored ciphertext
        is transparently decrypted in memory before returning. The DB row
        is NOT modified — only the in-memory ``value`` attribute is replaced
        with the plaintext. If decryption fails (``InvalidToken`` or missing
        ``SECRET_KEY``), this returns ``None`` and logs a warning so callers
        can fall through to env-var fallback or mock mode.

        Args:
            key: Setting key

        Returns:
            Settings instance or None
        """
        setting = self.repository.get_by_key(key)
        if setting is None:
            return None
        if setting.value_type == "encrypted":
            try:
                plaintext = SecretsService().decrypt(setting.value)
            except (InvalidToken, SecretsConfigurationError):
                logger.warning(
                    "Failed to decrypt setting key=%s — possibly SECRET_KEY rotation or DB corruption",
                    key,
                )
                return None
            # Detach from session BEFORE mutating .value so SQLAlchemy's
            # dirty-tracking does not flag this row for write-back. If we
            # mutated a session-bound entity, a downstream commit() in this
            # request lifecycle (autoflush, explicit commit, or session
            # teardown) would persist the plaintext over the ciphertext —
            # the exact regression CodeRabbit flagged.
            self.db.expunge(setting)
            setting.value = plaintext
        return setting

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings as a dictionary.

        Returns:
            Dictionary of all settings with typed values
        """
        all_settings = self.repository.get_all()
        return {
            setting.key: setting.get_typed_value()
            for setting in all_settings
        }

    def set_setting(self, key: str, value: Any, value_type: str = None, description: str = None) -> Settings:
        """
        Set a setting value.

        For ``value_type == "encrypted"``, the value is transparently
        encrypted via :class:`SecretsService` before being persisted. The
        ciphertext is stored in the ``value`` column and ``"encrypted"``
        in the ``value_type`` column.

        Args:
            key: Setting key
            value: Setting value (will be converted to string)
            value_type: Optional type override (auto-detected if None)
            description: Optional description

        Returns:
            Settings instance
        """
        # Encrypted secrets bypass type-detection entirely — caller opts in.
        if value_type == "encrypted":
            ciphertext = SecretsService().encrypt(str(value))
            return self.repository.set_value(key, ciphertext, "encrypted", description)

        # Auto-detect type if not provided
        if value_type is None:
            if isinstance(value, bool):
                value_type = "bool"
            elif isinstance(value, int):
                value_type = "int"
            elif isinstance(value, float):
                value_type = "float"
            else:
                value_type = "str"

        # Convert value to string for storage
        str_value = str(value).lower() if isinstance(value, bool) else str(value)

        return self.repository.set_value(key, str_value, value_type, description)

    def delete_setting(self, key: str) -> bool:
        """
        Delete a setting.

        Args:
            key: Setting key

        Returns:
            True if deleted, False if not found
        """
        return self.repository.delete_by_key(key)

    # Auto-renewal specific methods
    def is_auto_renew_enabled(self) -> bool:
        """
        Check if auto-renewal is enabled.

        Returns:
            True if enabled, False otherwise (default: True)
        """
        return self.repository.get_value(AUTO_RENEW_ENABLED, default=True)

    def set_auto_renew_enabled(self, enabled: bool) -> Settings:
        """
        Enable or disable auto-renewal.

        Args:
            enabled: True to enable, False to disable

        Returns:
            Settings instance
        """
        return self.set_setting(
            AUTO_RENEW_ENABLED,
            enabled,
            "bool",
            "Automatically renew schedule when running low"
        )

    def get_auto_renew_threshold_weeks(self) -> int:
        """
        Get the threshold in weeks to trigger auto-renewal.

        Returns:
            Number of weeks (default: 4)
        """
        return self.repository.get_value(AUTO_RENEW_THRESHOLD_WEEKS, default=4)

    def set_auto_renew_threshold_weeks(self, weeks: int) -> Settings:
        """
        Set the auto-renewal threshold.

        Args:
            weeks: Number of weeks

        Returns:
            Settings instance
        """
        return self.set_setting(
            AUTO_RENEW_THRESHOLD_WEEKS,
            weeks,
            "int",
            "Trigger auto-renewal when less than this many weeks remain"
        )

    def get_auto_renew_weeks(self) -> int:
        """
        Get the number of weeks to generate during auto-renewal.

        Returns:
            Number of weeks (default: 52)
        """
        return self.repository.get_value(AUTO_RENEW_WEEKS, default=52)

    def set_auto_renew_weeks(self, weeks: int) -> Settings:
        """
        Set the number of weeks to generate during auto-renewal.

        Args:
            weeks: Number of weeks

        Returns:
            Settings instance
        """
        return self.set_setting(
            AUTO_RENEW_WEEKS,
            weeks,
            "int",
            "Number of weeks to generate during auto-renewal"
        )

    def get_auto_renew_config(self) -> Dict[str, Any]:
        """
        Get all auto-renewal configuration.

        Returns:
            Dictionary with auto-renewal settings
        """
        return {
            "enabled": self.is_auto_renew_enabled(),
            "threshold_weeks": self.get_auto_renew_threshold_weeks(),
            "renew_weeks": self.get_auto_renew_weeks()
        }

    def update_auto_renew_config(self, config: Dict[str, Any]) -> Dict[str, Settings]:
        """
        Update auto-renewal configuration.

        Args:
            config: Dictionary with enabled, threshold_weeks, and/or renew_weeks

        Returns:
            Dictionary of updated Settings instances
        """
        updated = {}

        if "enabled" in config:
            updated["enabled"] = self.set_auto_renew_enabled(config["enabled"])

        if "threshold_weeks" in config:
            updated["threshold_weeks"] = self.set_auto_renew_threshold_weeks(config["threshold_weeks"])

        if "renew_weeks" in config:
            updated["renew_weeks"] = self.set_auto_renew_weeks(config["renew_weeks"])

        return updated

    # SMS template methods
    def get_sms_template(self) -> str:
        """
        Get the SMS notification template.

        Returns template from database, or default if not set.
        Automatically seeds default template on first access.

        Returns:
            SMS template string with variables: {name}, {start_time}, {end_time}, {duration}
        """
        template = self.repository.get_value(SMS_TEMPLATE, default=None)

        # Lazy initialization: seed default template if not exists
        if template is None:
            self.set_sms_template(DEFAULT_SMS_TEMPLATE)
            template = DEFAULT_SMS_TEMPLATE

        return template

    def set_sms_template(self, template: str) -> Settings:
        """
        Set the SMS notification template.

        Args:
            template: SMS template string with variables

        Returns:
            Settings instance

        Raises:
            ValueError: If template is invalid
        """
        # Basic validation (detailed validation in API layer)
        if not template or not template.strip():
            raise ValueError("SMS template cannot be empty")

        return self.set_setting(
            SMS_TEMPLATE,
            template,
            "text",
            "SMS notification template for on-call shift alerts"
        )

    # Escalation contact methods
    def get_escalation_config(self) -> Dict[str, Any]:
        """
        Get the escalation contact configuration.

        Returns dictionary with escalation settings:
        - enabled: bool (default: False)
        - primary_name: str | None
        - primary_phone: str | None
        - secondary_name: str | None
        - secondary_phone: str | None

        Returns:
            Escalation configuration dictionary
        """
        return {
            "enabled": self.repository.get_value(ESCALATION_ENABLED, default=False),
            "primary_name": self.repository.get_value(ESCALATION_PRIMARY_NAME, default=None),
            "primary_phone": self.repository.get_value(ESCALATION_PRIMARY_PHONE, default=None),
            "secondary_name": self.repository.get_value(ESCALATION_SECONDARY_NAME, default=None),
            "secondary_phone": self.repository.get_value(ESCALATION_SECONDARY_PHONE, default=None)
        }

    def set_escalation_config(
        self,
        enabled: bool,
        primary_name: Optional[str] = None,
        primary_phone: Optional[str] = None,
        secondary_name: Optional[str] = None,
        secondary_phone: Optional[str] = None
    ) -> Dict[str, Settings]:
        """
        Set the escalation contact configuration.

        Args:
            enabled: Enable or disable escalation display
            primary_name: Primary escalation contact name
            primary_phone: Primary escalation contact phone (E.164 format)
            secondary_name: Secondary escalation contact name
            secondary_phone: Secondary escalation contact phone (E.164 format)

        Returns:
            Dictionary of updated Settings instances

        Raises:
            ValueError: If validation fails
        """
        updated = {}

        # Set enabled flag
        updated["enabled"] = self.set_setting(
            ESCALATION_ENABLED,
            enabled,
            "bool",
            "Enable escalation contact display on dashboard"
        )

        # Set primary escalation contact
        if primary_name is not None:
            updated["primary_name"] = self.set_setting(
                ESCALATION_PRIMARY_NAME,
                primary_name,
                "text",
                "Primary escalation contact name"
            )

        if primary_phone is not None:
            updated["primary_phone"] = self.set_setting(
                ESCALATION_PRIMARY_PHONE,
                primary_phone,
                "text",
                "Primary escalation contact phone (E.164 format)"
            )

        # Set secondary escalation contact
        if secondary_name is not None:
            updated["secondary_name"] = self.set_setting(
                ESCALATION_SECONDARY_NAME,
                secondary_name,
                "text",
                "Secondary escalation contact name"
            )

        if secondary_phone is not None:
            updated["secondary_phone"] = self.set_setting(
                ESCALATION_SECONDARY_PHONE,
                secondary_phone,
                "text",
                "Secondary escalation contact phone (E.164 format)"
            )

        return updated

    def is_escalation_weekly_enabled(self) -> bool:
        """
        Check if weekly escalation contact schedule summary is enabled.

        Returns:
            True if enabled, False otherwise (default: False)
        """
        return self.repository.get_value(ESCALATION_WEEKLY_ENABLED, default=False)

    def set_escalation_weekly_enabled(self, enabled: bool) -> Settings:
        """
        Enable or disable weekly escalation contact schedule summary.

        Args:
            enabled: True to enable, False to disable

        Returns:
            Settings instance
        """
        return self.set_setting(
            ESCALATION_WEEKLY_ENABLED,
            enabled,
            "bool",
            "Send weekly SMS schedule summary to escalation contacts every Monday 8:00 AM CST"
        )
