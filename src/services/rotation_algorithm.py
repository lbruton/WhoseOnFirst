"""
Rotation Algorithm Service

This module implements the circular rotation algorithm for assigning team members
to on-call shifts in a fair, predictable manner.

The algorithm works by:
1. Ordering team members consistently (by ID)
2. Ordering shifts by shift_number
3. Each week, rotating assignments forward by one position
4. Handling any team size (including cases where members < shifts or members > shifts)

Example with 7 members and 6 shifts:
- Week 1: Members 0-5 work shifts 1-6, member 6 is off
- Week 2: Members 1-6 work shifts 1-6, member 0 is off
- Week 3: Members 2-6,0 work shifts 1-6, member 1 is off

The double-shift (e.g., Tuesday-Wednesday 48h) naturally spreads across weeks,
ensuring no special "weekend fairness" logic is needed.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from pytz import timezone

from src.repositories.team_member_repository import TeamMemberRepository
from src.repositories.shift_repository import ShiftRepository


class RotationAlgorithmError(Exception):
    """Base exception for rotation algorithm errors."""


class InsufficientMembersError(RotationAlgorithmError):
    """Raised when there are not enough active team members for rotation."""


class NoShiftsConfiguredError(RotationAlgorithmError):
    """Raised when no shifts are configured in the system."""


class InvalidWeekCountError(RotationAlgorithmError):
    """Raised when the week count is invalid (< 1)."""


class RotationAlgorithmService:
    """
    Service for generating fair on-call rotation schedules.

    This service implements a simple circular rotation algorithm where team members
    rotate through shifts in a predictable order each week. The rotation is fair
    because everyone moves forward by one position weekly, ensuring equal distribution
    of shifts over time.
    """

    # Mapping of day names to weekday offsets (Monday = 0)
    DAY_OFFSET_MAP = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6
    }

    def __init__(self, db: Session):
        """
        Initialize the rotation algorithm service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.team_member_repo = TeamMemberRepository(db)
        self.shift_repo = ShiftRepository(db)
        self.chicago_tz = timezone('America/Chicago')

    def generate_rotation(
        self,
        start_date: datetime,
        weeks: int = 4,
        active_members_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate a fair rotation schedule for the specified number of weeks.

        This method creates schedule entries by rotating team members through
        shifts in a circular pattern. Each week, every member moves to the next
        shift in sequence (or is off duty if there are more members than shifts).

        The rotation is anchored at start_date (WOF-9): the first member in
        rotation order takes the first shift on or after that date, and no
        entries are created for earlier days of the week. A mid-week start
        produces a partial week 0 plus one extra trailing week, so coverage
        from start_date is always at least `weeks` full weeks.

        Args:
            start_date: Start date for the rotation (timezone-aware).
                       The first generated shift falls on or after this date.
            weeks: Number of weeks to generate (minimum 1, default 4)
            active_members_only: If True, only include active team members

        Returns:
            List of schedule entry dictionaries ready for ScheduleRepository.bulk_create().
            Each dict contains: team_member_id, shift_id, week_number,
            start_datetime, end_datetime, notified (False).

        Raises:
            InsufficientMembersError: If there are no active members available
            NoShiftsConfiguredError: If no shifts are configured
            InvalidWeekCountError: If weeks < 1
            ValueError: If start_date is not timezone-aware

        Example:
            >>> service = RotationAlgorithmService(db)
            >>> monday = chicago_tz.localize(datetime(2025, 11, 3))
            >>> len(service.generate_rotation(monday, weeks=4))  # 6 shifts/week
            24
            >>> tuesday = chicago_tz.localize(datetime(2025, 11, 4))
            >>> len(service.generate_rotation(tuesday, weeks=4))  # 5 partial + 24
            29
        """
        # Validate inputs
        self._validate_inputs(start_date, weeks)

        # Get team members (sorted by ID for consistency)
        members = self._get_team_members(active_members_only)
        if not members:
            raise InsufficientMembersError(
                "No active team members available for rotation"
            )

        # Order shifts by chronological day of week, NOT by shift_number.
        # shift_number is a free-form user label that can drift out of day order
        # when shifts are removed and re-added in the admin UI (WOF-8) — a Tuesday
        # shift can end up numbered after Sunday. Each shift's calendar date is
        # derived from day_of_week, so day order is the correct rotation order;
        # ordering by shift_number would silently assign members to the wrong days.
        shifts = self._order_shifts_by_day(self.shift_repo.get_all_ordered())
        if not shifts:
            raise NoShiftsConfiguredError(
                "No shifts configured. Please create shifts before generating rotation."
            )

        # Normalize start_date to Monday of that week
        monday = self._get_week_start(start_date)

        # Anchor at start_date (WOF-9): week 0 only covers shifts on/after the
        # start day, and a mid-week start adds one trailing week so coverage
        # from start_date is never less than the requested number of weeks.
        start_day_offset = start_date.weekday()
        extra_weeks = 1 if start_day_offset > 0 else 0

        # Generate schedule entries
        schedule_entries = []
        assignment_count = 0

        for week in range(weeks + extra_weeks):
            # Assign members to shifts for this week
            for shift in shifts:
                # Week 0 skips shifts whose first day precedes the start date.
                # A multi-day shift straddling the start (e.g. starting on the
                # Wednesday of a Tuesday-Wednesday 48h shift) is skipped whole,
                # never truncated — the caller surfaces that as a warning.
                first_day_offset = self.DAY_OFFSET_MAP[shift.day_of_week.split('-')[0]]
                if week == 0 and first_day_offset < start_day_offset:
                    continue

                # Circular rotation over emitted entries: the first member in
                # rotation order takes the first generated shift (the start
                # date), and the cycle continues uninterrupted across weeks
                # regardless of team size vs. shift count.
                member = members[assignment_count % len(members)]
                assignment_count += 1

                # Calculate shift start datetime
                shift_start_datetime = self._calculate_shift_start(
                    monday, week, shift
                )

                # Calculate shift end datetime
                shift_end_datetime = shift_start_datetime + timedelta(
                    hours=shift.duration_hours
                )

                # Get ISO week number
                week_number = shift_start_datetime.isocalendar()[1]

                # Create schedule entry
                entry = {
                    "team_member_id": member.id,
                    "shift_id": shift.id,
                    "week_number": week_number,
                    "start_datetime": shift_start_datetime,
                    "end_datetime": shift_end_datetime,
                    "notified": False
                }

                schedule_entries.append(entry)

        return schedule_entries

    def get_rotation_horizon_end(self, start_date: datetime, weeks: int) -> datetime:
        """
        Return the exclusive end of the period generate_rotation will cover.

        A mid-week start adds one trailing week to the rotation (so coverage
        from start_date is at least `weeks` full weeks), which means the
        covered period can extend past start_date + weeks. Callers that check
        for existing schedules in the generation window must use this horizon,
        not a naive start_date + weeks, or entries in the trailing week escape
        the duplicate check.

        Args:
            start_date: Rotation start date (timezone-aware)
            weeks: Requested number of weeks

        Returns:
            Timezone-aware datetime of the Monday following the last
            generated week (exclusive end of the covered period)
        """
        extra_weeks = 1 if start_date.weekday() > 0 else 0
        return self._get_week_start(start_date) + timedelta(weeks=weeks + extra_weeks)

    def _order_shifts_by_day(self, shifts: List) -> List:
        """
        Order shifts by chronological day of week (Monday first).

        shift_number is a user-facing label and is NOT guaranteed to follow day
        order: a shift removed and re-added in the admin UI gets the next free
        number, which can place a Tuesday shift after Sunday (WOF-8). The rotation
        must walk shifts in true weekday order so members map to the correct days.
        Double shifts like "Tuesday-Wednesday" sort by their first day. Python's
        sort is stable, so shifts sharing a first day keep their incoming order.

        Args:
            shifts: List of Shift objects

        Returns:
            New list sorted by weekday offset (Monday=0 ... Sunday=6)
        """
        return sorted(
            shifts,
            key=lambda s: self.DAY_OFFSET_MAP[s.day_of_week.split('-')[0]]
        )

    def _validate_inputs(self, start_date: datetime, weeks: int) -> None:
        """
        Validate input parameters.

        Args:
            start_date: The start date to validate
            weeks: The number of weeks to validate

        Raises:
            ValueError: If start_date is not timezone-aware
            InvalidWeekCountError: If weeks < 1
        """
        if start_date.tzinfo is None:
            raise ValueError(
                "start_date must be timezone-aware. "
                "Use chicago_tz.localize() or start_date.replace(tzinfo=...)"
            )

        if weeks < 1:
            raise InvalidWeekCountError(
                f"weeks must be >= 1, got {weeks}"
            )

    def _get_team_members(self, active_only: bool) -> List:
        """
        Get team members sorted by rotation_order for consistent rotation order.

        Uses rotation_order if set, falls back to ID for members without rotation_order.
        This ensures consistent, predictable rotation regardless of when members were added.

        Args:
            active_only: If True, only return active members

        Returns:
            List of TeamMember objects sorted by rotation_order (then ID as fallback)
        """
        # Use the new repository method that handles ordering correctly
        return self.team_member_repo.get_ordered_for_rotation(active_only=active_only)

    def _get_week_start(self, date: datetime) -> datetime:
        """
        Normalize a date to the Monday of that week at midnight.

        Args:
            date: Any datetime in the target week

        Returns:
            Datetime representing Monday 00:00 of that week (timezone-aware)

        Example:
            >>> # Wednesday, Nov 6, 2025
            >>> wed = chicago_tz.localize(datetime(2025, 11, 6, 15, 30))
            >>> monday = self._get_week_start(wed)
            >>> monday  # Monday, Nov 4, 2025 00:00
        """
        # Monday = 0, Sunday = 6
        days_since_monday = date.weekday()

        # Go back to Monday, preserving timezone
        monday = date - timedelta(days=days_since_monday)

        # Set to midnight using replace() to keep timezone
        monday_midnight = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        return monday_midnight

    def _calculate_shift_start(
        self,
        base_monday: datetime,
        week: int,
        shift
    ) -> datetime:
        """
        Calculate the start datetime for a shift.

        Args:
            base_monday: The Monday of the first week (at midnight)
            week: Week offset (0 = first week, 1 = second week, etc.)
            shift: Shift object with day_of_week and duration_hours

        Returns:
            Timezone-aware datetime when the shift starts (8:00 AM Chicago time)

        Note:
            Shifts start at 8:00 AM per PRD requirements. Double shifts like
            "Tuesday-Wednesday" use the first day (Tuesday) as the start day.
        """
        # Handle double shifts like "Tuesday-Wednesday" -> use "Tuesday"
        day_name = shift.day_of_week.split('-')[0]

        # Get the day offset (Monday = 0, Tuesday = 1, etc.)
        day_offset = self.DAY_OFFSET_MAP[day_name]

        # Calculate the actual datetime: base Monday + week/day offsets
        # Then set to 8:00 AM using replace()
        shift_start = base_monday + timedelta(days=(week * 7) + day_offset)
        shift_start = shift_start.replace(hour=8, minute=0, second=0, microsecond=0)

        return shift_start
