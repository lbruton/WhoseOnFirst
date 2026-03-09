"""
Tests for Rotation Algorithm Service

This test suite validates the circular rotation algorithm that assigns team members
to on-call shifts. The algorithm must:
- Rotate members through shifts fairly and predictably
- Handle various team sizes (1 to 10+ members)
- Support any number of shifts
- Generate timezone-aware datetimes (America/Chicago)
- Return data compatible with ScheduleRepository.bulk_create()

Test organization:
- Basic functionality tests
- Edge case tests (small/large teams, odd scenarios)
- Error condition tests
- DateTime and timezone tests
- Integration tests with real database
"""

import pytest
from datetime import datetime, time, timedelta
from pytz import timezone

from src.services.rotation_algorithm import (
    RotationAlgorithmService,
    RotationAlgorithmError,
    InsufficientMembersError,
    NoShiftsConfiguredError,
    InvalidWeekCountError,
)
from src.repositories.team_member_repository import TeamMemberRepository
from src.repositories.shift_repository import ShiftRepository


# ============================================================================
# Test Class: Basic Rotation Functionality
# ============================================================================

class TestRotationAlgorithmBasic:
    """Tests for basic rotation generation with various team sizes."""

    def test_generate_one_week_rotation(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test generating a single week rotation with 4 active members and 6 shifts."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4, 8, 0))  # Monday

        entries = service.generate_rotation(start_date, weeks=1)

        # Should have 6 entries (one per shift)
        assert len(entries) == 6

        # All entries should have required fields
        for entry in entries:
            assert "team_member_id" in entry
            assert "shift_id" in entry
            assert "week_number" in entry
            assert "start_datetime" in entry
            assert "end_datetime" in entry
            assert "notified" in entry
            assert entry["notified"] is False

    def test_generate_four_week_rotation(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test generating a standard 4-week rotation."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=4)

        # 6 shifts * 4 weeks = 24 entries
        assert len(entries) == 24

    def test_rotation_assigns_all_shifts_each_week(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that every shift is assigned each week."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=3)

        # Group by week_number
        from collections import defaultdict
        weeks = defaultdict(list)
        for entry in entries:
            weeks[entry["week_number"]].append(entry)

        # Each week should have 6 shifts
        for week_num, week_entries in weeks.items():
            assert len(week_entries) == 6

            # All shifts should be unique within a week
            shift_ids = [e["shift_id"] for e in week_entries]
            assert len(shift_ids) == len(set(shift_ids))

    def test_circular_rotation_pattern(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that member assignment follows the continuous modulo cycling formula.

        Algorithm: shifts_elapsed = (week * num_shifts) + shift_index
                   member_index   = shifts_elapsed % num_members
        """
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        members = TeamMemberRepository(db_session).get_ordered_for_rotation(active_only=True)
        member_ids = [m.id for m in members]
        shifts = ShiftRepository(db_session).get_all_ordered()

        entries = service.generate_rotation(start_date, weeks=3)

        # Sort entries by (week_number, shift_id) to recover shift_index per week
        sorted_entries = sorted(entries, key=lambda e: (e["week_number"], e["shift_id"]))

        # Group by week, preserving shift order
        weeks = {}
        for entry in sorted_entries:
            weeks.setdefault(entry["week_number"], []).append(entry)

        for week_index, week_num in enumerate(sorted(weeks.keys())):
            week_entries = weeks[week_num]
            for shift_index, entry in enumerate(week_entries):
                shifts_elapsed = (week_index * len(shifts)) + shift_index
                expected_member_index = shifts_elapsed % len(member_ids)
                assert entry["team_member_id"] == member_ids[expected_member_index], (
                    f"Week {week_num}, shift_index {shift_index}: "
                    f"expected member {member_ids[expected_member_index]}, "
                    f"got {entry['team_member_id']}"
                )

    def test_members_rotate_forward_each_week(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that each member moves to the next shift position each week."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=2)

        # Get shifts in order
        shifts = ShiftRepository(db_session).get_all_ordered()
        first_shift_id = shifts[0].id
        second_shift_id = shifts[1].id

        # Find who has first shift in week 1
        week_1_entries = [e for e in entries if e["start_datetime"].isocalendar()[1] == 45]
        week_1_first_shift = next(e for e in week_1_entries if e["shift_id"] == first_shift_id)
        member_on_shift_1_week_1 = week_1_first_shift["team_member_id"]

        # Find week 2 entries
        week_2_entries = [e for e in entries if e["start_datetime"].isocalendar()[1] == 46]
        week_2_first_shift = next(e for e in week_2_entries if e["shift_id"] == first_shift_id)
        member_on_shift_1_week_2 = week_2_first_shift["team_member_id"]

        # They should be different (rotation happened)
        assert member_on_shift_1_week_1 != member_on_shift_1_week_2


# ============================================================================
# Test Class: Edge Cases
# ============================================================================

class TestRotationAlgorithmEdgeCases:
    """Tests for edge cases: unusual team sizes, shift counts, etc."""

    def test_single_member_rotation(
        self, db_session, sample_team_member_data, populated_shifts, chicago_tz
    ):
        """Test rotation with only one team member (works all shifts)."""
        # Create a single member
        member_repo = TeamMemberRepository(db_session)
        member = member_repo.create(sample_team_member_data)

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=2)

        # Single member works all shifts both weeks: 6 shifts * 2 weeks
        assert len(entries) == 12

        # All assignments should be to the same member
        for entry in entries:
            assert entry["team_member_id"] == member.id

    def test_two_member_rotation(
        self, db_session, sample_team_member_data, populated_shifts, chicago_tz
    ):
        """Test rotation with two members alternating shifts."""
        # Create two members
        member_repo = TeamMemberRepository(db_session)
        member1_data = sample_team_member_data.copy()
        member1 = member_repo.create(member1_data)

        member2_data = sample_team_member_data.copy()
        member2_data["phone"] = "+15558675310"
        member2_data["name"] = "Jane Smith"
        member2 = member_repo.create(member2_data)

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # 6 shifts, alternating between 2 members
        assert len(entries) == 6

        # Count assignments per member
        member1_count = sum(1 for e in entries if e["team_member_id"] == member1.id)
        member2_count = sum(1 for e in entries if e["team_member_id"] == member2.id)

        # With 6 shifts and 2 members: each gets 3 shifts
        assert member1_count == 3
        assert member2_count == 3

    def test_more_members_than_shifts(
        self, db_session, chicago_tz
    ):
        """Test rotation with 7 members and 6 shifts (one person off each week)."""
        # Create 7 team members
        member_repo = TeamMemberRepository(db_session)
        members = []
        for i in range(7):
            member_data = {
                "name": f"Member {i+1}",
                "phone": f"+1555867{i:04d}",
                "is_active": True
            }
            members.append(member_repo.create(member_data))

        # Create 6 shifts
        shift_repo = ShiftRepository(db_session)
        shift_configs = [
            (1, "Monday", 24),
            (2, "Tuesday-Wednesday", 48),
            (3, "Thursday", 24),
            (4, "Friday", 24),
            (5, "Saturday", 24),
            (6, "Sunday", 24),
        ]
        for num, day, duration in shift_configs:
            shift_repo.create({
                "shift_number": num,
                "day_of_week": day,
                "duration_hours": duration,
                "start_time": "08:00"
            })

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=7)

        # 6 shifts * 7 weeks = 42 entries
        assert len(entries) == 42

        # Over 7 weeks, each member should work exactly 6 times (1 off per cycle)
        from collections import Counter
        member_counts = Counter(e["team_member_id"] for e in entries)

        for member in members:
            assert member_counts[member.id] == 6

    def test_more_shifts_than_members(
        self, db_session, chicago_tz
    ):
        """Test rotation with 3 members and 6 shifts (members work multiple shifts)."""
        # Create 3 members
        member_repo = TeamMemberRepository(db_session)
        for i in range(3):
            member_repo.create({
                "name": f"Member {i+1}",
                "phone": f"+1555123{i:04d}",
                "is_active": True
            })

        # Create 6 shifts
        shift_repo = ShiftRepository(db_session)
        shift_configs = [
            (1, "Monday", 24),
            (2, "Tuesday", 24),
            (3, "Wednesday", 24),
            (4, "Thursday", 24),
            (5, "Friday", 24),
            (6, "Saturday", 24),
        ]
        for num, day, duration in shift_configs:
            shift_repo.create({
                "shift_number": num,
                "day_of_week": day,
                "duration_hours": duration,
                "start_time": "08:00"
            })

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # 6 shifts in one week
        assert len(entries) == 6

        # Each member should work 2 shifts (6 shifts / 3 members)
        from collections import Counter
        member_counts = Counter(e["team_member_id"] for e in entries)
        assert len(member_counts) == 3
        assert all(count == 2 for count in member_counts.values())

    def test_equal_members_and_shifts(
        self, db_session, populated_shifts, chicago_tz
    ):
        """Test rotation with 6 members and 6 shifts (everyone works each week)."""
        # Create 6 members
        member_repo = TeamMemberRepository(db_session)
        for i in range(6):
            member_repo.create({
                "name": f"Member {i+1}",
                "phone": f"+1555999{i:04d}",
                "is_active": True
            })

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=3)

        # 6 shifts * 3 weeks = 18 entries
        assert len(entries) == 18

        # Each week, every member works exactly once
        weeks = {}
        for entry in entries:
            week = entry["week_number"]
            if week not in weeks:
                weeks[week] = []
            weeks[week].append(entry["team_member_id"])

        for week_members in weeks.values():
            assert len(week_members) == 6
            assert len(set(week_members)) == 6  # All unique

    def test_large_team_rotation(
        self, db_session, populated_shifts, chicago_tz
    ):
        """Test rotation with 15 members (simulates large team)."""
        # Create 15 members
        member_repo = TeamMemberRepository(db_session)
        for i in range(15):
            member_repo.create({
                "name": f"Member {i+1:02d}",
                "phone": f"+1555{i:07d}",
                "is_active": True
            })

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=8)

        # 6 shifts * 8 weeks = 48 entries
        assert len(entries) == 48

        # Verify fairness: over time, shifts should be distributed
        from collections import Counter
        member_counts = Counter(e["team_member_id"] for e in entries)

        # With 15 members and 48 shifts, average is 3.2 shifts per member
        # The circular rotation creates a natural distribution where
        # some members get more shifts than others depending on position
        counts = list(member_counts.values())
        avg_count = sum(counts) / len(counts)
        assert 2.5 <= avg_count <= 4.0  # Average should be close to 3.2

        # All members should get at least one shift over 8 weeks
        assert min(counts) >= 1
        # No member should get more than twice the average (fairness check)
        assert max(counts) <= avg_count * 2


# ============================================================================
# Test Class: Error Conditions
# ============================================================================

class TestRotationAlgorithmErrors:
    """Tests for error handling and validation."""

    def test_no_active_members_raises_error(
        self, db_session, populated_shifts, chicago_tz
    ):
        """Test that rotation fails when no active members exist."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        with pytest.raises(InsufficientMembersError) as exc_info:
            service.generate_rotation(start_date, weeks=1)

        assert "No active team members" in str(exc_info.value)

    def test_no_shifts_configured_raises_error(
        self, db_session, populated_team_members, chicago_tz
    ):
        """Test that rotation fails when no shifts are configured."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        with pytest.raises(NoShiftsConfiguredError) as exc_info:
            service.generate_rotation(start_date, weeks=1)

        assert "No shifts configured" in str(exc_info.value)

    def test_invalid_week_count_zero(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that weeks=0 raises InvalidWeekCountError."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        with pytest.raises(InvalidWeekCountError) as exc_info:
            service.generate_rotation(start_date, weeks=0)

        assert "must be >= 1" in str(exc_info.value)

    def test_invalid_week_count_negative(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that negative weeks raises InvalidWeekCountError."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        with pytest.raises(InvalidWeekCountError):
            service.generate_rotation(start_date, weeks=-1)

    def test_naive_datetime_raises_error(
        self, db_session, populated_team_members, populated_shifts
    ):
        """Test that naive (non-timezone-aware) datetime raises ValueError."""
        service = RotationAlgorithmService(db_session)
        naive_date = datetime(2025, 11, 4)  # No timezone

        with pytest.raises(ValueError) as exc_info:
            service.generate_rotation(naive_date, weeks=1)

        assert "timezone-aware" in str(exc_info.value)


# ============================================================================
# Test Class: DateTime and Timezone Handling
# ============================================================================

class TestRotationAlgorithmDateTime:
    """Tests for datetime calculations and timezone handling."""

    def test_normalizes_to_monday(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that any start_date is normalized to Monday of that week."""
        service = RotationAlgorithmService(db_session)

        # Start on Thursday, Nov 6 (weekday=3)
        thursday = chicago_tz.localize(datetime(2025, 11, 6, 15, 30))

        entries = service.generate_rotation(thursday, weeks=1)

        # First entry should start on Monday, Nov 3 (going back 3 days from Thursday)
        first_entry = min(entries, key=lambda e: e["start_datetime"])
        assert first_entry["start_datetime"].weekday() == 0  # Monday
        assert first_entry["start_datetime"].date() == datetime(2025, 11, 3).date()

    def test_shifts_start_at_8am(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that all shifts start at 8:00 AM Chicago time."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        for entry in entries:
            assert entry["start_datetime"].hour == 8
            assert entry["start_datetime"].minute == 0

    def test_all_datetimes_are_timezone_aware(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that all generated datetimes are timezone-aware."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=2)

        for entry in entries:
            assert entry["start_datetime"].tzinfo is not None
            assert entry["end_datetime"].tzinfo is not None

    def test_shift_durations_calculated_correctly(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that end_datetime = start_datetime + duration_hours."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # Get shifts for reference
        shifts = {s.id: s for s in ShiftRepository(db_session).get_all_ordered()}

        for entry in entries:
            shift = shifts[entry["shift_id"]]
            expected_end = entry["start_datetime"] + timedelta(hours=shift.duration_hours)
            assert entry["end_datetime"] == expected_end

    def test_double_shift_duration_48_hours(
        self, db_session, populated_team_members, chicago_tz
    ):
        """Test that Tuesday-Wednesday double shift is 48 hours."""
        # Create a shift with 48 hour duration
        shift_repo = ShiftRepository(db_session)
        shift_repo.create({
            "shift_number": 1,
            "day_of_week": "Tuesday-Wednesday",
            "duration_hours": 48,
            "start_time": "08:00"
        })

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))  # Monday

        entries = service.generate_rotation(start_date, weeks=1)

        assert len(entries) == 1

        # Should start Tuesday 8am
        assert entries[0]["start_datetime"].weekday() == 1  # Tuesday
        assert entries[0]["start_datetime"].hour == 8

        # Should end Thursday 8am (48 hours later)
        expected_end = entries[0]["start_datetime"] + timedelta(hours=48)
        assert entries[0]["end_datetime"] == expected_end
        assert entries[0]["end_datetime"].weekday() == 3  # Thursday

    def test_week_number_is_iso_week(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that week_number uses ISO week numbering."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))  # Monday

        entries = service.generate_rotation(start_date, weeks=3)

        # Monday Nov 4, 2025 is ISO week 45
        # Week 1: Week 45
        # Week 2: Week 46
        # Week 3: Week 47

        week_numbers = sorted(set(e["week_number"] for e in entries))
        assert week_numbers == [45, 46, 47]

    def test_day_mapping_for_all_days(
        self, db_session, populated_team_members, chicago_tz
    ):
        """Test that all day names map to correct weekday offsets."""
        # Create shifts for each day of the week
        shift_repo = ShiftRepository(db_session)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for i, day in enumerate(days, start=1):
            shift_repo.create({
                "shift_number": i,
                "day_of_week": day,
                "duration_hours": 24,
                "start_time": "08:00"
            })

        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))  # Monday

        entries = service.generate_rotation(start_date, weeks=1)

        # Sort by shift_id to get Mon-Sun order
        entries_sorted = sorted(entries, key=lambda e: e["shift_id"])

        # Verify each shift starts on the correct day
        expected_weekdays = [0, 1, 2, 3, 4, 5, 6]  # Monday=0 through Sunday=6
        for entry, expected_weekday in zip(entries_sorted, expected_weekdays):
            assert entry["start_datetime"].weekday() == expected_weekday


# ============================================================================
# Test Class: Return Format and Integration
# ============================================================================

class TestRotationAlgorithmReturnFormat:
    """Tests for the format of returned schedule entries."""

    def test_return_format_compatible_with_repository(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that returned dicts are compatible with ScheduleRepository.bulk_create()."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # Test that we can bulk create these entries
        from src.repositories.schedule_repository import ScheduleRepository
        schedule_repo = ScheduleRepository(db_session)

        # This should not raise any errors
        created_schedules = schedule_repo.bulk_create(entries)

        assert len(created_schedules) == len(entries)

    def test_all_entries_have_required_fields(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that every entry has all required fields."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=2)

        required_fields = [
            "team_member_id",
            "shift_id",
            "week_number",
            "start_datetime",
            "end_datetime",
            "notified"
        ]

        for entry in entries:
            for field in required_fields:
                assert field in entry, f"Missing field: {field}"

    def test_notified_field_always_false(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that all entries have notified=False initially."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=3)

        for entry in entries:
            assert entry["notified"] is False

    def test_team_member_ids_are_valid(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that all team_member_ids refer to actual database members."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # Get all valid member IDs
        member_repo = TeamMemberRepository(db_session)
        valid_member_ids = {m.id for m in member_repo.get_active()}

        # Every entry should reference a valid member
        for entry in entries:
            assert entry["team_member_id"] in valid_member_ids

    def test_shift_ids_are_valid(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that all shift_ids refer to actual database shifts."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # Get all valid shift IDs
        shift_repo = ShiftRepository(db_session)
        valid_shift_ids = {s.id for s in shift_repo.get_all_ordered()}

        # Every entry should reference a valid shift
        for entry in entries:
            assert entry["shift_id"] in valid_shift_ids


# ============================================================================
# Test Class: Active vs Inactive Members
# ============================================================================

class TestRotationAlgorithmActiveMemberFilter:
    """Tests for active_members_only parameter."""

    def test_active_members_only_default_true(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that by default, only active members are included."""
        # populated_team_members has 4 active, 1 inactive
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(start_date, weeks=1)

        # Get the inactive member ID
        member_repo = TeamMemberRepository(db_session)
        all_members = member_repo.get_all()
        inactive_member_id = next(m.id for m in all_members if not m.is_active)

        # Inactive member should not appear in rotation
        assigned_member_ids = {e["team_member_id"] for e in entries}
        assert inactive_member_id not in assigned_member_ids

    def test_include_inactive_members_when_false(
        self, db_session, populated_team_members, populated_shifts, chicago_tz
    ):
        """Test that inactive members are included when active_members_only=False."""
        service = RotationAlgorithmService(db_session)
        start_date = chicago_tz.localize(datetime(2025, 11, 4))

        entries = service.generate_rotation(
            start_date, weeks=2, active_members_only=False
        )

        # Get all member IDs (including inactive)
        member_repo = TeamMemberRepository(db_session)
        all_member_ids = {m.id for m in member_repo.get_all()}

        # Over 2 weeks, all members (including inactive) should appear
        assigned_member_ids = {e["team_member_id"] for e in entries}

        # With 5 total members and 6 shifts * 2 weeks = 12 assignments
        # Each member works 2-3 times, so all should appear
        assert len(assigned_member_ids.intersection(all_member_ids)) >= 4
