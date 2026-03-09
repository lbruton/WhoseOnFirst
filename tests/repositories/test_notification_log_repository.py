"""
Tests for NotificationLogRepository.

Tests SMS notification logging and tracking functionality.
"""

import pytest
from datetime import datetime, timedelta
from src.repositories import NotificationLogRepository


class TestNotificationLogRepositoryCRUD:
    """Tests for basic CRUD operations on notification logs."""

    def test_create_notification_log(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test creating a notification log."""
        data = sample_notification_log_data(populated_schedules[0].id, status="sent")
        log = notification_log_repo.create(data)

        assert log.id is not None
        assert log.schedule_id == populated_schedules[0].id
        assert log.status == "sent"

    def test_log_notification_attempt(self, notification_log_repo, populated_schedules):
        """Test convenience method for logging attempts."""
        log = notification_log_repo.log_notification_attempt(
            schedule_id=populated_schedules[0].id,
            status="sent",
            twilio_sid="SM123456",
            error_message=None
        )

        assert log.id is not None
        assert log.status == "sent"
        assert log.twilio_sid == "SM123456"


class TestNotificationLogRepositoryQueries:
    """Tests for notification log queries."""

    def test_get_by_schedule(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test retrieving logs for specific schedule."""
        schedule = populated_schedules[0]

        # Create multiple logs for same schedule
        for status in ["sent", "failed", "delivered"]:
            data = sample_notification_log_data(schedule.id, status=status)
            notification_log_repo.create(data)

        logs = notification_log_repo.get_by_schedule(schedule.id)

        assert len(logs) == 3
        assert all(log.schedule_id == schedule.id for log in logs)

    def test_get_by_status(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test retrieving logs by status."""
        # Create logs with different statuses
        for i, status in enumerate(["sent", "failed", "sent"]):
            data = sample_notification_log_data(populated_schedules[i].id, status=status)
            notification_log_repo.create(data)

        sent_logs = notification_log_repo.get_by_status("sent")
        failed_logs = notification_log_repo.get_by_status("failed")

        assert len(sent_logs) == 2
        assert len(failed_logs) == 1

    def test_get_failed_notifications(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test retrieving failed notifications."""
        # Create failed log
        data = sample_notification_log_data(populated_schedules[0].id, status="failed")
        notification_log_repo.create(data)

        failed = notification_log_repo.get_failed_notifications(hours_ago=24)

        assert len(failed) >= 1
        assert all(log.status in ["failed", "undelivered"] for log in failed)

    def test_get_by_twilio_sid(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test retrieving log by Twilio SID."""
        sid = "SM_unique_test_sid"
        data = sample_notification_log_data(populated_schedules[0].id)
        data["twilio_sid"] = sid
        created = notification_log_repo.create(data)

        retrieved = notification_log_repo.get_by_twilio_sid(sid)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_recent_logs(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test retrieving recent logs."""
        # Create multiple logs
        for schedule in populated_schedules[:3]:
            data = sample_notification_log_data(schedule.id)
            notification_log_repo.create(data)

        recent = notification_log_repo.get_recent_logs(limit=5)

        assert len(recent) <= 5


class TestNotificationLogRepositoryUpdates:
    """Tests for updating notification logs."""

    def test_update_status(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test updating notification status."""
        data = sample_notification_log_data(populated_schedules[0].id, status="sent")
        log = notification_log_repo.create(data)

        updated = notification_log_repo.update_status(
            log.id,
            status="delivered",
            error_message=None
        )

        assert updated.status == "delivered"

    def test_update_status_with_error(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test updating status with error message."""
        data = sample_notification_log_data(populated_schedules[0].id, status="pending")
        log = notification_log_repo.create(data)

        updated = notification_log_repo.update_status(
            log.id,
            status="failed",
            error_message="Twilio API error"
        )

        assert updated.status == "failed"
        assert updated.error_message == "Twilio API error"


class TestNotificationLogRepositoryMetrics:
    """Tests for notification metrics and analytics."""

    def test_get_retry_count_for_schedule(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test counting retry attempts for a schedule."""
        schedule = populated_schedules[0]

        # Create multiple attempts
        for _ in range(3):
            data = sample_notification_log_data(schedule.id)
            notification_log_repo.create(data)

        count = notification_log_repo.get_retry_count_for_schedule(schedule.id)

        assert count == 3

    def test_get_success_rate(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        """Test calculating notification success rate."""
        # Create mix of successful and failed
        statuses = ["sent", "sent", "sent", "failed", "delivered"]
        for i, status in enumerate(statuses):
            data = sample_notification_log_data(populated_schedules[i].id, status=status)
            notification_log_repo.create(data)

        metrics = notification_log_repo.get_success_rate()

        assert metrics["total"] == 5
        assert metrics["sent"] == 3
        assert metrics["delivered"] == 1
        assert metrics["failed"] == 1
        assert metrics["success_rate"] == 80.0  # 4 out of 5

    def test_get_success_rate_empty(self, notification_log_repo):
        """Test success rate calculation with no logs."""
        metrics = notification_log_repo.get_success_rate()

        assert metrics["total"] == 0
        assert metrics["success_rate"] == 0.0


class TestNotificationLogRepositoryExtra:

    def test_count_all_empty(self, notification_log_repo):
        assert notification_log_repo.count_all() == 0

    def test_count_all_with_logs(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        data = sample_notification_log_data(schedule_id=populated_schedules[0].id)
        notification_log_repo.create(data)
        assert notification_log_repo.count_all() == 1

    def test_get_by_date_range(self, notification_log_repo, sample_notification_log_data, populated_schedules):
        data = sample_notification_log_data(schedule_id=populated_schedules[0].id)
        notification_log_repo.create(data)
        now = datetime.now()
        results = notification_log_repo.get_by_date_range(
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1)
        )
        assert len(results) == 1

    def test_get_by_date_range_empty(self, notification_log_repo):
        now = datetime.now()
        results = notification_log_repo.get_by_date_range(
            start_date=now - timedelta(days=2),
            end_date=now - timedelta(days=1)
        )
        assert results == []
