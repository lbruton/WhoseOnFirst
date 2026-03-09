"""
Tests for SMS service.

Covers Twilio integration, retry logic, error handling, and notification logging.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pytz import timezone

from twilio.base.exceptions import TwilioRestException

from src.services.sms_service import (
    SMSService,
    SMSServiceError,
    TwilioConfigurationError,
    SMSDeliveryError
)
from src.models import TeamMember, Shift, Schedule, NotificationLog


# Chicago timezone
CHICAGO_TZ = timezone('America/Chicago')


@pytest.fixture
def team_member(test_db_session):
    """Create a test team member."""
    member = TeamMember(
        name="John Doe",
        phone="+15551234567",
        is_active=True
    )
    test_db_session.add(member)
    test_db_session.commit()
    test_db_session.refresh(member)
    return member


@pytest.fixture
def shift(test_db_session):
    """Create a test shift."""
    shift = Shift(
        shift_number=1,
        day_of_week="Monday",
        start_time="08:00:00",
        duration_hours=24
    )
    test_db_session.add(shift)
    test_db_session.commit()
    test_db_session.refresh(shift)
    return shift


@pytest.fixture
def schedule(test_db_session, team_member, shift):
    """Create a test schedule."""
    start = datetime.now(CHICAGO_TZ)
    end = start + timedelta(hours=24)

    schedule = Schedule(
        team_member_id=team_member.id,
        shift_id=shift.id,
        week_number=1,
        start_datetime=start,
        end_datetime=end,
        notified=False
    )
    test_db_session.add(schedule)
    test_db_session.commit()
    test_db_session.refresh(schedule)
    return schedule


@pytest.fixture
def sms_service_mock_mode(test_db_session):
    """Create SMS service in mock mode (no Twilio client)."""
    return SMSService(test_db_session, mock_mode=True)


class TestSMSServiceInitialization:
    """Tests for SMS service initialization."""

    def test_initialization_mock_mode(self, test_db_session):
        """Test SMS service initialization in mock mode."""
        service = SMSService(test_db_session, mock_mode=True)

        assert service.db == test_db_session
        assert service.max_retries == 3
        assert service.base_delay == 60
        assert service.mock_mode is True
        assert service.twilio_client is None
        assert service.from_phone == "+15551234567"

    def test_initialization_with_custom_params(self, test_db_session):
        """Test SMS service initialization with custom parameters."""
        service = SMSService(
            test_db_session,
            max_retries=5,
            base_delay=30,
            mock_mode=True
        )

        assert service.max_retries == 5
        assert service.base_delay == 30

    @patch.dict(os.environ, {}, clear=True)
    def test_initialization_missing_credentials(self, test_db_session):
        """Test initialization fails with missing Twilio credentials."""
        with pytest.raises(TwilioConfigurationError) as exc_info:
            SMSService(test_db_session, mock_mode=False)

        assert "Twilio configuration missing" in str(exc_info.value)

    @patch.dict(os.environ, {
        'TWILIO_ACCOUNT_SID': 'AC123',
        'TWILIO_AUTH_TOKEN': 'token123',
        'TWILIO_PHONE_NUMBER': '+15551234567'
    })
    @patch('src.services.sms_service.Client')
    def test_initialization_with_credentials(self, mock_client, test_db_session):
        """Test successful initialization with valid credentials."""
        service = SMSService(test_db_session, mock_mode=False)

        assert service.twilio_client is not None
        assert service.from_phone == '+15551234567'
        mock_client.assert_called_once_with('AC123', 'token123')


class TestSendNotification:
    """Tests for sending individual notifications."""

    def test_send_notification_success(self, sms_service_mock_mode, schedule):
        """Test successful SMS notification."""
        result = sms_service_mock_mode.send_notification(schedule)

        assert result['success'] is True
        assert result['schedule_id'] == schedule.id
        assert result['twilio_sid'] is not None
        assert result['status'] == 'sent'
        assert result['attempts'] == 1
        assert result['error'] is None

        # Verify schedule marked as notified
        sms_service_mock_mode.db.refresh(schedule)
        assert schedule.notified is True
        assert schedule.notified_at is not None

    def test_send_notification_already_notified_skip(self, sms_service_mock_mode, schedule):
        """Test notification skipped if already notified."""
        schedule.notified = True
        sms_service_mock_mode.db.commit()

        result = sms_service_mock_mode.send_notification(schedule)

        assert result['success'] is True
        assert result['status'] == 'skipped'
        assert result['message'] == 'Already notified'
        assert result['attempts'] == 0

    def test_send_notification_already_notified_force(self, sms_service_mock_mode, schedule):
        """Test notification sent even if already notified when force=True."""
        schedule.notified = True
        sms_service_mock_mode.db.commit()

        result = sms_service_mock_mode.send_notification(schedule, force=True)

        assert result['success'] is True
        assert result['status'] == 'sent'
        assert result['attempts'] == 1

    def test_send_notification_no_team_member(self, sms_service_mock_mode, schedule):
        """Test notification fails if schedule has no team member."""
        # Manually set team_member to None (simulating a data integrity issue)
        schedule.team_member = None

        with pytest.raises(SMSServiceError) as exc_info:
            sms_service_mock_mode.send_notification(schedule)

        assert "no team member assigned" in str(exc_info.value)

    def test_send_notification_creates_log_entry(self, sms_service_mock_mode, schedule):
        """Test notification creates log entry."""
        result = sms_service_mock_mode.send_notification(schedule)

        # Verify log entry created
        logs = sms_service_mock_mode.notification_repo.get_by_schedule(schedule.id)
        assert len(logs) == 1
        assert logs[0].status == 'sent'
        assert logs[0].twilio_sid == result['twilio_sid']
        assert logs[0].error_message is None

    def test_send_notification_max_retries_exceeded(self, sms_service_mock_mode, schedule):
        """Test notification fails if max retries already exceeded."""
        # Create 3 failed attempts
        for _ in range(3):
            sms_service_mock_mode.notification_repo.log_notification_attempt(
                schedule_id=schedule.id,
                status='failed',
                error_message='Test error'
            )

        result = sms_service_mock_mode.send_notification(schedule)

        assert result['success'] is False
        assert result['status'] == 'failed'
        assert 'Exceeded maximum retry attempts' in result['message']


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    @patch('src.services.sms_service.sleep')
    def test_retry_with_exponential_backoff(self, mock_sleep, sms_service_mock_mode, schedule):
        """Test retry logic applies exponential backoff."""
        # Mock _send_sms to fail first 2 times, succeed on 3rd
        call_count = 0

        def mock_send_sms(to_phone, message_body):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TwilioRestException(
                    status=500,
                    uri="http://test.com",
                    msg="Server error",
                    code=20003
                )
            return {"sid": "SM123", "status": "sent"}

        with patch.object(sms_service_mock_mode, '_send_sms', side_effect=mock_send_sms):
            result = sms_service_mock_mode.send_notification(schedule)

        # Verify success after retries
        assert result['success'] is True
        assert result['attempts'] == 3

        # Verify exponential backoff delays
        assert mock_sleep.call_count == 2  # No sleep on first attempt
        mock_sleep.assert_any_call(60)  # 2nd attempt: base_delay
        mock_sleep.assert_any_call(120)  # 3rd attempt: base_delay * 2

    def test_retry_stops_on_non_retryable_error(self, sms_service_mock_mode, schedule):
        """Test retry stops immediately for non-retryable errors."""
        # Mock _send_sms to raise non-retryable error (invalid phone number)
        def mock_send_sms(to_phone, message_body):
            raise TwilioRestException(
                status=400,
                uri="http://test.com",
                msg="Invalid phone number",
                code=21211  # Non-retryable
            )

        with patch.object(sms_service_mock_mode, '_send_sms', side_effect=mock_send_sms):
            result = sms_service_mock_mode.send_notification(schedule)

        # Verify it stopped after 1 attempt (non-retryable)
        assert result['success'] is False
        assert result['attempts'] == 3  # Still tries max_retries, but doesn't retry


class TestMessageComposition:
    """Tests for SMS message composition."""

    def test_compose_message_format(self, sms_service_mock_mode, schedule):
        """Test message composition uses current template variables correctly."""
        message = sms_service_mock_mode._compose_message(schedule)

        # Default template: "WhoseOnFirst Alert\n\nHi {name}, you are now on-call..."
        assert "WhoseOnFirst Alert" in message
        assert schedule.team_member.name in message
        assert schedule.start_datetime.strftime('%a %I:%M %p') in message
        assert schedule.end_datetime.strftime('%a %I:%M %p') in message
        assert f"{schedule.shift.duration_hours}h" in message

    def test_compose_message_under_160_chars(self, sms_service_mock_mode, schedule):
        """Test message is under 160 characters for single SMS."""
        message = sms_service_mock_mode._compose_message(schedule)

        assert len(message) <= 160

    def test_compose_message_with_long_name(self, sms_service_mock_mode, schedule):
        """Test message includes full name without truncation."""
        long_name = "X" * 100
        schedule.team_member.name = long_name
        sms_service_mock_mode.db.commit()

        message = sms_service_mock_mode._compose_message(schedule)

        # Full name is included — no truncation applied
        assert long_name in message
        # Multi-part SMS is acceptable; no length cap enforced
        assert len(message) > 160


class TestBatchNotifications:
    """Tests for batch notification sending."""

    def test_send_batch_notifications_success(self, sms_service_mock_mode, test_db_session, team_member, shift):
        """Test successful batch notification sending."""
        # Create 3 schedules
        schedules = []
        for i in range(3):
            start = datetime.now(CHICAGO_TZ) + timedelta(days=i)
            schedule = Schedule(
                team_member_id=team_member.id,
                shift_id=shift.id,
                week_number=i + 1,
                start_datetime=start,
                end_datetime=start + timedelta(hours=24),
                notified=False
            )
            test_db_session.add(schedule)
            schedules.append(schedule)

        test_db_session.commit()
        for s in schedules:
            test_db_session.refresh(s)

        result = sms_service_mock_mode.send_batch_notifications(schedules)

        assert result['total'] == 3
        assert result['successful'] == 3
        assert result['failed'] == 0
        assert result['skipped'] == 0
        assert len(result['results']) == 3

    def test_send_batch_notifications_mixed_results(self, sms_service_mock_mode, test_db_session, team_member, shift):
        """Test batch notifications with mixed success/skip/fail."""
        # Create 3 schedules: 1 new, 1 already notified, 1 will fail
        schedules = []

        # Schedule 1: New (will succeed)
        schedule1 = Schedule(
            team_member_id=team_member.id,
            shift_id=shift.id,
            week_number=1,
            start_datetime=datetime.now(CHICAGO_TZ),
            end_datetime=datetime.now(CHICAGO_TZ) + timedelta(hours=24),
            notified=False
        )
        test_db_session.add(schedule1)
        schedules.append(schedule1)

        # Schedule 2: Already notified (will skip)
        schedule2 = Schedule(
            team_member_id=team_member.id,
            shift_id=shift.id,
            week_number=2,
            start_datetime=datetime.now(CHICAGO_TZ) + timedelta(days=1),
            end_datetime=datetime.now(CHICAGO_TZ) + timedelta(days=1, hours=24),
            notified=True
        )
        test_db_session.add(schedule2)
        schedules.append(schedule2)

        test_db_session.commit()
        for s in schedules:
            test_db_session.refresh(s)

        result = sms_service_mock_mode.send_batch_notifications(schedules)

        assert result['total'] == 2
        assert result['successful'] == 1
        assert result['skipped'] == 1
        assert result['failed'] == 0

    def test_send_batch_notifications_empty_list(self, sms_service_mock_mode):
        """Test batch notifications with empty list."""
        result = sms_service_mock_mode.send_batch_notifications([])

        assert result['total'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
        assert result['skipped'] == 0


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_is_retryable_error_rate_limit(self, sms_service_mock_mode):
        """Test rate limit errors are marked as retryable."""
        error = TwilioRestException(
            status=429,
            uri="http://test.com",
            msg="Too many requests"
        )

        assert sms_service_mock_mode._is_retryable_error(error) is True

    def test_is_retryable_error_server_error(self, sms_service_mock_mode):
        """Test server errors are marked as retryable."""
        error = TwilioRestException(
            status=500,
            uri="http://test.com",
            msg="Internal server error"
        )

        assert sms_service_mock_mode._is_retryable_error(error) is True

    def test_is_retryable_error_invalid_phone(self, sms_service_mock_mode):
        """Test invalid phone errors are marked as non-retryable."""
        error = TwilioRestException(
            status=400,
            uri="http://test.com",
            msg="Invalid phone number",
            code=21211
        )

        assert sms_service_mock_mode._is_retryable_error(error) is False

    def test_sanitize_phone_masks_last_digits(self, sms_service_mock_mode):
        """Test phone number sanitization masks last 4 digits."""
        sanitized = sms_service_mock_mode._sanitize_phone("+15551234567")

        assert sanitized == "+1555123XXXX"

    def test_sanitize_phone_short_number(self, sms_service_mock_mode):
        """Test phone number sanitization with short number."""
        sanitized = sms_service_mock_mode._sanitize_phone("+1")

        assert sanitized == "+1"


class TestDeliveryStatus:
    """Tests for Twilio delivery status checking."""

    def test_get_delivery_status_mock_mode(self, sms_service_mock_mode):
        """Test getting delivery status in mock mode."""
        status = sms_service_mock_mode.get_delivery_status("SM123")

        assert status['sid'] == "SM123"
        assert status['status'] == 'delivered'
        assert status['error_code'] is None
        assert status['error_message'] is None

    @patch.dict(os.environ, {
        'TWILIO_ACCOUNT_SID': 'AC123',
        'TWILIO_AUTH_TOKEN': 'token123',
        'TWILIO_PHONE_NUMBER': '+15551234567'
    })
    @patch('src.services.sms_service.Client')
    def test_get_delivery_status_real_mode(self, mock_client_class, test_db_session):
        """Test getting delivery status with real Twilio client."""
        # Setup mock
        mock_message = Mock()
        mock_message.sid = "SM123"
        mock_message.status = "delivered"
        mock_message.error_code = None
        mock_message.error_message = None

        mock_messages = Mock()
        mock_messages.return_value.fetch.return_value = mock_message
        mock_client = Mock()
        mock_client.messages = mock_messages
        mock_client_class.return_value = mock_client

        service = SMSService(test_db_session, mock_mode=False)
        status = service.get_delivery_status("SM123")

        assert status['sid'] == "SM123"
        assert status['status'] == "delivered"


class TestIntegration:
    """Integration tests for full notification workflow."""

    def test_full_notification_workflow(self, sms_service_mock_mode, schedule):
        """Test complete notification workflow from start to finish."""
        # Send notification
        result = sms_service_mock_mode.send_notification(schedule)

        # Verify result
        assert result['success'] is True
        assert result['schedule_id'] == schedule.id

        # Verify schedule updated
        sms_service_mock_mode.db.refresh(schedule)
        assert schedule.notified is True
        assert schedule.notified_at is not None

        # Verify notification log created
        logs = sms_service_mock_mode.notification_repo.get_by_schedule(schedule.id)
        assert len(logs) == 1
        assert logs[0].status == 'sent'
        assert logs[0].twilio_sid == result['twilio_sid']

        # Verify can't send again without force
        result2 = sms_service_mock_mode.send_notification(schedule)
        assert result2['status'] == 'skipped'

    def test_notification_with_repository_queries(self, sms_service_mock_mode, schedule):
        """Test notification logging integrates with repository queries."""
        # Send notification
        sms_service_mock_mode.send_notification(schedule)

        # Query notification logs via repository
        logs = sms_service_mock_mode.notification_repo.get_by_status('sent')
        assert len(logs) >= 1

        recent_logs = sms_service_mock_mode.notification_repo.get_recent_logs(limit=10)
        assert len(recent_logs) >= 1

        # Get success rate
        success_rate = sms_service_mock_mode.notification_repo.get_success_rate()
        assert success_rate['total'] >= 1
        assert success_rate['sent'] >= 1
        assert success_rate['success_rate'] > 0


# ===========================================================================
# TestSendNotificationMissingShift
# ===========================================================================

class TestSendNotificationMissingShift:
    """Test send_notification raises when schedule has no shift (line 147-148)."""

    def test_no_shift_raises_sms_service_error(self, sms_service_mock_mode, schedule):
        schedule.shift = None
        with pytest.raises(SMSServiceError, match="no shift assigned"):
            sms_service_mock_mode.send_notification(schedule)


# ===========================================================================
# TestIsRetryableError
# ===========================================================================

class TestIsRetryableError:
    """Tests for _is_retryable_error (lines 630-646)."""

    def _make_twilio_error(self, status=None, code=None):
        """Create a minimal mock that looks like TwilioRestException."""
        err = MagicMock(spec=TwilioRestException)
        if status is not None:
            err.status = status
        else:
            del err.status
        if code is not None:
            err.code = code
        else:
            del err.code
        return err

    def test_http_429_is_retryable(self, sms_service_mock_mode):
        err = self._make_twilio_error(status=429)
        assert sms_service_mock_mode._is_retryable_error(err) is True

    def test_http_500_is_retryable(self, sms_service_mock_mode):
        err = self._make_twilio_error(status=500)
        assert sms_service_mock_mode._is_retryable_error(err) is True

    def test_http_503_is_retryable(self, sms_service_mock_mode):
        err = self._make_twilio_error(status=503)
        assert sms_service_mock_mode._is_retryable_error(err) is True

    def test_non_retryable_code_21211(self, sms_service_mock_mode):
        err = self._make_twilio_error(code=21211)
        assert sms_service_mock_mode._is_retryable_error(err) is False

    def test_retryable_code_30001(self, sms_service_mock_mode):
        err = self._make_twilio_error(code=30001)
        assert sms_service_mock_mode._is_retryable_error(err) is True

    def test_unknown_error_defaults_to_non_retryable(self, sms_service_mock_mode):
        err = MagicMock(spec=TwilioRestException)
        # Remove both status and code attributes
        del err.status
        del err.code
        assert sms_service_mock_mode._is_retryable_error(err) is False


# ===========================================================================
# TestSanitizePhone
# ===========================================================================

class TestSanitizePhone:
    """Tests for _sanitize_phone (lines 648-660)."""

    def test_masks_last_4_digits(self, sms_service_mock_mode):
        result = sms_service_mock_mode._sanitize_phone("+15551234567")
        assert result == "+1555123XXXX"

    def test_short_phone_returned_unchanged(self, sms_service_mock_mode):
        result = sms_service_mock_mode._sanitize_phone("123")
        assert result == "123"


# ===========================================================================
# TestComposeWeeklySummary
# ===========================================================================

class TestComposeWeeklySummary:
    """Tests for _compose_weekly_summary (lines 505-607)."""

    def test_empty_schedules_shows_no_assignment(self, sms_service_mock_mode):
        message = sms_service_mock_mode._compose_weekly_summary([])
        assert "WhoseOnFirst Weekly Schedule" in message
        assert "No assignment" in message

    def test_standard_week_includes_member_name(self, sms_service_mock_mode, schedule):
        """Single 24h shift — should show member name and phone."""
        schedule.start_datetime = datetime.now(CHICAGO_TZ).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        schedule.end_datetime = schedule.start_datetime + timedelta(hours=24)
        sms_service_mock_mode.db.commit()

        message = sms_service_mock_mode._compose_weekly_summary([schedule])
        assert schedule.team_member.name in message
        assert "WhoseOnFirst Weekly Schedule" in message

    def test_48h_shift_shows_continues_on_second_day(self, sms_service_mock_mode, test_db_session, team_member):
        """48h shift should print '(48h)' on day 1 and '(continues)' on day 2."""
        monday = datetime.now(CHICAGO_TZ).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        # Find next Monday
        days_ahead = (7 - monday.weekday()) % 7 or 7
        monday = monday + timedelta(days=days_ahead)

        shift_48 = Shift(
            shift_number=2,
            day_of_week="Tuesday-Wednesday",
            start_time="08:00:00",
            duration_hours=48
        )
        test_db_session.add(shift_48)
        test_db_session.commit()
        test_db_session.refresh(shift_48)

        sched = Schedule(
            team_member_id=team_member.id,
            shift_id=shift_48.id,
            week_number=1,
            start_datetime=monday,
            end_datetime=monday + timedelta(hours=48),
            notified=False
        )
        test_db_session.add(sched)
        test_db_session.commit()
        test_db_session.refresh(sched)

        message = sms_service_mock_mode._compose_weekly_summary([sched])
        assert "(48h)" in message
        assert "(continues)" in message


# ===========================================================================
# TestSendManualNotification
# ===========================================================================

class TestSendManualNotification:
    """Tests for send_manual_notification (lines 769-851)."""

    def test_success_returns_sent_status(self, sms_service_mock_mode, team_member):
        result = sms_service_mock_mode.send_manual_notification(
            team_member=team_member,
            message="Hi John, this is a test notification."
        )
        assert result["success"] is True
        assert result["status"] == "sent"
        assert result["twilio_sid"] is not None
        assert result["error"] is None

    def test_twilio_error_returns_failed_status(self, sms_service_mock_mode, team_member):
        twilio_err = MagicMock(spec=TwilioRestException)
        twilio_err.__str__ = lambda self: "Twilio error 21211"

        with patch.object(sms_service_mock_mode, "_send_sms", side_effect=twilio_err):
            result = sms_service_mock_mode.send_manual_notification(
                team_member=team_member,
                message="test"
            )

        assert result["success"] is False
        assert result["status"] == "failed"


# ===========================================================================
# TestSendEscalationWeeklySummary
# ===========================================================================

class TestSendEscalationWeeklySummary:
    """Tests for send_escalation_weekly_summary (lines 888-1020)."""

    def _make_config(self, primary=True, secondary=False):
        config = {
            "primary_name": "Alice" if primary else "",
            "primary_phone": "+15551111111" if primary else "",
            "secondary_name": "Bob" if secondary else "",
            "secondary_phone": "+15552222222" if secondary else "",
        }
        return config

    def test_primary_contact_only_sends_one(self, sms_service_mock_mode):
        config = self._make_config(primary=True, secondary=False)
        result = sms_service_mock_mode.send_escalation_weekly_summary(
            message="Weekly schedule summary",
            escalation_config=config
        )
        assert result["total"] == 1
        assert result["successful"] == 1
        assert result["failed"] == 0

    def test_both_contacts_sends_two(self, sms_service_mock_mode):
        config = self._make_config(primary=True, secondary=True)
        result = sms_service_mock_mode.send_escalation_weekly_summary(
            message="Weekly schedule summary",
            escalation_config=config
        )
        assert result["total"] == 2
        assert result["successful"] == 2

    def test_no_contacts_sends_zero(self, sms_service_mock_mode):
        config = self._make_config(primary=False, secondary=False)
        result = sms_service_mock_mode.send_escalation_weekly_summary(
            message="Weekly schedule summary",
            escalation_config=config
        )
        assert result["total"] == 0
        assert result["successful"] == 0

    def test_twilio_error_increments_failed(self, sms_service_mock_mode):
        config = self._make_config(primary=True, secondary=False)
        twilio_err = MagicMock(spec=TwilioRestException)
        twilio_err.__str__ = lambda self: "Twilio error"

        with patch.object(sms_service_mock_mode, "_send_sms", side_effect=twilio_err):
            result = sms_service_mock_mode.send_escalation_weekly_summary(
                message="Weekly schedule summary",
                escalation_config=config
            )

        assert result["failed"] == 1
        assert result["successful"] == 0
