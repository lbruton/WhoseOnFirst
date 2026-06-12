"""
Schedule Service

This module provides business logic for schedule generation and management,
coordinating between the rotation algorithm and schedule persistence.

The ScheduleService is responsible for:
- Generating new schedules using RotationAlgorithmService
- Persisting schedules via ScheduleRepository
- Querying existing schedules (current week, upcoming, date ranges)
- Regenerating schedules when team composition changes
- Validating schedule operations
"""

from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from pytz import timezone

from src.repositories.schedule_repository import ScheduleRepository
from src.services.rotation_algorithm import RotationAlgorithmService
from src.models.schedule import Schedule


# Hour (America/Chicago) when the daily notification job fires. Owned here so
# the scheduler's CronTrigger and the generation-warning check can never drift
# apart (WOF-9): if generation starts "today" at or after this hour, today's
# on-call has already been skipped by the daily job.
DAILY_NOTIFICATION_HOUR = 8


class ScheduleServiceError(Exception):
    """Base exception for schedule service errors."""


class ScheduleAlreadyExistsError(ScheduleServiceError):
    """Raised when trying to generate schedule for dates that already exist."""


class InvalidDateRangeError(ScheduleServiceError):
    """Raised when date range is invalid (end < start)."""


class ScheduleService:
    """
    Service for schedule generation and management.

    This service orchestrates schedule operations, coordinating between
    the rotation algorithm and database persistence. It ensures schedules
    are generated correctly and provides query methods for retrieving schedules.
    """

    def __init__(self, db: Session):
        """
        Initialize the schedule service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.schedule_repo = ScheduleRepository(db)
        self.rotation_service = RotationAlgorithmService(db)
        self.chicago_tz = timezone('America/Chicago')

    def generate_schedule(
        self,
        start_date: datetime,
        weeks: int = 4,
        force: bool = False
    ) -> List[Schedule]:
        """
        Generate a new schedule for the specified period.

        This method coordinates rotation generation and persistence. It checks
        for existing schedules to prevent duplication (unless force=True).

        Args:
            start_date: Start date for schedule (timezone-aware)
            weeks: Number of weeks to generate (default 4, minimum 1)
            force: If True, delete existing schedules and regenerate

        Returns:
            List of created Schedule objects

        Raises:
            ScheduleAlreadyExistsError: If schedules exist for this period and force=False
            InsufficientMembersError: If no active team members (from rotation service)
            NoShiftsConfiguredError: If no shifts configured (from rotation service)
            InvalidWeekCountError: If weeks < 1 (from rotation service)
            ValueError: If start_date is not timezone-aware

        Example:
            >>> service = ScheduleService(db)
            >>> start = chicago_tz.localize(datetime(2025, 11, 4))
            >>> schedules = service.generate_schedule(start, weeks=4)
            >>> len(schedules)  # 6 shifts * 4 weeks = 24
            24
        """
        # Validate start_date
        if start_date.tzinfo is None:
            raise ValueError(
                "start_date must be timezone-aware. "
                "Use chicago_tz.localize() or start_date.replace(tzinfo=...)"
            )

        # Calculate end date for the period. The rotation can extend one
        # trailing week past start_date + weeks on a mid-week start (WOF-9),
        # so the duplicate check must cover the full generation horizon.
        end_date = self.rotation_service.get_rotation_horizon_end(start_date, weeks)

        # Check if schedules already exist
        existing = self.schedule_repo.get_by_date_range(start_date, end_date)

        if existing and not force:
            raise ScheduleAlreadyExistsError(
                f"Schedules already exist for period {start_date.date()} to {end_date.date()}. "
                f"Use force=True to regenerate."
            )

        # If force=True and schedules exist, delete them
        if existing and force:
            self.schedule_repo.delete_future_schedules(start_date)

        # Generate rotation entries using rotation algorithm
        schedule_entries = self.rotation_service.generate_rotation(
            start_date,
            weeks,
            active_members_only=True
        )

        # Persist to database
        schedules = self.schedule_repo.bulk_create(schedule_entries)

        return schedules

    def get_generation_warnings(
        self,
        start_date: datetime,
        schedules: List[Schedule]
    ) -> List[str]:
        """
        Report non-blocking conditions for a just-generated schedule (WOF-9).

        Two conditions are surfaced so the silent day-shift the user hit in
        production can never recur without explanation:
        1. Missed SMS: the start date is today (America/Chicago) and the
           daily notification job has already run, so today's on-call will
           not receive an SMS unless notifications are triggered manually.
        2. Uncovered start day: no generated shift begins on the start date
           (it fell mid-way through a multi-day shift that was skipped whole
           rather than truncated).

        Args:
            start_date: The start date the schedule was generated with
            schedules: The Schedule objects returned by generate_schedule

        Returns:
            List of human-readable warning strings (empty when nothing applies)
        """
        warnings = []

        now = datetime.now(self.chicago_tz)
        start_local = start_date.astimezone(self.chicago_tz)

        if (start_local.date() == now.date()
                and now.hour >= DAILY_NOTIFICATION_HOUR):
            warnings.append(
                f"Today's {DAILY_NOTIFICATION_HOUR}:00 AM notification has "
                "already run; today's on-call will not receive an SMS unless "
                "notifications are triggered manually."
            )

        if schedules:
            # DB datetimes are naive America/Chicago wall time
            earliest = min(s.start_datetime for s in schedules)
            if earliest.date() > start_local.date():
                warnings.append(
                    f"No shift covers the start date "
                    f"{start_local.date().isoformat()}; the first generated "
                    f"shift begins {earliest.date().isoformat()}."
                )

        return warnings

    def get_current_week_schedule(self) -> List[Schedule]:
        """
        Get the schedule for the current week.

        Returns schedules for the week containing today's date.

        Returns:
            List of Schedule objects for current week (may be empty)

        Example:
            >>> service = ScheduleService(db)
            >>> current_week = service.get_current_week_schedule()
            >>> len(current_week)  # Typically 6 shifts
            6
        """
        return self.schedule_repo.get_current_week()

    def get_upcoming_schedules(self, weeks: int = 4) -> List[Schedule]:
        """
        Get upcoming schedules for the next N weeks.

        Args:
            weeks: Number of weeks to retrieve (default 4)

        Returns:
            List of Schedule objects for upcoming weeks (may be empty)

        Example:
            >>> service = ScheduleService(db)
            >>> upcoming = service.get_upcoming_schedules(weeks=2)
            >>> # Schedules for next 2 weeks
        """
        return self.schedule_repo.get_upcoming_weeks(weeks)

    def get_schedule_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Schedule]:
        """
        Get schedules for a specific date range.

        Args:
            start_date: Range start (inclusive, timezone-aware)
            end_date: Range end (inclusive, timezone-aware)

        Returns:
            List of Schedule objects in the date range (may be empty)

        Raises:
            InvalidDateRangeError: If end_date < start_date
            ValueError: If either date is not timezone-aware

        Example:
            >>> service = ScheduleService(db)
            >>> start = chicago_tz.localize(datetime(2025, 11, 4))
            >>> end = chicago_tz.localize(datetime(2025, 11, 18))
            >>> schedules = service.get_schedule_by_date_range(start, end)
        """
        # Validate dates
        if start_date.tzinfo is None or end_date.tzinfo is None:
            raise ValueError("Both start_date and end_date must be timezone-aware")

        if end_date < start_date:
            raise InvalidDateRangeError(
                f"end_date ({end_date.date()}) must be >= start_date ({start_date.date()})"
            )

        return self.schedule_repo.get_by_date_range(start_date, end_date)

    def regenerate_from_date(
        self,
        from_date: datetime,
        weeks: int = 4
    ) -> List[Schedule]:
        """
        Regenerate schedules from a specific date forward.

        This method is used when team composition changes (member added/removed).
        It deletes all future schedules from the specified date and generates
        new schedules based on the current team roster.

        Historical schedules (before from_date) are preserved.

        Args:
            from_date: Date to start regeneration from (timezone-aware)
            weeks: Number of weeks to generate forward (default 4)

        Returns:
            List of newly created Schedule objects

        Raises:
            ValueError: If from_date is not timezone-aware
            InsufficientMembersError: If no active team members
            NoShiftsConfiguredError: If no shifts configured

        Example:
            >>> # Admin adds new team member on Nov 10
            >>> service = ScheduleService(db)
            >>> from_date = chicago_tz.localize(datetime(2025, 11, 10))
            >>> new_schedules = service.regenerate_from_date(from_date)
            >>> # Schedules before Nov 10 are preserved
            >>> # Schedules from Nov 10+ are regenerated with new team member
        """
        # Validate from_date
        if from_date.tzinfo is None:
            raise ValueError(
                "from_date must be timezone-aware. "
                "Use chicago_tz.localize() or from_date.replace(tzinfo=...)"
            )

        # Delete future schedules from this date forward
        _ = self.schedule_repo.delete_future_schedules(from_date)

        # Generate new schedules (force=True since we just deleted)
        schedules = self.generate_schedule(from_date, weeks, force=True)

        return schedules

    def get_schedule_by_member(
        self,
        team_member_id: int,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Schedule]:
        """
        Get all schedules for a specific team member.

        Args:
            team_member_id: ID of the team member
            start_date: Optional start date filter (timezone-aware)
            end_date: Optional end date filter (timezone-aware)

        Returns:
            List of Schedule objects for the team member (may be empty)

        Example:
            >>> service = ScheduleService(db)
            >>> member_schedules = service.get_schedule_by_member(member_id=1)
            >>> # All schedules for team member #1
        """
        return self.schedule_repo.get_by_team_member(
            team_member_id,
            start_date,
            end_date
        )

    def get_next_assignment(self, team_member_id: int) -> Schedule:
        """
        Get the next scheduled assignment for a team member.

        Args:
            team_member_id: ID of the team member

        Returns:
            Next Schedule object for this member, or None if no future assignments

        Example:
            >>> service = ScheduleService(db)
            >>> next_shift = service.get_next_assignment(member_id=1)
            >>> if next_shift:
            >>>     print(f"Next shift: {next_shift.start_datetime}")
        """
        return self.schedule_repo.get_next_assignment_for_member(team_member_id)

    def get_pending_notifications(self, target_date: datetime = None, force: bool = False) -> List[Schedule]:
        """
        Get schedules that need notifications sent.

        Args:
            target_date: Optional target date (default: today)
            force: If True, include already-notified schedules (for testing)

        Returns:
            List of Schedule objects that haven't been notified yet
            for the target date (or all schedules for date if force=True)

        Example:
            >>> service = ScheduleService(db)
            >>> pending = service.get_pending_notifications()
            >>> # Schedules starting today that haven't been notified
            >>> pending_force = service.get_pending_notifications(force=True)
            >>> # All schedules starting today (for testing)
        """
        # Convert datetime to date if provided
        if target_date is not None:
            target_date = target_date.date()

        return self.schedule_repo.get_pending_notifications(target_date, force=force)

    def mark_as_notified(self, schedule_id: int) -> Schedule:
        """
        Mark a schedule entry as notified.

        Args:
            schedule_id: ID of the schedule entry

        Returns:
            Updated Schedule object

        Example:
            >>> service = ScheduleService(db)
            >>> updated = service.mark_as_notified(schedule_id=1)
            >>> updated.notified
            True
        """
        return self.schedule_repo.mark_as_notified(schedule_id)
