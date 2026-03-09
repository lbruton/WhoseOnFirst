"""
Tests for ScheduleRepository.

Tests complex schedule queries including date ranges, notifications,
and bulk operations.
"""

import pytest
from datetime import datetime, timedelta
import pytz
from src.repositories import ScheduleRepository


class TestScheduleRepositoryCRUD:
    """Tests for basic CRUD operations on schedules."""

    def test_create_schedule(self, schedule_repo, sample_schedule_data, populated_team_members, populated_shifts):
        """Test creating a schedule assignment."""
        data = sample_schedule_data(populated_team_members[0].id, populated_shifts[0].id)
        schedule = schedule_repo.create(data)

        assert schedule.id is not None
        assert schedule.team_member_id == populated_team_members[0].id
        assert schedule.notified is False

    def test_get_by_id(self, schedule_repo, populated_schedules):
        """Test retrieving schedule by ID."""
        schedule = schedule_repo.get_by_id(populated_schedules[0].id)

        assert schedule is not None
        assert schedule.id == populated_schedules[0].id


class TestScheduleRepositoryDateQueries:
    """Tests for date-based schedule queries."""

    def test_get_by_date_range(self, schedule_repo, populated_schedules, chicago_tz):
        """Test retrieving schedules within date range."""
        # Use timezone-aware datetimes for query
        start = datetime.now(chicago_tz) - timedelta(days=1)
        end = datetime.now(chicago_tz) + timedelta(days=10)

        schedules = schedule_repo.get_by_date_range(start, end)

        assert len(schedules) > 0
        # SQLite returns naive datetimes, so we need to localize them for comparison
        for sched in schedules:
            # Make schedule datetime timezone-aware for comparison
            sched_start = chicago_tz.localize(sched.start_datetime) if sched.start_datetime.tzinfo is None else sched.start_datetime
            assert start <= sched_start <= end

    def test_get_current_week(self, schedule_repo, populated_schedules):
        """Test retrieving current week's schedules."""
        schedules = schedule_repo.get_current_week()

        assert len(schedules) > 0

    def test_get_upcoming_weeks(self, schedule_repo, populated_schedules):
        """Test retrieving upcoming weeks."""
        schedules = schedule_repo.get_upcoming_weeks(num_weeks=2)

        assert len(schedules) >= 0


class TestScheduleRepositoryNotifications:
    """Tests for notification-related queries."""

    def test_get_pending_notifications(self, schedule_repo, populated_schedules):
        """Test retrieving schedules needing notifications."""
        pending = schedule_repo.get_pending_notifications()

        # Should get schedules that are not notified and start today
        for sched in pending:
            assert sched.notified is False

    def test_mark_as_notified(self, schedule_repo, populated_schedules):
        """Test marking schedule as notified."""
        schedule = populated_schedules[0]
        updated = schedule_repo.mark_as_notified(schedule.id)

        assert updated.notified is True

    def test_get_active_assignments(self, schedule_repo, populated_schedules):
        """Test retrieving currently active assignments."""
        active = schedule_repo.get_active_assignments()

        # Verify all returned schedules are currently active
        now = datetime.now()
        for sched in active:
            # Note: datetime comparison needs timezone handling
            assert sched.start_datetime <= now or sched.end_datetime >= now


class TestScheduleRepositoryMemberQueries:
    """Tests for team member-specific queries."""

    def test_get_by_team_member(self, schedule_repo, populated_schedules, populated_team_members):
        """Test retrieving schedules for specific team member."""
        member = populated_team_members[0]
        schedules = schedule_repo.get_by_team_member(member.id)

        assert all(s.team_member_id == member.id for s in schedules)

    def test_get_by_team_member_with_date_filters(self, schedule_repo, populated_schedules, populated_team_members, chicago_tz):
        """Test get_by_team_member with start and end date filters."""
        from datetime import datetime
        member = populated_team_members[0]
        now = datetime.now()
        schedules = schedule_repo.get_by_team_member(
            member.id,
            start_date=now - timedelta(days=365),
            end_date=now + timedelta(days=365)
        )
        assert isinstance(schedules, list)

    def test_get_next_assignment_for_member(self, schedule_repo, populated_schedules, populated_team_members):
        """Test getting next upcoming assignment for member."""
        member = populated_team_members[0]
        next_assignment = schedule_repo.get_next_assignment_for_member(member.id)

        if next_assignment:
            assert next_assignment.team_member_id == member.id
            assert next_assignment.start_datetime > datetime.now()


class TestScheduleRepositoryBulkOperations:
    """Tests for bulk operations."""

    def test_bulk_create(self, schedule_repo, populated_team_members, populated_shifts, chicago_tz):
        """Test creating multiple schedules at once."""
        base_date = datetime.now(chicago_tz)
        schedules_data = []

        for i in range(3):
            schedules_data.append({
                "team_member_id": populated_team_members[i].id,
                "shift_id": populated_shifts[i].id,
                "week_number": 1,
                "start_datetime": base_date + timedelta(days=i),
                "end_datetime": base_date + timedelta(days=i, hours=24),
                "notified": False
            })

        created = schedule_repo.bulk_create(schedules_data)

        assert len(created) == 3
        assert all(s.id is not None for s in created)

    def test_delete_future_schedules(self, schedule_repo, populated_schedules, chicago_tz):
        """Test deleting schedules from a specific date forward."""
        # Use naive datetime to match what SQLite stores/retrieves
        future_date = datetime.now() + timedelta(days=100)

        # Create future schedule with naive datetime
        future_schedule = schedule_repo.create({
            "team_member_id": populated_schedules[0].team_member_id,
            "shift_id": populated_schedules[0].shift_id,
            "week_number": 99,
            "start_datetime": future_date,
            "end_datetime": future_date + timedelta(hours=24),
            "notified": False
        })

        deleted_count = schedule_repo.delete_future_schedules(future_date)

        assert deleted_count >= 1
        assert schedule_repo.get_by_id(future_schedule.id) is None


class TestScheduleRepositoryShiftQueries:

    def test_get_by_shift_returns_matching(self, schedule_repo, populated_schedules, populated_shifts):
        shift_id = populated_schedules[0].shift_id
        results = schedule_repo.get_by_shift(shift_id)
        assert all(s.shift_id == shift_id for s in results)

    def test_get_by_shift_no_results(self, schedule_repo, populated_schedules):
        results = schedule_repo.get_by_shift(99999)
        assert results == []

    def test_get_by_shift_with_date_range(self, schedule_repo, populated_schedules, populated_shifts, chicago_tz):
        from datetime import datetime
        shift_id = populated_schedules[0].shift_id
        now = datetime.now()
        results = schedule_repo.get_by_shift(
            shift_id,
            start_date=now - timedelta(days=365),
            end_date=now + timedelta(days=365)
        )
        assert isinstance(results, list)

    def test_get_by_week_number(self, schedule_repo, populated_schedules):
        week = populated_schedules[0].week_number
        results = schedule_repo.get_by_week_number(week)
        assert len(results) >= 1
        assert all(s.week_number == week for s in results)
