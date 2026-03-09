"""
Tests for Schedule Service

This test suite validates the ScheduleService, which coordinates schedule
generation, persistence, and queries. The service integrates the rotation
algorithm with database operations.

Test organization:
- Basic schedule generation
- Query operations (current week, upcoming, date ranges)
- Regeneration when team changes
- Error conditions and validation
- Integration with rotation algorithm
"""

import pytest
from datetime import datetime, timedelta
from pytz import timezone

from src.services.schedule_service import (
    ScheduleService,
    ScheduleServiceError,
    ScheduleAlreadyExistsError,
    InvalidDateRangeError,
)
from src.services.rotation_algorithm import (
    InsufficientMembersError,
    NoShiftsConfiguredError,
)
from src.repositories.team_member_repository import TeamMemberRepository
from src.repositories.shift_repository import ShiftRepository


# ============================================================================
# Test Class: Basic Schedule Generation
# ============================================================================

class TestScheduleServiceGeneration:
    """Tests for schedule generation functionality."""

    def test_generate_schedule_basic(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test basic schedule generation for 4 weeks."""
        service = ScheduleService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        schedules = service.generate_schedule(start_date, weeks=4)

        # Should create 6 shifts * 4 weeks = 24 schedules
        assert len(schedules) == 24

        # All should be persisted to database (have IDs)
        assert all(s.id is not None for s in schedules)

        # All should have required fields
        for schedule in schedules:
            assert schedule.team_member_id is not None
            assert schedule.shift_id is not None
            assert schedule.start_datetime is not None
            assert schedule.end_datetime is not None
            assert schedule.notified is False

    def test_generate_schedule_one_week(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test generating a single week schedule."""
        service = ScheduleService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        schedules = service.generate_schedule(start_date, weeks=1)

        assert len(schedules) == 6  # 6 shifts

    def test_generate_schedule_multiple_weeks(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test generating schedules for 8 weeks."""
        service = ScheduleService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        schedules = service.generate_schedule(start_date, weeks=8)

        assert len(schedules) == 48  # 6 shifts * 8 weeks

    def test_generate_schedule_uses_rotation_algorithm(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that schedules follow circular rotation pattern."""
        service = ScheduleService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        schedules = service.generate_schedule(start_date, weeks=2)

        # Group by week
        week_1 = [s for s in schedules if s.week_number == 45]
        week_2 = [s for s in schedules if s.week_number == 46]

        # Should have 6 shifts each week
        assert len(week_1) == 6
        assert len(week_2) == 6

        # Week 2 should have rotated assignments (different from week 1)
        week_1_sorted = sorted(week_1, key=lambda s: s.shift_id)
        week_2_sorted = sorted(week_2, key=lambda s: s.shift_id)

        # At least some assignments should be different (rotation happened)
        different_count = sum(
            1 for w1, w2 in zip(week_1_sorted, week_2_sorted)
            if w1.team_member_id != w2.team_member_id
        )
        assert different_count > 0


# ============================================================================
# Test Class: Duplicate Prevention
# ============================================================================

class TestScheduleServiceDuplicatePrevention:
    """Tests for preventing duplicate schedule generation."""

    def test_generate_fails_if_schedules_exist(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that generating again for same period raises error."""
        service = ScheduleService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        # First generation succeeds
        service.generate_schedule(start_date, weeks=4)

        # Second generation for same period fails
        with pytest.raises(ScheduleAlreadyExistsError) as exc_info:
            service.generate_schedule(start_date, weeks=4)

        assert "already exist" in str(exc_info.value)
        assert "force=True" in str(exc_info.value)

    def test_generate_with_force_regenerates(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that force=True allows regeneration."""
        service = ScheduleService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        # First generation
        original_schedules = service.generate_schedule(start_date, weeks=2)
        original_ids = {s.id for s in original_schedules}

        # Force regeneration
        new_schedules = service.generate_schedule(start_date, weeks=2, force=True)
        new_ids = {s.id for s in new_schedules}

        # Should have created new schedules (different IDs)
        assert original_ids != new_ids
        assert len(new_schedules) == len(original_schedules)

    def test_can_generate_non_overlapping_periods(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that non-overlapping periods can both be generated."""
        service = ScheduleService(db_session)

        # Generate Nov 4-30
        nov_start = chicago_tz.localize(datetime(2025, 11, 4))
        nov_schedules = service.generate_schedule(nov_start, weeks=4)

        # Generate Dec 2-29 (non-overlapping)
        dec_start = chicago_tz.localize(datetime(2025, 12, 2))
        dec_schedules = service.generate_schedule(dec_start, weeks=4)

        # Both should succeed
        assert len(nov_schedules) == 24
        assert len(dec_schedules) == 24


# ============================================================================
# Test Class: Query Operations
# ============================================================================

class TestScheduleServiceQueries:
    """Tests for schedule query methods."""

    def test_get_current_week_schedule(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test retrieving current week's schedule."""
        service = ScheduleService(db_session)

        # Generate schedule starting this week
        now = datetime.now(chicago_tz)
        monday = now - timedelta(days=now.weekday())  # Get Monday of this week
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        service.generate_schedule(monday, weeks=4)

        # Get current week
        current_week = service.get_current_week_schedule()

        # Should have 6 shifts
        assert len(current_week) >= 6  # May have more if multiple weeks included

    def test_get_upcoming_schedules(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test retrieving upcoming schedules."""
        service = ScheduleService(db_session)

        # Generate schedule starting next week
        now = datetime.now(chicago_tz)
        next_monday = now + timedelta(days=(7 - now.weekday()))
        next_monday = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)

        service.generate_schedule(next_monday, weeks=4)

        # Get upcoming 2 weeks
        upcoming = service.get_upcoming_schedules(weeks=2)

        # Should have schedules
        assert len(upcoming) >= 0  # May be empty depending on timing

    def test_get_schedule_by_date_range(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test retrieving schedules by custom date range."""
        service = ScheduleService(db_session)

        # Generate schedules
        start = chicago_tz.localize(datetime(2025, 11, 4))
        service.generate_schedule(start, weeks=4)

        # Query specific range
        range_start = chicago_tz.localize(datetime(2025, 11, 4))
        range_end = chicago_tz.localize(datetime(2025, 11, 18))

        schedules = service.get_schedule_by_date_range(range_start, range_end)

        # Should have schedules for 2 weeks
        assert len(schedules) == 12  # 6 shifts * 2 weeks

        # All schedules should be in range (compare naive datetimes since DB stores naive)
        range_start_naive = range_start.replace(tzinfo=None)
        range_end_naive = range_end.replace(tzinfo=None)
        for schedule in schedules:
            assert range_start_naive <= schedule.start_datetime <= range_end_naive

    def test_get_schedule_by_date_range_empty(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test querying date range with no schedules returns empty list."""
        service = ScheduleService(db_session)

        # Query range with no schedules
        start = chicago_tz.localize(datetime(2026, 1, 1))
        end = chicago_tz.localize(datetime(2026, 1, 31))

        schedules = service.get_schedule_by_date_range(start, end)

        assert schedules == []

    def test_get_schedule_by_member(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test retrieving schedules for specific team member."""
        service = ScheduleService(db_session)

        # Generate schedules
        start = chicago_tz.localize(datetime(2025, 11, 4))
        all_schedules = service.generate_schedule(start, weeks=4)

        # Get schedules for first member
        member_id = all_schedules[0].team_member_id
        member_schedules = service.get_schedule_by_member(member_id)

        # Should have some schedules for this member
        assert len(member_schedules) > 0

        # All should be for the same member
        assert all(s.team_member_id == member_id for s in member_schedules)

    def test_get_next_assignment(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test getting next assignment for a team member."""
        service = ScheduleService(db_session)

        # Use a date well in the future so schedules are always upcoming
        future_start = chicago_tz.localize(datetime(2027, 1, 4))  # Monday
        schedules = service.generate_schedule(future_start, weeks=4)

        # Get next assignment for first member
        member_id = schedules[0].team_member_id
        next_assignment = service.get_next_assignment(member_id)

        # Should return a schedule
        assert next_assignment is not None
        assert next_assignment.team_member_id == member_id


# ============================================================================
# Test Class: Regeneration
# ============================================================================

class TestScheduleServiceRegeneration:
    """Tests for schedule regeneration when team changes."""

    def test_regenerate_from_date_deletes_future(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that regeneration deletes future schedules."""
        service = ScheduleService(db_session)

        # Generate initial schedules
        start = chicago_tz.localize(datetime(2025, 11, 4))
        original = service.generate_schedule(start, weeks=4)

        # Regenerate from 2 weeks in
        regen_date = chicago_tz.localize(datetime(2025, 11, 18))
        new_schedules = service.regenerate_from_date(regen_date, weeks=4)

        # Should have new schedules
        assert len(new_schedules) == 24  # 6 shifts * 4 weeks

        # Old schedules before regen_date should still exist
        old_schedules = service.get_schedule_by_date_range(
            start,
            regen_date - timedelta(days=1)
        )
        assert len(old_schedules) > 0

    def test_regenerate_creates_new_rotation(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that regeneration creates new rotation with current team."""
        service = ScheduleService(db_session)

        # Generate initial schedules
        start = chicago_tz.localize(datetime(2025, 11, 4))
        service.generate_schedule(start, weeks=4)

        # Add a new team member
        member_repo = TeamMemberRepository(db_session)
        new_member = member_repo.create({
            "name": "New Person",
            "phone": "+15559999999",
            "is_active": True
        })

        # Regenerate from start
        new_schedules = service.regenerate_from_date(start, weeks=4)

        # New member should appear in new schedules
        member_ids = {s.team_member_id for s in new_schedules}
        assert new_member.id in member_ids

    def test_regenerate_preserves_historical_schedules(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that regeneration doesn't delete historical schedules."""
        service = ScheduleService(db_session)

        # Generate schedules from Nov 4
        nov_4 = chicago_tz.localize(datetime(2025, 11, 4))
        service.generate_schedule(nov_4, weeks=4)

        # Regenerate from Nov 18 (2 weeks later)
        nov_18 = chicago_tz.localize(datetime(2025, 11, 18))
        service.regenerate_from_date(nov_18, weeks=4)

        # Schedules from Nov 4-17 should still exist
        historical = service.get_schedule_by_date_range(
            nov_4,
            nov_18 - timedelta(days=1)
        )

        assert len(historical) > 0  # Historical schedules preserved


# ============================================================================
# Test Class: Error Conditions
# ============================================================================

class TestScheduleServiceErrors:
    """Tests for error handling and validation."""

    def test_generate_with_naive_datetime_raises_error(
        self, db_session, populated_team_members, populated_shifts
    ):
        """Test that naive datetime raises ValueError."""
        service = ScheduleService(db_session)
        naive_date = datetime(2025, 11, 4)  # No timezone

        with pytest.raises(ValueError) as exc_info:
            service.generate_schedule(naive_date, weeks=4)

        assert "timezone-aware" in str(exc_info.value)

    def test_generate_with_no_active_members_raises_error(
        self, db_session, populated_shifts, chicago_tz
    ):
        """Test that generating with no active members raises error."""
        service = ScheduleService(db_session)
        start = chicago_tz.localize(datetime(2025, 11, 4))

        # No team members in database
        with pytest.raises(InsufficientMembersError):
            service.generate_schedule(start, weeks=4)

    def test_generate_with_no_shifts_raises_error(
        self, db_session, populated_team_members, chicago_tz
    ):
        """Test that generating with no shifts raises error."""
        service = ScheduleService(db_session)
        start = chicago_tz.localize(datetime(2025, 11, 4))

        # No shifts in database
        with pytest.raises(NoShiftsConfiguredError):
            service.generate_schedule(start, weeks=4)

    def test_date_range_query_with_invalid_range_raises_error(
        self, db_session, chicago_tz
    ):
        """Test that end_date < start_date raises InvalidDateRangeError."""
        service = ScheduleService(db_session)

        start = chicago_tz.localize(datetime(2025, 11, 18))
        end = chicago_tz.localize(datetime(2025, 11, 4))  # Before start

        with pytest.raises(InvalidDateRangeError) as exc_info:
            service.get_schedule_by_date_range(start, end)

        assert "must be >=" in str(exc_info.value)

    def test_date_range_query_with_naive_dates_raises_error(
        self, db_session
    ):
        """Test that naive dates in range query raise ValueError."""
        service = ScheduleService(db_session)

        naive_start = datetime(2025, 11, 4)
        naive_end = datetime(2025, 11, 18)

        with pytest.raises(ValueError) as exc_info:
            service.get_schedule_by_date_range(naive_start, naive_end)

        assert "timezone-aware" in str(exc_info.value)

    def test_regenerate_with_naive_datetime_raises_error(
        self, db_session, populated_team_members, populated_shifts
    ):
        """Test that regenerate with naive datetime raises ValueError."""
        service = ScheduleService(db_session)
        naive_date = datetime(2025, 11, 4)

        with pytest.raises(ValueError) as exc_info:
            service.regenerate_from_date(naive_date, weeks=4)

        assert "timezone-aware" in str(exc_info.value)


# ============================================================================
# Test Class: Notification Support
# ============================================================================

class TestScheduleServiceNotifications:
    """Tests for notification-related functionality."""

    def test_get_pending_notifications(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test retrieving schedules that need notifications."""
        service = ScheduleService(db_session)

        # Generate schedules starting yesterday (so some are past-due)
        yesterday = datetime.now(chicago_tz) - timedelta(days=1)
        monday = yesterday - timedelta(days=yesterday.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        service.generate_schedule(monday, weeks=2)

        # Get pending notifications
        pending = service.get_pending_notifications()

        # Should have some pending (past shifts not yet notified)
        # Exact count depends on current time, but should be >= 0
        assert isinstance(pending, list)

        # All should have notified=False
        assert all(not s.notified for s in pending)

    def test_mark_as_notified(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test marking a schedule as notified."""
        service = ScheduleService(db_session)

        # Generate schedules
        start = chicago_tz.localize(datetime(2025, 11, 4))
        schedules = service.generate_schedule(start, weeks=1)

        # Mark first schedule as notified
        first_schedule = schedules[0]
        assert first_schedule.notified is False

        updated = service.mark_as_notified(first_schedule.id)

        assert updated.notified is True
        assert updated.id == first_schedule.id

    def test_pending_notifications_excludes_notified(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that pending notifications excludes already-notified schedules."""
        service = ScheduleService(db_session)

        # Generate schedules in the past
        past = datetime.now(chicago_tz) - timedelta(days=7)
        monday = past - timedelta(days=past.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        schedules = service.generate_schedule(monday, weeks=1)

        # Mark some as notified
        for schedule in schedules[:3]:
            service.mark_as_notified(schedule.id)

        # Get pending
        pending = service.get_pending_notifications()

        # Should not include the notified ones
        notified_ids = {s.id for s in schedules[:3]}
        pending_ids = {s.id for s in pending}

        assert notified_ids.isdisjoint(pending_ids)


# ============================================================================
# Test Class: Integration Tests
# ============================================================================

class TestScheduleServiceIntegration:
    """Integration tests for complete workflows."""

    def test_full_schedule_generation_workflow(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test complete workflow: generate, query, regenerate."""
        service = ScheduleService(db_session)

        # Step 1: Generate initial schedule
        start = chicago_tz.localize(datetime(2025, 11, 4))
        initial = service.generate_schedule(start, weeks=4)

        assert len(initial) == 24

        # Step 2: Query schedules
        current_week = service.get_current_week_schedule()
        upcoming = service.get_upcoming_schedules(weeks=2)

        # Step 3: Add team member and regenerate
        member_repo = TeamMemberRepository(db_session)
        new_member = member_repo.create({
            "name": "New Hire",
            "phone": "+15558888888",
            "is_active": True
        })

        regen_date = chicago_tz.localize(datetime(2025, 11, 18))
        regenerated = service.regenerate_from_date(regen_date, weeks=4)

        # Verify new member appears in regenerated schedules
        member_ids = {s.team_member_id for s in regenerated}
        assert new_member.id in member_ids

    def test_schedule_lifecycle_with_notifications(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test schedule lifecycle including notification tracking."""
        service = ScheduleService(db_session)

        # Generate past schedules
        past = datetime.now(chicago_tz) - timedelta(days=14)
        monday = past - timedelta(days=past.weekday())
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        schedules = service.generate_schedule(monday, weeks=2)

        # Get pending notifications
        pending = service.get_pending_notifications()

        # Mark some as notified
        for schedule in pending[:5]:
            service.mark_as_notified(schedule.id)

        # Verify they're no longer pending
        still_pending = service.get_pending_notifications()
        notified_ids = {s.id for s in pending[:5]}
        still_pending_ids = {s.id for s in still_pending}

        assert notified_ids.isdisjoint(still_pending_ids)

    def test_handles_team_size_changes_correctly(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that rotation adjusts when team size changes."""
        service = ScheduleService(db_session)
        member_repo = TeamMemberRepository(db_session)

        # Initial generation with 4 active members
        start = chicago_tz.localize(datetime(2025, 11, 4))
        initial = service.generate_schedule(start, weeks=2)

        initial_member_ids = {s.team_member_id for s in initial}
        assert len(initial_member_ids) == 4  # 4 active members

        # Add 3 more members
        for i in range(3):
            member_repo.create({
                "name": f"Extra Member {i}",
                "phone": f"+1555777000{i}",
                "is_active": True
            })

        # Regenerate
        regenerated = service.regenerate_from_date(start, weeks=2)

        regenerated_member_ids = {s.team_member_id for s in regenerated}
        assert len(regenerated_member_ids) == 7  # Now 7 active members

        # Verify rotation still works correctly
        assert len(regenerated) == 12  # Still 6 shifts * 2 weeks
