"""
Shift Service Layer.

This module provides business logic for shift configuration management.
It coordinates between the API layer and repository layer, handling validation,
business rules, and shift-related operations.

Key responsibilities:
- CRUD operations for shift configurations
- Shift number uniqueness validation
- Weekend shift identification
- Duration validation (24h or 48h)
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.shift import Shift
from src.repositories.shift_repository import ShiftRepository


class ShiftServiceError(Exception):
    """Base exception for shift service errors."""


class DuplicateShiftNumberError(ShiftServiceError):
    """Raised when attempting to create shift with duplicate shift number."""


class ShiftNotFoundError(ShiftServiceError):
    """Raised when shift is not found."""


class InvalidShiftDataError(ShiftServiceError):
    """Raised when shift data is invalid."""


class ShiftService:
    """
    Service for shift configuration business logic.

    This service encapsulates all business logic related to shift management,
    including CRUD operations, validation, and coordination with schedule generation.

    Attributes:
        db: SQLAlchemy database session
        repository: ShiftRepository instance for data access
    """

    # Valid shift durations in hours
    VALID_DURATIONS = [24, 48]

    # Valid days of week (single days + all consecutive 2-day pairs for 48h shifts)
    VALID_DAY_NAMES = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "Monday-Tuesday", "Tuesday-Wednesday", "Wednesday-Thursday",
        "Thursday-Friday", "Friday-Saturday", "Saturday-Sunday", "Sunday-Monday",
    ]

    # Weekend shift numbers (Saturday=5, Sunday=6 per PRD)
    WEEKEND_SHIFT_NUMBERS = [5, 6]

    def __init__(self, db: Session):
        """
        Initialize the shift service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.repository = ShiftRepository(db)

    def create(self, shift_data: Dict[str, Any]) -> Shift:
        """
        Create a new shift configuration.

        Validates shift data before creation.

        Args:
            shift_data: Dictionary containing shift data
                - shift_number: Unique shift number (1-7)
                - day_of_week: Day of week (0=Monday, 6=Sunday)
                - duration_hours: Duration in hours (24 or 48)
                - start_time: Optional start time (HH:MM:SS)

        Returns:
            Created Shift instance

        Raises:
            InvalidShiftDataError: If shift data is invalid
            DuplicateShiftNumberError: If shift number already exists
            ShiftServiceError: For other creation errors
        """
        # Validate shift data
        self._validate_shift_data(shift_data)

        shift_number = shift_data.get("shift_number")

        # Check for duplicate shift number
        if self.repository.shift_number_exists(shift_number):
            raise DuplicateShiftNumberError(
                f"Shift number already exists: {shift_number}"
            )

        try:
            shift = self.repository.create(shift_data)
            return shift

        except IntegrityError as e:
            raise DuplicateShiftNumberError(
                f"Shift number already exists: {shift_number}"
            ) from e
        except Exception as e:
            raise ShiftServiceError(
                f"Failed to create shift: {str(e)}"
            ) from e

    def get_by_id(self, shift_id: int) -> Shift:
        """
        Get shift by ID.

        Args:
            shift_id: ID of the shift

        Returns:
            Shift instance

        Raises:
            ShiftNotFoundError: If shift not found
        """
        shift = self.repository.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift not found: {shift_id}")
        return shift

    def get_by_shift_number(self, shift_number: int) -> Optional[Shift]:
        """
        Get shift by shift number.

        Args:
            shift_number: Shift number to find

        Returns:
            Shift instance if found, None otherwise
        """
        return self.repository.get_by_shift_number(shift_number)

    def get_all(self, ordered: bool = True) -> List[Shift]:
        """
        Get all shift configurations.

        Args:
            ordered: If True, return shifts ordered by shift_number

        Returns:
            List of Shift instances
        """
        if ordered:
            return self.repository.get_all_ordered()
        return self.repository.get_all()

    def get_weekend_shifts(self) -> List[Shift]:
        """
        Get all weekend shift configurations.

        Returns:
            List of weekend Shift instances (shift numbers 5 and 6)
        """
        return self.repository.get_weekend_shifts()

    def get_by_duration(self, duration_hours: int) -> List[Shift]:
        """
        Get shifts by duration.

        Args:
            duration_hours: Duration in hours (24 or 48)

        Returns:
            List of Shift instances with specified duration

        Raises:
            InvalidShiftDataError: If duration is invalid
        """
        if duration_hours not in self.VALID_DURATIONS:
            raise InvalidShiftDataError(
                f"Invalid duration. Must be one of {self.VALID_DURATIONS}"
            )

        return self.repository.get_by_duration(duration_hours)

    def get_by_day_of_week(self, day_of_week: str) -> List[Shift]:
        """
        Get shifts by day of week.

        Args:
            day_of_week: Day of week name (e.g., "Monday", "Tuesday-Wednesday")

        Returns:
            List of Shift instances for specified day

        Raises:
            InvalidShiftDataError: If day_of_week is invalid
        """
        if day_of_week not in self.VALID_DAY_NAMES:
            raise InvalidShiftDataError(
                f"Invalid day_of_week. Must be one of {self.VALID_DAY_NAMES}"
            )

        return self.repository.get_by_day_of_week(day_of_week)

    def update(
        self,
        shift_id: int,
        update_data: Dict[str, Any]
    ) -> Shift:
        """
        Update shift configuration.

        Validates update data before applying changes.

        Args:
            shift_id: ID of the shift to update
            update_data: Dictionary of fields to update

        Returns:
            Updated Shift instance

        Raises:
            ShiftNotFoundError: If shift not found
            InvalidShiftDataError: If update data is invalid
            DuplicateShiftNumberError: If new shift number already exists
        """
        # Check shift exists
        _ = self.get_by_id(shift_id)

        # Validate update data
        self._validate_shift_data(update_data, partial=True)

        # Check for duplicate shift number if being updated
        if "shift_number" in update_data:
            new_shift_number = update_data["shift_number"]
            if self.repository.shift_number_exists(
                new_shift_number,
                exclude_id=shift_id
            ):
                raise DuplicateShiftNumberError(
                    f"Shift number already exists: {new_shift_number}"
                )

        try:
            updated_shift = self.repository.update(shift_id, update_data)
            return updated_shift

        except IntegrityError as e:
            raise DuplicateShiftNumberError(
                f"Shift number already exists: {update_data.get('shift_number')}"
            ) from e
        except Exception as e:
            raise ShiftServiceError(
                f"Failed to update shift: {str(e)}"
            ) from e

    def delete(self, shift_id: int) -> bool:
        """
        Delete a shift configuration.

        Note: This will cascade delete all associated schedule entries.

        Args:
            shift_id: ID of the shift to delete

        Returns:
            True if deleted successfully

        Raises:
            ShiftNotFoundError: If shift not found
        """
        shift = self.get_by_id(shift_id)
        return self.repository.delete(shift_id)

    def shift_number_exists(
        self,
        shift_number: int,
        exclude_id: Optional[int] = None
    ) -> bool:
        """
        Check if shift number is already in use.

        Args:
            shift_number: Shift number to check
            exclude_id: Optional shift ID to exclude from check (for updates)

        Returns:
            True if shift number exists, False otherwise
        """
        return self.repository.shift_number_exists(shift_number, exclude_id=exclude_id)

    def get_max_shift_number(self) -> Optional[int]:
        """
        Get the maximum shift number currently configured.

        Useful for determining the next shift number when creating new shifts.

        Returns:
            Maximum shift number or None if no shifts exist
        """
        return self.repository.get_max_shift_number()

    def is_weekend_shift(self, shift_number: int) -> bool:
        """
        Check if a shift number is a weekend shift.

        Per PRD: Saturday = Shift 5, Sunday = Shift 6

        Args:
            shift_number: Shift number to check

        Returns:
            True if weekend shift, False otherwise
        """
        return shift_number in self.WEEKEND_SHIFT_NUMBERS

    def get_count(self) -> int:
        """
        Get total count of shift configurations.

        Returns:
            Count of shifts
        """
        return self.repository.count()

    def _validate_shift_data(
        self,
        shift_data: Dict[str, Any],
        partial: bool = False
    ) -> None:
        """
        Validate shift data.

        Args:
            shift_data: Dictionary of shift data to validate
            partial: If True, allows partial data (for updates)

        Raises:
            InvalidShiftDataError: If data is invalid
        """
        # Required fields for creation
        if not partial:
            required_fields = ["shift_number", "day_of_week", "duration_hours"]
            missing_fields = [f for f in required_fields if f not in shift_data]
            if missing_fields:
                raise InvalidShiftDataError(
                    f"Missing required fields: {', '.join(missing_fields)}"
                )

        # Validate shift_number
        if "shift_number" in shift_data:
            shift_number = shift_data["shift_number"]
            if not isinstance(shift_number, int) or shift_number < 1:
                raise InvalidShiftDataError(
                    "shift_number must be a positive integer"
                )

        # Validate day_of_week
        if "day_of_week" in shift_data:
            day_of_week = shift_data["day_of_week"]
            if not isinstance(day_of_week, str):
                raise InvalidShiftDataError(
                    f"day_of_week must be a string day name, got: {type(day_of_week)}"
                )
            if day_of_week not in self.VALID_DAY_NAMES:
                raise InvalidShiftDataError(
                    f"day_of_week must be one of {self.VALID_DAY_NAMES}, got: {day_of_week}"
                )

        # Validate duration_hours
        if "duration_hours" in shift_data:
            duration = shift_data["duration_hours"]
            if duration not in self.VALID_DURATIONS:
                raise InvalidShiftDataError(
                    f"duration_hours must be one of {self.VALID_DURATIONS}, got: {duration}"
                )

        # Validate start_time format if provided
        if "start_time" in shift_data and shift_data["start_time"] is not None:
            start_time = shift_data["start_time"]
            if not isinstance(start_time, str):
                raise InvalidShiftDataError(
                    "start_time must be a string in HH:MM:SS format"
                )
            # Basic format validation
            parts = start_time.split(":")
            if len(parts) != 3:
                raise InvalidShiftDataError(
                    "start_time must be in HH:MM:SS format"
                )
            try:
                hours, minutes, seconds = map(int, parts)
                if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                    raise InvalidShiftDataError(
                        "start_time has invalid hour, minute, or second values"
                    )
            except ValueError:
                raise InvalidShiftDataError(
                    "start_time must contain valid integers in HH:MM:SS format"
                )
