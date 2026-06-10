"""
Tests for scheduler/schedule_manager.py

Covers: send_daily_notifications, trigger_notifications_manually,
        check_auto_renewal, send_weekly_escalation_summary,
        trigger_weekly_summary_manually, complete_past_overrides,
        trigger_override_completion_manually, ScheduleManager class lifecycle
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, PropertyMock
from contextlib import contextmanager

from src.scheduler.schedule_manager import (
    send_daily_notifications,
    trigger_notifications_manually,
    check_auto_renewal,
    send_weekly_escalation_summary,
    trigger_weekly_summary_manually,
    complete_past_overrides,
    trigger_override_completion_manually,
    collect_weekly_digest_recipients,
    ScheduleManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_db_session_patch(mock_db):
    """Return a context manager factory that yields mock_db."""
    @contextmanager
    def _ctx():
        yield mock_db
    return _ctx


# ---------------------------------------------------------------------------
# send_daily_notifications
# ---------------------------------------------------------------------------

class TestSendDailyNotifications:

    def test_no_pending_schedules_returns_zeros(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockService:
            MockService.return_value.get_pending_notifications.return_value = []

            result = send_daily_notifications()

        assert result == {"successful": 0, "failed": 0, "skipped": 0, "total": 0}

    def test_with_pending_schedules_calls_batch(self):
        mock_db = MagicMock()
        mock_schedules = [MagicMock(), MagicMock()]
        batch_result = {"successful": 2, "failed": 0, "skipped": 0, "total": 2}

        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockSchedule, \
             patch("src.scheduler.schedule_manager.SMSService") as MockSMS:
            MockSchedule.return_value.get_pending_notifications.return_value = mock_schedules
            MockSMS.return_value.send_batch_notifications.return_value = batch_result

            result = send_daily_notifications()

        assert result["successful"] == 2
        assert result["total"] == 2

    def test_exception_propagates(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockService:
            MockService.return_value.get_pending_notifications.side_effect = RuntimeError("DB error")

            with pytest.raises(RuntimeError, match="DB error"):
                send_daily_notifications()


# ---------------------------------------------------------------------------
# trigger_notifications_manually
# ---------------------------------------------------------------------------

class TestTriggerNotificationsManually:

    def test_success_wraps_result_with_status(self):
        with patch("src.scheduler.schedule_manager.send_daily_notifications") as mock_send:
            mock_send.return_value = {"successful": 1, "failed": 0, "skipped": 0, "total": 1}
            result = trigger_notifications_manually()

        assert result["status"] == "success"
        assert result["successful"] == 1
        assert result["total"] == 1
        assert "timestamp" in result

    def test_exception_returns_error_dict(self):
        with patch("src.scheduler.schedule_manager.send_daily_notifications") as mock_send:
            mock_send.side_effect = Exception("Twilio down")
            result = trigger_notifications_manually()

        assert result["status"] == "error"
        assert result["message"] == "Daily notification job failed - see server logs"
        assert "Twilio down" not in result["message"]
        assert result["successful"] == 0


# ---------------------------------------------------------------------------
# check_auto_renewal
# ---------------------------------------------------------------------------

class TestCheckAutoRenewal:

    def test_disabled_returns_early(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings:
            MockSettings.return_value.is_auto_renew_enabled.return_value = False
            # Should return None without calling schedule service
            check_auto_renewal()

            MockSettings.return_value.is_auto_renew_enabled.assert_called_once()

    def test_no_schedules_returns_early(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockSchedule:
            MockSettings.return_value.is_auto_renew_enabled.return_value = True
            MockSettings.return_value.get_auto_renew_threshold_weeks.return_value = 4
            MockSettings.return_value.get_auto_renew_weeks.return_value = 8
            MockSchedule.return_value.schedule_repo.get_all.return_value = []

            check_auto_renewal()

            MockSchedule.return_value.generate_schedule.assert_not_called()

    def test_above_threshold_skips_renewal(self):
        mock_db = MagicMock()
        far_future = datetime(2030, 1, 1)
        mock_schedule = MagicMock()
        mock_schedule.end_datetime = far_future

        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockSchedule:
            MockSettings.return_value.is_auto_renew_enabled.return_value = True
            MockSettings.return_value.get_auto_renew_threshold_weeks.return_value = 4
            MockSettings.return_value.get_auto_renew_weeks.return_value = 8
            MockSchedule.return_value.schedule_repo.get_all.return_value = [mock_schedule]

            check_auto_renewal()

            MockSchedule.return_value.generate_schedule.assert_not_called()

    def test_below_threshold_triggers_generation(self):
        mock_db = MagicMock()
        # Slightly in the future — within threshold
        near_future = datetime(2026, 3, 11)  # 2 days away from test date
        mock_schedule = MagicMock()
        mock_schedule.end_datetime = near_future

        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockSchedule:
            MockSettings.return_value.is_auto_renew_enabled.return_value = True
            MockSettings.return_value.get_auto_renew_threshold_weeks.return_value = 4
            MockSettings.return_value.get_auto_renew_weeks.return_value = 8
            MockSchedule.return_value.schedule_repo.get_all.return_value = [mock_schedule]
            MockSchedule.return_value.generate_schedule.return_value = [MagicMock()] * 10

            check_auto_renewal()

            MockSchedule.return_value.generate_schedule.assert_called_once()


# ---------------------------------------------------------------------------
# send_weekly_escalation_summary
# ---------------------------------------------------------------------------

class TestSendWeeklyEscalationSummary:

    def test_disabled_returns_early(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings:
            MockSettings.return_value.is_escalation_weekly_enabled.return_value = False

            result = send_weekly_escalation_summary()

        assert result["total"] == 0
        assert result["message"] == "Feature disabled"

    def test_no_recipients_returns_early(self):
        """WOF-10: escalation disabled + no opted-in members = nothing to send."""
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.TeamMemberRepository") as MockMembers:
            MockSettings.return_value.is_escalation_weekly_enabled.return_value = True
            MockSettings.return_value.get_escalation_config.return_value = {"enabled": False}
            MockMembers.return_value.get_digest_recipients.return_value = []

            result = send_weekly_escalation_summary()

        assert result["total"] == 0
        assert result["message"] == "No digest recipients"

    def test_empty_contacts_and_no_members_returns_early(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.TeamMemberRepository") as MockMembers:
            MockSettings.return_value.is_escalation_weekly_enabled.return_value = True
            MockSettings.return_value.get_escalation_config.return_value = {
                "enabled": True,
                "primary_name": "",
                "primary_phone": "",
                "secondary_name": "",
                "secondary_phone": "",
            }
            MockMembers.return_value.get_digest_recipients.return_value = []

            result = send_weekly_escalation_summary()

        assert result["total"] == 0
        assert result["message"] == "No digest recipients"

    def test_success_sends_to_contacts(self):
        mock_db = MagicMock()
        escalation_config = {
            "enabled": True,
            "primary_name": "Alice",
            "primary_phone": "+15551111111",
            "secondary_name": "",
            "secondary_phone": "",
        }
        sms_result = {"successful": 1, "failed": 0, "total": 1}

        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockSchedule, \
             patch("src.scheduler.schedule_manager.TeamMemberRepository") as MockMembers, \
             patch("src.scheduler.schedule_manager.SMSService") as MockSMS:
            MockSettings.return_value.is_escalation_weekly_enabled.return_value = True
            MockSettings.return_value.get_escalation_config.return_value = escalation_config
            MockSchedule.return_value.schedule_repo.get_by_date_range.return_value = []
            MockMembers.return_value.get_digest_recipients.return_value = []
            MockSMS.return_value._compose_weekly_summary.return_value = "Weekly summary"
            MockSMS.return_value.send_weekly_digest.return_value = sms_result

            result = send_weekly_escalation_summary()

        assert result["successful"] == 1
        assert "timestamp" in result

    def test_member_only_digest_sends_without_escalation(self):
        """WOF-10: the supervisor case — opted-in member, escalation disabled."""
        mock_db = MagicMock()
        supervisor = MagicMock()
        supervisor.name = "Super Visor"
        supervisor.phone = "+15554440001"
        sms_result = {"successful": 1, "failed": 0, "total": 1}

        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.SettingsService") as MockSettings, \
             patch("src.scheduler.schedule_manager.ScheduleService") as MockSchedule, \
             patch("src.scheduler.schedule_manager.TeamMemberRepository") as MockMembers, \
             patch("src.scheduler.schedule_manager.SMSService") as MockSMS:
            MockSettings.return_value.is_escalation_weekly_enabled.return_value = True
            MockSettings.return_value.get_escalation_config.return_value = {"enabled": False}
            MockSchedule.return_value.schedule_repo.get_by_date_range.return_value = []
            MockMembers.return_value.get_digest_recipients.return_value = [supervisor]
            MockSMS.return_value._compose_weekly_summary.return_value = "Weekly summary"
            MockSMS.return_value.send_weekly_digest.return_value = sms_result

            result = send_weekly_escalation_summary()

        assert result["successful"] == 1
        # The member reached the send call as a recipient
        sent_recipients = MockSMS.return_value.send_weekly_digest.call_args.kwargs.get(
            "recipients"
        ) or MockSMS.return_value.send_weekly_digest.call_args.args[1]
        assert any(r["phone"] == "+15554440001" for r in sent_recipients)


# ---------------------------------------------------------------------------
# collect_weekly_digest_recipients (WOF-10) — real services, real DB
# ---------------------------------------------------------------------------

class TestCollectWeeklyDigestRecipients:
    """Recipient selection across member opt-in × escalation flag combinations."""

    def _add_member(self, db_session, name, phone, optin, active=True):
        from src.repositories.team_member_repository import TeamMemberRepository
        return TeamMemberRepository(db_session).create({
            "name": name,
            "phone": phone,
            "is_active": active,
            "weekly_digest_optin": optin,
        })

    def _set_escalation(self, db_session, **kwargs):
        from src.services.settings_service import SettingsService
        SettingsService(db_session).set_escalation_config(**kwargs)

    def test_opted_in_member_included_without_escalation(self, db_session):
        self._add_member(db_session, "Super Visor", "+15554440001", optin=True)
        self._add_member(db_session, "Quiet Quinn", "+15554440002", optin=False)

        recipients = collect_weekly_digest_recipients(db_session)

        phones = [r["phone"] for r in recipients]
        assert phones == ["+15554440001"]
        assert recipients[0]["label"] == "Team Member Digest"

    def test_inactive_opted_in_member_excluded(self, db_session):
        self._add_member(db_session, "Gone Gary", "+15554440003", optin=True, active=False)

        recipients = collect_weekly_digest_recipients(db_session)

        assert recipients == []

    def test_escalation_contact_respects_individual_flag(self, db_session):
        self._set_escalation(
            db_session,
            enabled=True,
            primary_name="New Engineer",
            primary_phone="+15554440004",
            secondary_name="Old Hand",
            secondary_phone="+15554440005",
            primary_weekly_digest=False,
            secondary_weekly_digest=True,
        )

        recipients = collect_weekly_digest_recipients(db_session)

        phones = [r["phone"] for r in recipients]
        assert phones == ["+15554440005"]
        assert recipients[0]["label"] == "Secondary Escalation Contact"

    def test_escalation_disabled_excludes_contacts_but_not_members(self, db_session):
        self._set_escalation(
            db_session,
            enabled=False,
            primary_name="New Engineer",
            primary_phone="+15554440004",
        )
        self._add_member(db_session, "Super Visor", "+15554440001", optin=True)

        recipients = collect_weekly_digest_recipients(db_session)

        phones = [r["phone"] for r in recipients]
        assert phones == ["+15554440001"]

    def test_dedupes_member_who_is_also_escalation_contact(self, db_session):
        self._set_escalation(
            db_session,
            enabled=True,
            primary_name="Super Visor",
            primary_phone="+15554440001",
        )
        self._add_member(db_session, "Super Visor", "+15554440001", optin=True)

        recipients = collect_weekly_digest_recipients(db_session)

        assert len(recipients) == 1
        # Escalation listing wins the label (collected first)
        assert recipients[0]["label"] == "Primary Escalation Contact"


# ---------------------------------------------------------------------------
# trigger_weekly_summary_manually
# ---------------------------------------------------------------------------

class TestTriggerWeeklySummaryManually:

    def test_success_wraps_result(self):
        with patch("src.scheduler.schedule_manager.send_weekly_escalation_summary") as mock_fn:
            mock_fn.return_value = {
                "successful": 1, "failed": 0, "total": 1,
                "timestamp": "2026-03-09T08:00:00"
            }
            result = trigger_weekly_summary_manually()

        assert result["status"] == "success"
        assert result["successful"] == 1

    def test_exception_returns_error_dict(self):
        with patch("src.scheduler.schedule_manager.send_weekly_escalation_summary") as mock_fn:
            mock_fn.side_effect = Exception("connection failed")
            result = trigger_weekly_summary_manually()

        assert result["status"] == "error"
        assert result["message"] == "Weekly summary job failed - see server logs"
        assert "connection failed" not in result["message"]


# ---------------------------------------------------------------------------
# complete_past_overrides
# ---------------------------------------------------------------------------

class TestCompletePastOverrides:

    def test_returns_completed_count(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.ScheduleOverrideService") as MockService:
            MockService.return_value.complete_past_overrides.return_value = 3

            result = complete_past_overrides()

        assert result["completed_count"] == 3
        assert "timestamp" in result

    def test_zero_completed_succeeds(self):
        mock_db = MagicMock()
        with patch("src.scheduler.schedule_manager.get_db_session", make_db_session_patch(mock_db)), \
             patch("src.scheduler.schedule_manager.ScheduleOverrideService") as MockService:
            MockService.return_value.complete_past_overrides.return_value = 0

            result = complete_past_overrides()

        assert result["completed_count"] == 0


# ---------------------------------------------------------------------------
# trigger_override_completion_manually
# ---------------------------------------------------------------------------

class TestTriggerOverrideCompletionManually:

    def test_success_wraps_result(self):
        with patch("src.scheduler.schedule_manager.complete_past_overrides") as mock_fn:
            mock_fn.return_value = {"completed_count": 2, "timestamp": "2026-03-09T08:05:00"}
            result = trigger_override_completion_manually()

        assert result["status"] == "success"
        assert result["completed_count"] == 2

    def test_exception_returns_error_dict(self):
        with patch("src.scheduler.schedule_manager.complete_past_overrides") as mock_fn:
            mock_fn.side_effect = Exception("override error")
            result = trigger_override_completion_manually()

        assert result["status"] == "error"
        assert result["message"] == "Override completion job failed - see server logs"
        assert "override error" not in result["message"]
        assert result["completed_count"] == 0


# ---------------------------------------------------------------------------
# ScheduleManager class
# ---------------------------------------------------------------------------

class TestScheduleManager:

    def test_start_when_already_running_logs_warning(self, caplog):
        manager = ScheduleManager()
        manager.is_running = True

        with patch.object(manager.scheduler, "start") as mock_start:
            manager.start()
            mock_start.assert_not_called()

    def test_stop_when_not_running_logs_warning(self, caplog):
        manager = ScheduleManager()
        manager.is_running = False

        with patch.object(manager.scheduler, "shutdown") as mock_shutdown:
            manager.stop()
            mock_shutdown.assert_not_called()

    def test_trigger_job_now_job_not_found_raises_lookup_error(self):
        manager = ScheduleManager()
        with patch.object(manager.scheduler, "get_job", return_value=None):
            with pytest.raises(LookupError, match="not found"):
                manager.trigger_job_now("nonexistent_job")

    def test_get_job_status_not_found_returns_none(self):
        manager = ScheduleManager()
        with patch.object(manager.scheduler, "get_job", return_value=None):
            result = manager.get_job_status("nonexistent_job")
        assert result is None

    def test_get_job_status_found_returns_dict(self):
        manager = ScheduleManager()
        mock_job = MagicMock()
        mock_job.id = "daily_oncall_notifications"
        mock_job.name = "Daily On-Call SMS Notifications"
        mock_job.next_run_time = datetime(2026, 3, 10, 8, 0, 0)
        mock_job.trigger = "cron[hour=8]"

        with patch.object(manager.scheduler, "get_job", return_value=mock_job):
            result = manager.get_job_status("daily_oncall_notifications")

        assert result["id"] == "daily_oncall_notifications"
        assert result["name"] == "Daily On-Call SMS Notifications"
        assert result["next_run_time"] is not None
