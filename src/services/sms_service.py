"""
SMS service for sending notifications via Twilio.

Handles SMS delivery with retry logic, error handling, and notification logging.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from time import sleep

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from sqlalchemy.orm import Session

from ..repositories import NotificationLogRepository, ScheduleRepository, ScheduleOverrideRepository
from ..models import Schedule
from .settings_service import SettingsService


logger = logging.getLogger(__name__)


class SMSServiceError(Exception):
    """Base exception for SMS service errors."""


class TwilioConfigurationError(SMSServiceError):
    """Raised when Twilio configuration is invalid or missing."""


class SMSDeliveryError(SMSServiceError):
    """Raised when SMS delivery fails after all retry attempts."""


class SMSService:
    """
    Service for sending SMS notifications via Twilio.

    Implements:
    - SMS message composition and delivery
    - Exponential backoff retry logic
    - Notification logging for audit trail
    - Error handling and recovery
    - Phone number formatting and validation

    Attributes:
        db: Database session
        twilio_client: Twilio REST client
        from_phone: Twilio phone number for sending messages
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        notification_repo: Repository for logging notifications
        schedule_repo: Repository for schedule operations
        settings_service: Service for accessing application settings
    """

    def __init__(
        self,
        db: Session,
        max_retries: int = 3,
        base_delay: int = 60,
        mock_mode: bool = False
    ):
        """
        Initialize SMS service.

        Resolves Twilio configuration in precedence order:
            1. Database settings (DB) — populated via the admin UI (WHO-43).
            2. Environment variables — preserved for existing deployments.
            3. None — enters the explicit ``unconfigured`` state (mock_mode
               stays False, config_source == "none"). The app boots so an
               admin can land on /admin.html to configure Twilio, but any
               send attempt raises SMSDeliveryError loudly. Mock mode is
               NOT activated; that would silently log fake successful sends.

        ``SMS_MOCK_MODE`` (env var) and ``mock_mode=True`` (constructor arg)
        force mock mode regardless of any other configuration. Mock mode is
        an explicit opt-in only — it is never entered automatically when
        credentials are absent.

        Args:
            db: SQLAlchemy database session
            max_retries: Maximum retry attempts (default: 3)
            base_delay: Base delay in seconds for exponential backoff (default: 60)
            mock_mode: If True, skip Twilio client initialization for testing.
                Can also be enabled at runtime by setting the SMS_MOCK_MODE
                environment variable to "1", "true", or "yes" (case-insensitive).
                The env var is OR'd with this parameter, so either one being
                truthy forces mock mode. This is the supported way to disable
                real SMS in dev containers — see `.env.dev.example`.

        Raises:
            Nothing on init. Missing credentials → unconfigured state
            (config_source == "none", mock_mode stays False, sends raise
            SMSDeliveryError). Present-but-rejected credentials (Twilio SDK
            init failure) → also enter unconfigured state with a WARNING log
            rather than raising, so the app stays up. TwilioConfigurationError
            is no longer raised from __init__.
        """
        self.db = db
        self.max_retries = max_retries
        self.base_delay = base_delay
        # SMS_MOCK_MODE env var provides runtime override for dev containers.
        # OR'd with the constructor arg so tests passing mock_mode=True still work.
        self.mock_mode = mock_mode or os.getenv('SMS_MOCK_MODE', '').lower() in ('1', 'true', 'yes')
        # When True, SMS service has no usable credentials AND no intentional
        # mock-mode opt-in — sends MUST fail rather than silently log
        # successful-delivered. See CodeRabbit C2 / WHO-49 follow-up.
        self.unconfigured = False

        # Initialize repositories and services
        self.notification_repo = NotificationLogRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.settings_service = SettingsService(db)

        # Resolve Twilio config via precedence chain (DB → env → none/mock)
        sid, token, phone, source = self._load_twilio_config()
        self.config_source = source

        if source in ("db", "env"):
            try:
                self.twilio_client = Client(
                    sid, token,
                    http_client=TwilioHttpClient(timeout=5.0),
                )
                self.from_phone = phone
                logger.info(
                    f"SMS service: Twilio config loaded (source={source})"
                )
            except Exception as exc:
                # Credentials were present but the Twilio SDK rejected them
                # (expired/rotated/malformed token). Enter unconfigured state
                # rather than crashing — the app stays up so an admin can
                # correct the credentials via /admin.html. Subsequent sends
                # fail loudly via SMSDeliveryError (T9).
                logger.warning(
                    f"SMS service: Twilio SDK rejected credentials from "
                    f"{source} ({exc}) — entering unconfigured state"
                )
                self.unconfigured = True
                self.twilio_client = None
                self.from_phone = "+15551234567"  # Placeholder; never used.
                self.config_source = "none"
        elif source == "none":
            # No DB config and no env config — DO NOT enter mock mode (which
            # would silently log fake successful sends). Mark service as
            # unconfigured so any send attempt raises SMSDeliveryError.
            # The app still boots so an admin can land on /admin.html and
            # configure Twilio via the new UI.
            self.unconfigured = True
            self.twilio_client = None
            self.from_phone = "+15551234567"  # Placeholder; never used.
            logger.warning(
                "SMS service: no credentials configured — running in "
                "unconfigured mode, sends will fail (source=none)"
            )
        else:
            # source == "mock" — intentional dev fake, mock_mode already True.
            self.twilio_client = None
            self.from_phone = "+15551234567"  # Mock phone number
            logger.info(
                "SMS service: mock mode forced via SMS_MOCK_MODE env var "
                "(source=mock)"
            )

    def _load_twilio_config(
        self,
    ) -> tuple[Optional[str], Optional[str], Optional[str], str]:
        """Resolve Twilio config in precedence order: DB → env → none/mock.

        Returns:
            Tuple of ``(sid, token, phone, source)`` where ``source`` is one
            of ``"db"``, ``"env"``, ``"none"``, or ``"mock"``. The credential
            slots are ``None`` when ``source`` is ``"none"`` or ``"mock"``.

        Notes:
            - DB lookup uses ``SettingsService.get_setting`` which returns
              ``None`` both when the row is missing AND when decryption of an
              encrypted value fails (e.g. SECRET_KEY rotation). Both cases
              fall through to env, then to ``"none"``.
            - Mock mode short-circuits the chain — when ``self.mock_mode`` is
              already truthy from the env var or constructor arg, no DB or
              env reads happen.
        """
        if self.mock_mode:
            return (None, None, None, "mock")

        # Try DB first
        sid_setting = self.settings_service.get_setting("twilio_account_sid")
        token_setting = self.settings_service.get_setting("twilio_auth_token")
        phone_setting = self.settings_service.get_setting("twilio_phone_number")
        if (
            sid_setting and sid_setting.value
            and token_setting and token_setting.value
            and phone_setting and phone_setting.value
        ):
            return (
                sid_setting.value,
                token_setting.value,
                phone_setting.value,
                "db",
            )

        # Try env vars
        env_sid = os.getenv("TWILIO_ACCOUNT_SID")
        env_token = os.getenv("TWILIO_AUTH_TOKEN")
        env_phone = os.getenv("TWILIO_PHONE_NUMBER")
        if env_sid and env_token and env_phone:
            return (env_sid, env_token, env_phone, "env")

        # Nothing configured
        return (None, None, None, "none")

    def send_notification(
        self,
        schedule: Schedule,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Send SMS notification for a schedule assignment.

        Implements retry logic with exponential backoff:
        - Attempt 1: Immediate
        - Attempt 2: After 60 seconds (base_delay)
        - Attempt 3: After 120 seconds (base_delay * 2)
        - etc.

        Args:
            schedule: Schedule instance to send notification for
            force: If True, send even if already notified (default: False)

        Returns:
            Dictionary with result information:
            {
                "success": bool,
                "schedule_id": int,
                "twilio_sid": str or None,
                "status": str,
                "message": str,
                "attempts": int,
                "error": str or None
            }

        Raises:
            SMSServiceError: If schedule data is invalid
        """
        # Validate schedule
        if not schedule.team_member:
            raise SMSServiceError(f"Schedule {schedule.id} has no team member assigned")

        if not schedule.shift:
            raise SMSServiceError(f"Schedule {schedule.id} has no shift assigned")

        # Check for active override
        override_repo = ScheduleOverrideRepository(self.db)
        override = override_repo.get_override_for_schedule(schedule.id)

        # Determine recipient (override member or original member)
        if override and override.is_active:
            recipient_member = override.override_member
            recipient_name = override.override_member_name
            logger.info(f"Override active for schedule {schedule.id}: sending to {recipient_name}")
        else:
            recipient_member = schedule.team_member
            recipient_name = schedule.team_member.name

        # Check if already notified
        if schedule.notified and not force:
            logger.info(f"Schedule {schedule.id} already notified, skipping")
            return {
                "success": True,
                "schedule_id": schedule.id,
                "twilio_sid": None,
                "status": "skipped",
                "message": "Already notified",
                "attempts": 0,
                "error": None
            }

        # Check retry count
        retry_count = self.notification_repo.get_retry_count_for_schedule(schedule.id)
        if retry_count >= self.max_retries:
            logger.warning(
                f"Schedule {schedule.id} exceeded max retries ({self.max_retries}), "
                "marking as failed"
            )
            self.notification_repo.log_notification_attempt(
                schedule_id=schedule.id,
                status='failed',
                error_message=f"Exceeded maximum retry attempts ({self.max_retries})",
                recipient_name=recipient_name,
                recipient_phone=recipient_member.phone
            )
            return {
                "success": False,
                "schedule_id": schedule.id,
                "twilio_sid": None,
                "status": "failed",
                "message": "Exceeded maximum retry attempts",
                "attempts": retry_count,
                "error": "Max retries exceeded"
            }

        # Compose message
        message_body = self._compose_message(schedule)

        # Send to primary phone (override member or original member)
        primary_result = self._send_to_single_phone(
            phone=recipient_member.phone,
            message_body=message_body,
            schedule=schedule,
            phone_type="primary",
            recipient_name=recipient_name
        )

        # Send to secondary phone if configured
        secondary_result = None
        if recipient_member.secondary_phone:
            secondary_result = self._send_to_single_phone(
                phone=recipient_member.secondary_phone,
                message_body=message_body,
                schedule=schedule,
                phone_type="secondary",
                recipient_name=recipient_name
            )

        # Mark as notified if EITHER phone succeeded (redundancy pattern)
        if primary_result['success'] or (secondary_result and secondary_result['success']):
            schedule.notified = True
            schedule.notified_at = datetime.now()
            self.db.commit()

            # Determine which phone(s) succeeded
            if primary_result['success'] and secondary_result and secondary_result['success']:
                message = "SMS sent successfully to both phones"
            elif primary_result['success']:
                message = "SMS sent successfully to primary phone"
            else:
                message = "SMS sent successfully to secondary phone"

            return {
                "success": True,
                "schedule_id": schedule.id,
                "twilio_sid": primary_result.get('twilio_sid') or (secondary_result.get('twilio_sid') if secondary_result else None),
                "status": "sent",
                "message": message,
                "attempts": primary_result.get('attempts', 0),
                "error": None,
                "primary": primary_result,
                "secondary": secondary_result
            }

        # Both phones failed
        return {
            "success": False,
            "schedule_id": schedule.id,
            "twilio_sid": None,
            "status": "failed",
            "message": "Failed to send SMS to any phone",
            "attempts": primary_result.get('attempts', 0),
            "error": primary_result.get('error'),
            "primary": primary_result,
            "secondary": secondary_result
        }

    def _send_to_single_phone(
        self,
        phone: str,
        message_body: str,
        schedule: Schedule,
        phone_type: str,
        recipient_name: str
    ) -> Dict[str, Any]:
        """
        Send SMS to a single phone number with retry logic.

        Args:
            phone: Recipient phone number (E.164 format)
            message_body: SMS message text
            schedule: Schedule instance for logging
            phone_type: "primary" or "secondary" for logging purposes
            recipient_name: Name of actual recipient (override member or scheduled member)

        Returns:
            Dictionary with result information for this phone
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Apply exponential backoff (except first attempt)
                if attempt > 0:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    logger.info(
                        f"Retry attempt {attempt + 1}/{self.max_retries} "
                        f"for {phone_type} phone of schedule {schedule.id} after {delay}s delay"
                    )
                    sleep(delay)

                # Send SMS
                result = self._send_sms(phone, message_body)

                # Log successful send with recipient snapshot
                _ = self.notification_repo.log_notification_attempt(
                    schedule_id=schedule.id,
                    status='sent',
                    twilio_sid=result['sid'],
                    error_message=None,
                    recipient_name=recipient_name,
                    recipient_phone=phone
                )

                logger.info(
                    f"SMS sent successfully to {phone_type} phone {self._sanitize_phone(phone)} "
                    f"for schedule {schedule.id} (SID: {result['sid']})"
                )

                return {
                    "success": True,
                    "twilio_sid": result['sid'],
                    "status": "sent",
                    "phone_type": phone_type,
                    "attempts": attempt + 1,
                    "error": None
                }

            except SMSDeliveryError as e:
                # Permanent failure — service is unconfigured. Do not retry;
                # log exactly one failure row and exit the loop immediately.
                last_error = str(e)
                error_msg = f"SMS unconfigured on {phone_type} phone for schedule {schedule.id}: {str(e)}"
                logger.error(error_msg)

                self.notification_repo.log_notification_attempt(
                    schedule_id=schedule.id,
                    status='failed',
                    twilio_sid=None,
                    error_message=error_msg,
                    recipient_name=recipient_name,
                    recipient_phone=phone
                )
                break

            except TwilioRestException as e:
                last_error = str(e)
                error_msg = f"Twilio error on {phone_type} phone (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                logger.error(error_msg)

                # Log failed attempt
                self.notification_repo.log_notification_attempt(
                    schedule_id=schedule.id,
                    status='failed',
                    twilio_sid=None,
                    error_message=error_msg,
                    recipient_name=recipient_name,
                    recipient_phone=phone
                )

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(
                        f"Non-retryable Twilio error for {phone_type} phone of schedule {schedule.id}: {str(e)}"
                    )
                    break

            except Exception as e:
                last_error = str(e)
                error_msg = f"Unexpected error on {phone_type} phone (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                logger.error(error_msg)

                # Log failed attempt
                self.notification_repo.log_notification_attempt(
                    schedule_id=schedule.id,
                    status='failed',
                    twilio_sid=None,
                    error_message=error_msg,
                    recipient_name=recipient_name,
                    recipient_phone=phone
                )

        # All attempts failed for this phone
        logger.error(
            f"Failed to send SMS to {phone_type} phone for schedule {schedule.id} after "
            f"{self.max_retries} attempts. Last error: {last_error}"
        )

        return {
            "success": False,
            "twilio_sid": None,
            "status": "failed",
            "phone_type": phone_type,
            "attempts": self.max_retries,
            "error": last_error
        }

    def _send_sms(self, to_phone: str, message_body: str) -> Dict[str, str]:
        """
        Send SMS via Twilio.

        Args:
            to_phone: Recipient phone number (E.164 format)
            message_body: SMS message text

        Returns:
            Dictionary with Twilio response data (sid, status)

        Raises:
            SMSDeliveryError: Always raised when the service is in unconfigured
                state (no Twilio credentials) — before any Twilio API call is
                attempted. This is a permanent failure; callers must not retry.
            TwilioRestException: If the Twilio API call fails. Only raised when
                the service is fully configured (config_source in ("db", "env")).
        """
        if self.unconfigured:
            # Refuse to fake-deliver when no Twilio creds are configured.
            # Without this, an unconfigured deploy would log every send as
            # successful while transmitting nothing (CodeRabbit C2).
            raise SMSDeliveryError(
                "SMS not configured — no Twilio credentials available "
                "(configure via /admin.html or set TWILIO_* env vars)"
            )

        if self.mock_mode:
            # Mock mode for testing
            logger.info(f"[MOCK] Sending SMS to {to_phone}: {message_body}")
            return {
                "sid": f"SM{os.urandom(16).hex()}",
                "status": "sent"
            }

        message = self.twilio_client.messages.create(
            body=message_body,
            from_=self.from_phone,
            to=to_phone
        )

        return {
            "sid": message.sid,
            "status": message.status
        }

    def _compose_message(self, schedule: Schedule) -> str:
        """
        Compose SMS message for a schedule assignment using template from database.

        Loads the SMS template from settings and replaces variables:
        - {name}: Team member name (or override member if override is active)
        - {start_time}: Shift start time (e.g., "Mon 08:00 AM")
        - {end_time}: Shift end time (e.g., "Tue 08:00 AM")
        - {duration}: Shift duration (e.g., "24h")

        Args:
            schedule: Schedule instance

        Returns:
            Formatted SMS message text from template

        Raises:
            Exception: If template loading or formatting fails
        """
        try:
            # Load template from database
            template = self.settings_service.get_sms_template()

            # Check for active override
            override_repo = ScheduleOverrideRepository(self.db)
            override = override_repo.get_override_for_schedule(schedule.id)

            # Use override member if override exists and is active
            if override and override.is_active:
                member_name = override.override_member_name
                logger.info(f"Using override member '{member_name}' for schedule {schedule.id}")
            else:
                member_name = schedule.team_member.name

            # Prepare template variables
            duration_hours = schedule.shift.duration_hours
            start_time = schedule.start_datetime.strftime('%a %I:%M %p')
            end_time = schedule.end_datetime.strftime('%a %I:%M %p')

            # Format template with variables
            message = template.format(
                name=member_name,
                start_time=start_time,
                end_time=end_time,
                duration=f"{duration_hours}h"
            )

            logger.info(f"Composed message for schedule {schedule.id}: {len(message)} characters")
            return message

        except KeyError as e:
            # Missing template variable
            logger.error(f"Template formatting error: missing variable {e}")
            raise Exception(f"SMS template missing required variable: {e}")

        except Exception as e:
            # Fallback to basic message if template loading fails
            logger.error(f"Error loading SMS template: {str(e)}, using fallback")

            # Check for active override (even in fallback)
            override_repo = ScheduleOverrideRepository(self.db)
            override = override_repo.get_override_for_schedule(schedule.id)

            if override and override.is_active:
                member_name = override.override_member_name
            else:
                member_name = schedule.team_member.name

            end_time = schedule.end_datetime.strftime('%a %I:%M %p')
            return f"WhoseOnFirst: {member_name}, your on-call shift has started (until {end_time})"

    def _compose_weekly_summary(self, schedules: list) -> str:
        """
        Compose weekly schedule summary message for escalation contacts.

        Formats a 7-day schedule (Mon-Sun) with special handling for 48-hour shifts.
        - Single-day shifts: "Mon 11/25: Name +1234567890"
        - 48h shift first day: "Tue 11/26: Name +1234567890 (48h)"
        - 48h shift second day: "Wed 11/27: Name (continues)"
        - Missing assignments: "Thu 11/28: No assignment"

        Args:
            schedules: List of Schedule instances sorted by start_datetime

        Returns:
            Formatted weekly summary message (~320 chars)

        Example:
            WhoseOnFirst Weekly Schedule (Nov 25 - Dec 1)

            Mon 11/25: Lance B +19187019714
            Tue 11/26: Gary K +19187019714 (48h)
            Wed 11/27: Gary K (continues)
            Thu 11/28: Troy M +19187019714
            ...

            Questions? Reply to this message.
        """
        from datetime import datetime, timedelta
        from pytz import timezone

        # Get America/Chicago timezone
        chicago_tz = timezone('America/Chicago')

        # Determine date range from schedules
        if not schedules:
            now = datetime.now(chicago_tz)
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = schedules[0].start_datetime
            if start_date.tzinfo is None:
                start_date = chicago_tz.localize(start_date)
            else:
                start_date = start_date.astimezone(chicago_tz)

        end_date = start_date + timedelta(days=6)

        # Format header with date range
        header = f"WhoseOnFirst Weekly Schedule ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"

        # Build schedule lines
        lines = []

        # Create a map of date -> schedule for easy lookup
        schedule_map = {}
        for schedule in schedules:
            sched_date = schedule.start_datetime
            if sched_date.tzinfo is None:
                sched_date = chicago_tz.localize(sched_date)
            else:
                sched_date = sched_date.astimezone(chicago_tz)
            date_key = sched_date.date()
            schedule_map[date_key] = schedule

        # Track 48h shifts to handle "continues" on second day
        previous_schedule = None
        previous_member_name = None  # Track actual displayed member (with overrides)
        is_continuation = False

        # Iterate through 7 days
        for day_offset in range(7):
            current_date = (start_date + timedelta(days=day_offset)).date()
            day_name = (start_date + timedelta(days=day_offset)).strftime('%a %m/%d')

            if current_date in schedule_map:
                schedule = schedule_map[current_date]

                # Check for active override for this schedule
                override_repo = ScheduleOverrideRepository(self.db)
                override = override_repo.get_override_for_schedule(schedule.id)

                # Use override member if override exists and is active
                if override and override.is_active:
                    member_name = override.override_member_name
                    member_phone = override.override_member.phone
                else:
                    member_name = schedule.team_member.name
                    member_phone = schedule.team_member.phone

                duration = schedule.shift.duration_hours

                # Check if this is a continuation of previous 48h shift
                # Compare actual displayed names (accounting for overrides)
                if (previous_schedule and
                    previous_member_name == member_name and
                    is_continuation):
                    # Second day of 48h shift - just show name + "(continues)"
                    lines.append(f"{day_name}: {member_name} (continues)")
                    is_continuation = False  # Reset for next potential 48h shift
                else:
                    # Check if this is the START of a 48h shift
                    if duration == 48:
                        lines.append(f"{day_name}: {member_name} {member_phone} (48h)")
                        is_continuation = True  # Next day will be continuation
                    else:
                        lines.append(f"{day_name}: {member_name} {member_phone}")
                        is_continuation = False

                previous_schedule = schedule
                previous_member_name = member_name  # Track displayed member for continuation logic
            else:
                # No schedule entry for this day
                # Check if we're in the middle of a 48h shift continuation
                if is_continuation and previous_member_name:
                    # This is the second day of a 48h shift
                    # Use the previously displayed member name (accounting for overrides)
                    lines.append(f"{day_name}: {previous_member_name} (continues)")
                    is_continuation = False  # Reset after showing continuation
                else:
                    # Truly no assignment for this day
                    lines.append(f"{day_name}: No assignment")
                    is_continuation = False
                    previous_schedule = None
                    previous_member_name = None

        # Build final message
        message_lines = [header, ""] + lines
        message = "\n".join(message_lines)

        logger.info(f"Composed weekly summary: {len(message)} characters")
        return message

    def _is_retryable_error(self, error: TwilioRestException) -> bool:
        """
        Determine if a Twilio error is retryable.

        Retryable errors (temporary):
        - 429: Too Many Requests (rate limiting)
        - 500-503: Server errors
        - 20003: Authentication issues (temporary)
        - 21610: Message cannot be sent to this phone number (temporary)

        Non-retryable errors (permanent):
        - 21211: Invalid phone number
        - 21408: Permission denied
        - 21614: Invalid number format

        Args:
            error: TwilioRestException instance

        Returns:
            True if error is retryable, False otherwise
        """
        # HTTP status codes
        if hasattr(error, 'status'):
            if error.status in [429, 500, 502, 503]:
                return True

        # Twilio error codes
        if hasattr(error, 'code'):
            retryable_codes = [20003, 21610, 30001, 30002, 30003, 30004, 30005, 30006]
            non_retryable_codes = [21211, 21408, 21614, 21217, 21601]

            if error.code in non_retryable_codes:
                return False
            if error.code in retryable_codes:
                return True

        # Default to non-retryable for unknown errors
        return False

    def _sanitize_phone(self, phone: str) -> str:
        """
        Sanitize phone number for logging (mask last 4 digits).

        Args:
            phone: Phone number in E.164 format

        Returns:
            Sanitized phone number (e.g., +1555123XXXX)
        """
        if len(phone) >= 4:
            return phone[:-4] + 'XXXX'
        return phone

    def send_batch_notifications(
        self,
        schedules: list[Schedule],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Send notifications for multiple schedules.

        Args:
            schedules: List of Schedule instances
            force: If True, send even if already notified

        Returns:
            Dictionary with batch result summary:
            {
                "total": int,
                "successful": int,
                "failed": int,
                "skipped": int,
                "results": list of individual results
            }
        """
        results = []
        successful = 0
        failed = 0
        skipped = 0

        logger.info(f"Starting batch notification for {len(schedules)} schedules")

        for schedule in schedules:
            try:
                result = self.send_notification(schedule, force=force)
                results.append(result)

                if result['success']:
                    if result['status'] == 'skipped':
                        skipped += 1
                    else:
                        successful += 1
                else:
                    failed += 1

            except Exception as e:
                error_msg = f"Error sending notification for schedule {schedule.id}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "success": False,
                    "schedule_id": schedule.id,
                    "twilio_sid": None,
                    "status": "error",
                    "message": error_msg,
                    "attempts": 0,
                    "error": str(e)
                })
                failed += 1

        summary = {
            "total": len(schedules),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results
        }

        logger.info(
            f"Batch notification complete: {successful} successful, "
            f"{failed} failed, {skipped} skipped out of {len(schedules)} total"
        )

        return summary

    def send_manual_notification(
        self,
        team_member,
        message: str
    ) -> Dict[str, Any]:
        """
        Send a manual SMS notification to a team member.

        This method bypasses the schedule system entirely and sends
        a custom message directly to a team member. Logs the notification
        with schedule_id=NULL to indicate a manual send.

        Args:
            team_member: TeamMember instance to send notification to
            message: Custom SMS message text

        Returns:
            Dictionary with send result:
            {
                "success": bool,
                "notification_id": int or None,
                "twilio_sid": str or None,
                "status": str (sent, failed),
                "message": str,
                "error": str or None
            }

        Example:
            >>> service = SMSService(db)
            >>> result = service.send_manual_notification(
            ...     team_member=member,
            ...     message="Hi {name}, this is a test."
            ... )
            >>> result['success']
            True
        """
        logger.info(
            f"Sending manual notification to {self._sanitize_phone(team_member.phone)} "
            f"({team_member.name})"
        )

        try:
            # Send SMS via Twilio
            twilio_result = self._send_sms(team_member.phone, message)

            # Log manual notification (schedule_id=NULL)
            log_entry = self.notification_repo.log_notification_attempt(
                schedule_id=None,  # NULL for manual notifications
                status='sent',
                twilio_sid=twilio_result['sid'],
                error_message=None,
                recipient_name=team_member.name,
                recipient_phone=team_member.phone
            )

            logger.info(
                f"Manual SMS sent successfully to {self._sanitize_phone(team_member.phone)} "
                f"({team_member.name}, SID: {twilio_result['sid']})"
            )

            return {
                "success": True,
                "notification_id": log_entry.id,
                "twilio_sid": twilio_result['sid'],
                "status": "sent",
                "message": f"SMS sent successfully to {team_member.name}",
                "error": None
            }

        except TwilioRestException as e:
            error_msg = f"Twilio error sending manual notification: {str(e)}"
            logger.error(error_msg)

            # Log failed manual notification
            log_entry = self.notification_repo.log_notification_attempt(
                schedule_id=None,  # NULL for manual notifications
                status='failed',
                twilio_sid=None,
                error_message=error_msg,
                recipient_name=team_member.name,
                recipient_phone=team_member.phone
            )

            return {
                "success": False,
                "notification_id": log_entry.id,
                "twilio_sid": None,
                "status": "failed",
                "message": f"Failed to send SMS to {team_member.name}",
                "error": str(e)
            }

        except Exception as e:
            error_msg = f"Unexpected error sending manual notification: {str(e)}"
            logger.error(error_msg)

            # Log failed manual notification
            try:
                log_entry = self.notification_repo.log_notification_attempt(
                    schedule_id=None,
                    status='failed',
                    twilio_sid=None,
                    error_message=error_msg,
                    recipient_name=team_member.name,
                    recipient_phone=team_member.phone
                )
                notification_id = log_entry.id
            except Exception as log_error:
                logger.error(f"Failed to log manual notification attempt: {str(log_error)}")
                notification_id = None

            return {
                "success": False,
                "notification_id": notification_id,
                "twilio_sid": None,
                "status": "failed",
                "message": f"Failed to send SMS to {team_member.name}",
                "error": str(e)
            }

    def send_escalation_weekly_summary(
        self,
        message: str,
        escalation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send the weekly schedule summary SMS to opted-in escalation contacts.

        Thin wrapper over :meth:`send_weekly_digest` that builds the
        recipient list from the escalation config. Each contact's
        ``*_weekly_digest`` flag is honored individually (WOF-10); a missing
        flag (config predating WOF-10) counts as opted in.

        Args:
            message: The weekly summary message text
            escalation_config: Escalation config dict with keys:
                - primary_name: Primary contact name
                - primary_phone: Primary contact phone
                - secondary_name: Secondary contact name
                - secondary_phone: Secondary contact phone
                - primary_weekly_digest: Primary digest opt-in (default True)
                - secondary_weekly_digest: Secondary digest opt-in (default True)

        Returns:
            Dictionary with send results (see send_weekly_digest)

        Example:
            >>> config = settings_service.get_escalation_config()
            >>> message = sms_service._compose_weekly_summary(schedules)
            >>> result = sms_service.send_escalation_weekly_summary(message, config)
            >>> print(f"Sent to {result['successful']}/{result['total']} contacts")
        """
        contacts = []

        # Primary escalation contact (individually opted in)
        if (escalation_config.get('primary_name')
                and escalation_config.get('primary_phone')
                and escalation_config.get('primary_weekly_digest', True)):
            contacts.append({
                "name": escalation_config['primary_name'],
                "phone": escalation_config['primary_phone'],
                "label": "Primary Escalation Contact"
            })

        # Secondary escalation contact (individually opted in)
        if (escalation_config.get('secondary_name')
                and escalation_config.get('secondary_phone')
                and escalation_config.get('secondary_weekly_digest', True)):
            contacts.append({
                "name": escalation_config['secondary_name'],
                "phone": escalation_config['secondary_phone'],
                "label": "Secondary Escalation Contact"
            })

        return self.send_weekly_digest(message, contacts)

    def send_weekly_digest(
        self,
        message: str,
        recipients: list
    ) -> Dict[str, Any]:
        """
        Send the weekly schedule digest SMS to a list of recipients (WOF-10).

        Sends the provided message to every recipient. Each send is logged
        individually with schedule_id=NULL to indicate a weekly digest
        notification. Recipients may be escalation contacts or opted-in team
        members — the caller decides (see
        scheduler.schedule_manager.collect_weekly_digest_recipients).

        Args:
            message: The weekly digest message text
            recipients: List of dicts with keys:
                - name: Recipient display name
                - phone: Recipient phone (E.164)
                - label: Recipient role label for logs/details

        Returns:
            Dictionary with send results:
            {
                "successful": int (count of successful sends),
                "failed": int (count of failed sends),
                "total": int (total attempted sends),
                "details": list of individual send results
            }
        """
        logger.info("Sending weekly digest to %d recipients", len(recipients))

        results = {
            "successful": 0,
            "failed": 0,
            "total": 0,
            "details": []
        }

        contacts = recipients

        # Send to each contact
        for contact in contacts:
            results["total"] += 1
            contact_name = contact["name"]
            contact_phone = contact["phone"]
            contact_label = contact["label"]

            try:
                logger.info(
                    f"Sending weekly summary to {self._sanitize_phone(contact_phone)} "
                    f"({contact_name} - {contact_label})"
                )

                # Send SMS via Twilio
                twilio_result = self._send_sms(contact_phone, message)

                # Log successful send (schedule_id=NULL for weekly summary)
                log_entry = self.notification_repo.log_notification_attempt(
                    schedule_id=None,  # NULL for weekly summaries
                    status='sent',
                    twilio_sid=twilio_result['sid'],
                    error_message=None,
                    recipient_name=contact_name,
                    recipient_phone=contact_phone
                )

                results["successful"] += 1
                results["details"].append({
                    "contact": contact_label,
                    "name": contact_name,
                    "phone": self._sanitize_phone(contact_phone),
                    "status": "sent",
                    "twilio_sid": twilio_result['sid'],
                    "notification_id": log_entry.id
                })

                logger.info(
                    f"Weekly summary sent successfully to {self._sanitize_phone(contact_phone)} "
                    f"(SID: {twilio_result['sid']})"
                )

            except TwilioRestException as e:
                error_msg = f"Twilio error: {str(e)}"
                logger.error(f"Failed to send weekly summary to {contact_name}: {error_msg}")

                # Log failed send
                try:
                    log_entry = self.notification_repo.log_notification_attempt(
                        schedule_id=None,
                        status='failed',
                        twilio_sid=None,
                        error_message=error_msg,
                        recipient_name=contact_name,
                        recipient_phone=contact_phone
                    )
                    notification_id = log_entry.id
                except Exception as log_error:
                    logger.error(f"Failed to log notification attempt: {str(log_error)}")
                    notification_id = None

                results["failed"] += 1
                results["details"].append({
                    "contact": contact_label,
                    "name": contact_name,
                    "phone": self._sanitize_phone(contact_phone),
                    "status": "failed",
                    "error": str(e),
                    "notification_id": notification_id
                })

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(f"Failed to send weekly summary to {contact_name}: {error_msg}")

                # Log failed send
                try:
                    log_entry = self.notification_repo.log_notification_attempt(
                        schedule_id=None,
                        status='failed',
                        twilio_sid=None,
                        error_message=error_msg,
                        recipient_name=contact_name,
                        recipient_phone=contact_phone
                    )
                    notification_id = log_entry.id
                except Exception as log_error:
                    logger.error(f"Failed to log notification attempt: {str(log_error)}")
                    notification_id = None

                results["failed"] += 1
                results["details"].append({
                    "contact": contact_label,
                    "name": contact_name,
                    "phone": self._sanitize_phone(contact_phone),
                    "status": "failed",
                    "error": str(e),
                    "notification_id": notification_id
                })

        logger.info(
            f"Weekly escalation summary complete: {results['successful']} successful, "
            f"{results['failed']} failed, {results['total']} total"
        )

        return results

    def get_delivery_status(self, twilio_sid: str) -> Optional[Dict[str, Any]]:
        """
        Query Twilio for message delivery status.

        Useful for checking delivery confirmation after sending.

        Args:
            twilio_sid: Twilio message SID

        Returns:
            Dictionary with status information or None if not found

        Raises:
            TwilioRestException: If Twilio API call fails
        """
        if self.unconfigured:
            # No client to query — surface "no record" instead of fake delivered.
            logger.warning(
                "get_delivery_status called while SMS unconfigured (sid=%s)",
                twilio_sid,
            )
            return None

        if self.mock_mode:
            return {
                "sid": twilio_sid,
                "status": "delivered",
                "error_code": None,
                "error_message": None
            }

        try:
            message = self.twilio_client.messages(twilio_sid).fetch()
            return {
                "sid": message.sid,
                "status": message.status,
                "error_code": message.error_code,
                "error_message": message.error_message
            }
        except TwilioRestException as e:
            logger.error(f"Failed to fetch message status for SID {twilio_sid}: {str(e)}")
            return None
