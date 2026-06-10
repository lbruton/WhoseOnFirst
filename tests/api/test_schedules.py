"""
Schedules API endpoint tests.
"""

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pytz import timezone

from src.models.team_member import TeamMember
from src.models.shift import Shift
from src.models.schedule import Schedule


# Chicago timezone for testing
CHICAGO_TZ = timezone('America/Chicago')


@pytest.fixture
def setup_team_and_shifts(db_session: Session):
    """
    Fixture to set up team members and shifts for testing.

    Creates 3 active team members and 6 standard shifts.
    """
    # Create team members
    members = [
        TeamMember(name="Alice", phone="+15551111111", is_active=True),
        TeamMember(name="Bob", phone="+15552222222", is_active=True),
        TeamMember(name="Charlie", phone="+15553333333", is_active=True),
    ]
    db_session.add_all(members)

    # Create standard 6-shift weekly rotation
    shifts = [
        Shift(shift_number=1, day_of_week="Monday", duration_hours=24, start_time="08:00"),
        Shift(shift_number=2, day_of_week="Tuesday-Wednesday", duration_hours=48, start_time="08:00"),
        Shift(shift_number=3, day_of_week="Thursday", duration_hours=24, start_time="08:00"),
        Shift(shift_number=4, day_of_week="Friday", duration_hours=24, start_time="08:00"),
        Shift(shift_number=5, day_of_week="Saturday", duration_hours=24, start_time="08:00"),
        Shift(shift_number=6, day_of_week="Sunday", duration_hours=24, start_time="08:00"),
    ]
    db_session.add_all(shifts)
    db_session.commit()

    return {"members": members, "shifts": shifts}


class TestGetCurrentWeekSchedule:
    """Tests for GET /api/v1/schedules/current"""

    def test_get_current_week_empty(self, client: TestClient, setup_team_and_shifts):
        """Test getting current week schedule when no schedules exist."""
        response = client.get("/api/v1/schedules/current")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_current_week_with_schedules(
        self, client: TestClient, db_session: Session, setup_team_and_shifts
    ):
        """Test getting current week schedule with existing schedules."""
        # Generate schedule for current week
        start_date = CHICAGO_TZ.localize(datetime.now().replace(hour=8, minute=0, second=0, microsecond=0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 1,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get current week schedule
        response = client.get("/api/v1/schedules/current")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Verify schedules have required fields
        for schedule in data:
            assert "id" in schedule
            assert "team_member_name" in schedule
            assert "shift_number" in schedule


class TestGetUpcomingSchedules:
    """Tests for GET /api/v1/schedules/upcoming"""

    def test_get_upcoming_default_weeks(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test getting upcoming schedules with default 4 weeks."""
        # Generate schedule for next 4 weeks
        start_date = CHICAGO_TZ.localize(
            (datetime.now() + timedelta(days=7)).replace(hour=8, minute=0, second=0, microsecond=0)
        )
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get upcoming schedules
        response = client.get("/api/v1/schedules/upcoming")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_get_upcoming_custom_weeks(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test getting upcoming schedules with custom week count."""
        # Generate schedule for next 8 weeks
        start_date = CHICAGO_TZ.localize(
            (datetime.now() + timedelta(days=7)).replace(hour=8, minute=0, second=0, microsecond=0)
        )
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 8,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get upcoming schedules for 8 weeks
        response = client.get("/api/v1/schedules/upcoming?weeks=8")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


class TestGetSchedulesByDateRange:
    """Tests for GET /api/v1/schedules/"""

    def test_get_all_schedules(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test getting all schedules without filters."""
        # Generate schedules
        start_date = CHICAGO_TZ.localize(
            datetime(2025, 1, 6, 8, 0, 0)
        )
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get all schedules
        response = client.get("/api/v1/schedules/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_get_schedules_with_date_range(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test getting schedules filtered by date range."""
        # Generate schedules for January 2025
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get schedules for first two weeks of January
        query_start = CHICAGO_TZ.localize(datetime(2025, 1, 1, 0, 0, 0))
        query_end = CHICAGO_TZ.localize(datetime(2025, 1, 14, 23, 59, 59))

        response = client.get(
            f"/api/v1/schedules/?start_date={query_start.isoformat()}&end_date={query_end.isoformat()}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


class TestGetMemberSchedules:
    """Tests for GET /api/v1/schedules/member/{id}"""

    def test_get_member_schedules(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test getting all schedules for a specific team member."""
        members = setup_team_and_shifts["members"]

        # Generate schedules
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get schedules for first member
        member_id = members[0].id
        response = client.get(f"/api/v1/schedules/member/{member_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Verify all schedules are for the correct member
        for schedule in data:
            assert schedule["team_member_id"] == member_id


class TestGenerateSchedule:
    """Tests for POST /api/v1/schedules/generate"""

    def test_generate_valid_schedule(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test generating a valid schedule."""
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))

        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )

        assert response.status_code == 201
        data = response.json()["schedules"]
        assert len(data) > 0
        # With 3 members and 6 shifts per week, over 4 weeks = 24 assignments
        assert len(data) == 24

    def test_generate_duplicate_without_force(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test generating schedule when schedules already exist (without force)."""
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))

        # Generate first time
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": False
            }
        )
        assert response.status_code == 201

        # Try to generate again without force
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": False
            }
        )
        assert response.status_code == 400
        assert "already exist" in response.json()["detail"].lower()

    def test_generate_with_force(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test force regenerating existing schedules."""
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))

        # Generate first time
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": False
            }
        )
        assert response.status_code == 201
        first_schedule_count = len(response.json()["schedules"])

        # Force regenerate
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": True
            }
        )
        assert response.status_code == 201
        second_schedule_count = len(response.json()["schedules"])
        # Should have same count
        assert second_schedule_count == first_schedule_count

    def test_generate_without_team_members(self, client: TestClient, db_session: Session):
        """Test generating schedule without any active team members."""
        # Create shifts but no team members
        shifts = [
            Shift(shift_number=1, day_of_week="Monday", duration_hours=24, start_time="08:00"),
        ]
        db_session.add_all(shifts)
        db_session.commit()

        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 1,
                "force": False
            }
        )
        assert response.status_code == 400
        assert "no active team members" in response.json()["detail"].lower()

    def test_generate_without_shifts(self, client: TestClient, db_session: Session):
        """Test generating schedule without any configured shifts."""
        # Create team members but no shifts
        members = [
            TeamMember(name="Alice", phone="+15551111111", is_active=True),
        ]
        db_session.add_all(members)
        db_session.commit()

        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 1,
                "force": False
            }
        )
        assert response.status_code == 400
        assert "no shifts configured" in response.json()["detail"].lower()


class TestGenerateScheduleEnvelope:
    """Tests for the WOF-9 response envelope and anchored generation."""

    def test_generate_returns_envelope_with_schedules_and_warnings(
        self, client: TestClient, setup_team_and_shifts
    ):
        """POST /generate returns {schedules: [...], warnings: [...]}."""
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))  # Monday

        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": False
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert set(data.keys()) == {"schedules", "warnings"}
        assert len(data["schedules"]) == 12  # 6 shifts * 2 weeks
        assert data["warnings"] == []  # past Monday start: nothing to warn about

    def test_generate_today_after_8am_includes_missed_notification_warning(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Starting today after 8 AM CT returns the missed-SMS warning."""
        # 15:00 UTC = 09:00 CST on Tuesday 2025-01-07
        with freeze_time("2025-01-07 15:00:00"):
            response = client.post(
                "/api/v1/schedules/generate",
                json={
                    "start_date": "2025-01-07T08:00:00-06:00",
                    "weeks": 1,
                    "force": False
                }
            )

        assert response.status_code == 201
        data = response.json()
        assert any("notification" in w.lower() for w in data["warnings"])
        # Anchored: the earliest entry is today, not Monday of the week
        earliest = min(s["start_datetime"] for s in data["schedules"])
        assert earliest.startswith("2025-01-07")

    def test_generate_midweek_first_member_on_start_date(
        self, client: TestClient, setup_team_and_shifts
    ):
        """End-to-end: member 1 is assigned the chosen mid-week start date."""
        members = setup_team_and_shifts["members"]
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 7, 8, 0, 0))  # Tuesday

        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 2,
                "force": False
            }
        )

        assert response.status_code == 201
        schedules = response.json()["schedules"]
        first = min(schedules, key=lambda s: s["start_datetime"])
        assert first["start_datetime"].startswith("2025-01-07")
        assert first["team_member_id"] == members[0].id


class TestRegenerateSchedule:
    """Tests for POST /api/v1/schedules/regenerate"""

    def test_regenerate_from_date(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test regenerating schedules from a specific date."""
        # Generate initial 4 weeks
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )
        assert response.status_code == 201

        # Regenerate from week 3 onwards
        regenerate_date = CHICAGO_TZ.localize(datetime(2025, 1, 20, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/regenerate",
            json={
                "from_date": regenerate_date.isoformat(),
                "weeks": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


class TestGetNextAssignment:
    """Tests for GET /api/v1/schedules/member/{id}/next"""

    def test_get_next_assignment(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test getting next assignment for a team member."""
        members = setup_team_and_shifts["members"]

        # Generate future schedules
        start_date = CHICAGO_TZ.localize(
            (datetime.now() + timedelta(days=7)).replace(hour=8, minute=0, second=0, microsecond=0)
        )
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )
        assert response.status_code == 201

        # Get next assignment
        member_id = members[0].id
        response = client.get(f"/api/v1/schedules/member/{member_id}/next")
        assert response.status_code == 200
        # May return a schedule or null if none exist
        data = response.json()
        if data is not None:
            assert data["team_member_id"] == member_id


class TestScheduleIntegration:
    """Integration tests for schedule workflows."""

    def test_full_schedule_lifecycle(
        self, client: TestClient, setup_team_and_shifts
    ):
        """Test complete schedule lifecycle: generate -> query -> regenerate."""
        # Generate initial schedule
        start_date = CHICAGO_TZ.localize(datetime(2025, 1, 6, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "start_date": start_date.isoformat(),
                "weeks": 4,
                "force": False
            }
        )
        assert response.status_code == 201
        initial_count = len(response.json()["schedules"])

        # Query current week
        response = client.get("/api/v1/schedules/current")
        assert response.status_code == 200

        # Query upcoming
        response = client.get("/api/v1/schedules/upcoming?weeks=4")
        assert response.status_code == 200

        # Query by date range
        query_start = CHICAGO_TZ.localize(datetime(2025, 1, 1, 0, 0, 0))
        query_end = CHICAGO_TZ.localize(datetime(2025, 1, 31, 23, 59, 59))
        response = client.get(
            f"/api/v1/schedules/?start_date={query_start.isoformat()}&end_date={query_end.isoformat()}"
        )
        assert response.status_code == 200

        # Regenerate from midpoint
        regenerate_date = CHICAGO_TZ.localize(datetime(2025, 1, 20, 8, 0, 0))
        response = client.post(
            "/api/v1/schedules/regenerate",
            json={
                "from_date": regenerate_date.isoformat(),
                "weeks": 2
            }
        )
        assert response.status_code == 200
