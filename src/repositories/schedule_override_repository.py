"""
Schedule override repository for database operations.

Handles all database operations related to manual shift overrides,
including creating overrides, cancelling overrides, and audit queries.
"""

from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func
from pytz import timezone

from .base_repository import BaseRepository
from ..models.schedule_override import ScheduleOverride
from ..models.schedule import Schedule


class ScheduleOverrideRepository(BaseRepository[ScheduleOverride]):
    """
    Repository for schedule override database operations.

    Extends BaseRepository with override-specific queries:
    - Get active overrides
    - Get override for specific schedule
    - Get by date range
    - Cancel overrides
    - Pagination support

    Attributes:
        db: SQLAlchemy database session
    """

    def __init__(self, db: Session):
        """
        Initialize ScheduleOverrideRepository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(db, ScheduleOverride)

    def get_display_overrides(self) -> List[ScheduleOverride]:
        """
        Get overrides for calendar display purposes.

        Returns both active and completed overrides (excludes cancelled).
        Used by dashboard to show historical and current override coverage.
        Ordered by creation date (most recent first).

        Returns:
            List of ScheduleOverride instances for display

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.status.in_(['active', 'completed']))
                .order_by(self.model.created_at.desc())
                .all()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting display overrides: {str(e)}")

    def get_active_overrides(self) -> List[ScheduleOverride]:
        """
        Get all currently active overrides.

        Returns:
            List of ScheduleOverride instances with status='active'

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.status == 'active')
                .all()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting active overrides: {str(e)}")

    def get_override_for_schedule(self, schedule_id: int) -> Optional[ScheduleOverride]:
        """
        Check if active override exists for a specific schedule.

        Used to determine if a schedule assignment has been overridden
        when sending notifications.

        Args:
            schedule_id: Schedule ID to check for overrides

        Returns:
            Active ScheduleOverride instance if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(
                    self.model.schedule_id == schedule_id,
                    self.model.status == 'active'
                )
                .first()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting override for schedule: {str(e)}")

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[str] = None
    ) -> List[ScheduleOverride]:
        """
        Get overrides within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            status: Optional status filter (active, cancelled, completed)

        Returns:
            List of ScheduleOverride instances in the date range

        Raises:
            Exception: If database operation fails
        """
        try:
            query = self.db.query(self.model).filter(
                self.model.created_at >= start_date,
                self.model.created_at <= end_date
            )

            if status:
                query = query.filter(self.model.status == status)

            return query.order_by(self.model.created_at.desc()).all()

        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting overrides by date range: {str(e)}")

    def cancel_override(self, override_id: int) -> Optional[ScheduleOverride]:
        """
        Cancel an override by setting status to 'cancelled'.

        Soft delete: Sets status='cancelled' and records cancellation timestamp.
        Does not physically delete the override from the database.

        Args:
            override_id: ID of override to cancel

        Returns:
            Updated ScheduleOverride instance if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        try:
            override = self.get_by_id(override_id)
            if override:
                override.status = 'cancelled'
                override.cancelled_at = func.now()
                self.db.commit()
                self.db.refresh(override)
            return override

        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error cancelling override: {str(e)}")

    def get_paginated(
        self,
        page: int = 1,
        per_page: int = 25,
        status: Optional[str] = None,
        include_schedule: bool = True
    ) -> Tuple[List[ScheduleOverride], int]:
        """
        Get paginated overrides with total count.

        Useful for audit trail table display with pagination controls.

        Args:
            page: Page number (1-indexed)
            per_page: Number of results per page (default 25)
            status: Optional status filter (active, cancelled, completed)
            include_schedule: Whether to eagerly load schedule relationship

        Returns:
            Tuple of (list of ScheduleOverride instances, total count)

        Raises:
            Exception: If database operation fails
        """
        try:
            query = self.db.query(self.model)

            if status:
                query = query.filter(self.model.status == status)

            if include_schedule:
                query = query.options(joinedload(self.model.schedule))

            total = query.count()
            offset = (page - 1) * per_page

            overrides = (
                query
                .order_by(self.model.created_at.desc())
                .limit(per_page)
                .offset(offset)
                .all()
            )

            return overrides, total

        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting paginated overrides: {str(e)}")

    def count_all(self) -> int:
        """
        Get total count of all overrides for pagination.

        Returns:
            Total number of override records

        Raises:
            Exception: If database operation fails
        """
        try:
            return self.db.query(self.model).count()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error counting overrides: {str(e)}")

    def get_recent_overrides(
        self,
        limit: int = 25,
        offset: int = 0,
        include_schedule: bool = True
    ) -> List[ScheduleOverride]:
        """
        Get most recent overrides with pagination support.

        Useful for dashboard and audit views.

        Args:
            limit: Maximum number of overrides to return (default 25)
            offset: Number of records to skip (default 0)
            include_schedule: Whether to eagerly load schedule relationship

        Returns:
            List of recent ScheduleOverride instances ordered by created_at DESC

        Raises:
            Exception: If database operation fails
        """
        try:
            query = self.db.query(self.model)

            if include_schedule:
                query = query.options(joinedload(self.model.schedule))

            return (
                query
                .order_by(self.model.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting recent overrides: {str(e)}")

    def complete_past_overrides(self) -> int:
        """
        Mark active overrides as 'completed' if their schedule has ended.

        Finds all overrides where:
        - status = 'active'
        - schedule.end_datetime < current time (Chicago timezone)

        Updates them to:
        - status = 'completed'
        - completed_at = current timestamp

        This should be called daily after notifications (e.g., 8:05 AM CST)
        to transition overrides that have served their purpose.

        Returns:
            Number of overrides marked as completed

        Raises:
            Exception: If database operation fails
        """
        try:
            chicago_tz = timezone('America/Chicago')
            now = datetime.now(chicago_tz)

            # Find active overrides with past schedule end times
            # Need to join with Schedule to check end_datetime
            past_overrides = (
                self.db.query(self.model)
                .join(Schedule, self.model.schedule_id == Schedule.id)
                .filter(
                    self.model.status == 'active',
                    Schedule.end_datetime < now
                )
                .all()
            )

            completed_count = 0
            for override in past_overrides:
                override.status = 'completed'
                override.completed_at = func.now()
                completed_count += 1

            if completed_count > 0:
                self.db.commit()

            return completed_count

        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error completing past overrides: {str(e)}")
