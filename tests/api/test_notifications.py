"""
Tests for notification API endpoints.

Tests cover notification message retrieval, including mock mode behavior.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.models.notification_log import NotificationLog


class TestGetNotificationMessageMockMode:
    """Tests for GET /api/v1/notifications/{id}/message in SMS mock mode."""

    def test_get_message_mock_mode_returns_mock_data(
        self, client: TestClient, db_session, monkeypatch
    ):
        """Test that mock mode returns synthetic message data instead of calling Twilio.

        When SMS_MOCK_MODE=true, SMSService sets twilio_client=None.
        The /message endpoint should detect mock mode and return mock data
        rather than crashing with AttributeError on NoneType.

        Before the fix, the code at notifications.py:270 called
        sms_service.twilio_client.messages(...).fetch() unconditionally,
        which raised AttributeError when twilio_client was None.
        """
        # Create a notification log entry with a fake Twilio SID
        log = NotificationLog(
            schedule_id=None,
            sent_at=datetime.now(timezone.utc),
            status="sent",
            twilio_sid="SM1234567890abcdef1234567890abcdef",
            recipient_name="Test User",
            recipient_phone="+15551234567",
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        # Enable mock mode so SMSService.twilio_client will be None
        monkeypatch.setenv("SMS_MOCK_MODE", "true")

        # Call the endpoint — current code will crash here with:
        # AttributeError: 'NoneType' object has no attribute 'messages'
        response = client.get(f"/api/v1/notifications/{log.id}/message")

        # Expected behavior after fix: 200 with all mock message fields
        assert response.status_code == 200
        data = response.json()
        expected_keys = {
            "body", "status", "direction", "from", "to",
            "date_sent", "date_updated", "sid", "num_segments",
            "price", "price_unit", "error_code", "error_message",
        }
        assert set(data.keys()) == expected_keys
        assert data["sid"] == "SM1234567890abcdef1234567890abcdef"
        assert data["status"] == "delivered"
