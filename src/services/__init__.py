"""
Service layer for WhoseOnFirst.

This module exports all service classes for business logic operations.
Services implement the Service Layer Pattern to encapsulate business logic
and coordinate between the API layer and repository layer.

Usage:
    from src.services import TeamMemberService, ShiftService
    from src.models import get_db

    db = next(get_db())
    team_service = TeamMemberService(db)
    active_members = team_service.get_active()
"""

from .team_member_service import (
    TeamMemberService,
    TeamMemberServiceError,
    DuplicatePhoneError,
    MemberNotFoundError,
    InvalidPhoneError,
)
from .shift_service import (
    ShiftService,
    ShiftServiceError,
    DuplicateShiftNumberError,
    ShiftNotFoundError,
    InvalidShiftDataError,
)
from .rotation_algorithm import (
    RotationAlgorithmService,
    RotationAlgorithmError,
    InsufficientMembersError,
    NoShiftsConfiguredError,
    InvalidWeekCountError,
)
from .schedule_service import (
    ScheduleService,
    ScheduleServiceError,
    ScheduleAlreadyExistsError,
    InvalidDateRangeError,
)
from .sms_service import (
    SMSService,
    SMSServiceError,
    TwilioConfigurationError,
    SMSDeliveryError,
)
from .settings_service import (
    SettingsService,
)
from .secrets_service import (
    SecretsService,
    SecretsConfigurationError,
)

# Export all services and exceptions
__all__ = [
    # Team Member Service
    "TeamMemberService",
    "TeamMemberServiceError",
    "DuplicatePhoneError",
    "MemberNotFoundError",
    "InvalidPhoneError",
    # Shift Service
    "ShiftService",
    "ShiftServiceError",
    "DuplicateShiftNumberError",
    "ShiftNotFoundError",
    "InvalidShiftDataError",
    # Rotation Algorithm Service
    "RotationAlgorithmService",
    "RotationAlgorithmError",
    "InsufficientMembersError",
    "NoShiftsConfiguredError",
    "InvalidWeekCountError",
    # Schedule Service
    "ScheduleService",
    "ScheduleServiceError",
    "ScheduleAlreadyExistsError",
    "InvalidDateRangeError",
    # SMS Service
    "SMSService",
    "SMSServiceError",
    "TwilioConfigurationError",
    "SMSDeliveryError",
    # Settings Service
    "SettingsService",
    # Secrets Service
    "SecretsService",
    "SecretsConfigurationError",
]
