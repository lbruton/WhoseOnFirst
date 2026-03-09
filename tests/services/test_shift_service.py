"""
Tests for ShiftService.

This module contains comprehensive tests for the shift service layer,
covering CRUD operations, validation, error handling, and business logic.
"""

import pytest
from sqlalchemy.orm import Session

from src.services import (
    ShiftService,
    DuplicateShiftNumberError,
    ShiftNotFoundError,
    InvalidShiftDataError,
)
from src.models.shift import Shift


class TestShiftServiceCreate:
    """Tests for creating shifts."""

    def test_create_success(self, db_session: Session, sample_shift_data):
        """Test successful shift creation."""
        service = ShiftService(db_session)

        shift = service.create(sample_shift_data)

        assert shift.id is not None
        assert shift.shift_number == sample_shift_data["shift_number"]
        assert shift.day_of_week == sample_shift_data["day_of_week"]
        assert shift.duration_hours == sample_shift_data["duration_hours"]
        assert shift.created_at is not None

    def test_create_with_start_time(self, db_session: Session, sample_shift_data):
        """Test creating shift with start time."""
        service = ShiftService(db_session)
        sample_shift_data["start_time"] = "08:00:00"

        shift = service.create(sample_shift_data)

        assert shift.start_time == "08:00:00"

    def test_create_duplicate_shift_number_fails(self, db_session: Session, sample_shift_data):
        """Test that creating shift with duplicate number raises error."""
        service = ShiftService(db_session)

        # Create first shift
        service.create(sample_shift_data)

        # Attempt to create duplicate
        duplicate_data = sample_shift_data.copy()
        duplicate_data["day_of_week"] = "Tuesday"  # Different day, same number
        with pytest.raises(DuplicateShiftNumberError) as exc_info:
            service.create(duplicate_data)

        assert "already exists" in str(exc_info.value).lower()

    def test_create_missing_required_fields(self, db_session: Session):
        """Test that missing required fields raises error."""
        service = ShiftService(db_session)

        # Missing shift_number
        with pytest.raises(InvalidShiftDataError) as exc_info:
            service.create({"day_of_week": "Monday", "duration_hours": 24})
        assert "missing required fields" in str(exc_info.value).lower()

        # Missing day_of_week
        with pytest.raises(InvalidShiftDataError):
            service.create({"shift_number": 1, "duration_hours": 24})

        # Missing duration_hours
        with pytest.raises(InvalidShiftDataError):
            service.create({"shift_number": 1, "day_of_week": "Monday"})

    def test_create_invalid_shift_number(self, db_session: Session):
        """Test that invalid shift number raises error."""
        service = ShiftService(db_session)

        # Negative number
        with pytest.raises(InvalidShiftDataError):
            service.create({
                "shift_number": -1,
                "day_of_week": "Monday",
                "duration_hours": 24
            })

        # Zero
        with pytest.raises(InvalidShiftDataError):
            service.create({
                "shift_number": 0,
                "day_of_week": "Monday",
                "duration_hours": 24
            })

    def test_create_invalid_day_of_week(self, db_session: Session):
        """Test that invalid day_of_week raises error."""
        service = ShiftService(db_session)

        invalid_days = ["Funday", "NotADay", "", 123]

        for day in invalid_days:
            with pytest.raises(InvalidShiftDataError):
                service.create({
                    "shift_number": 1,
                    "day_of_week": day,
                    "duration_hours": 24
                })

    def test_create_invalid_duration(self, db_session: Session):
        """Test that invalid duration raises error."""
        service = ShiftService(db_session)

        invalid_durations = [12, 36, 72, 0, -24]

        for duration in invalid_durations:
            with pytest.raises(InvalidShiftDataError):
                service.create({
                    "shift_number": 1,
                    "day_of_week": 0,
                    "duration_hours": duration
                })

    def test_create_invalid_start_time_format(self, db_session: Session):
        """Test that invalid start_time format raises error."""
        service = ShiftService(db_session)

        invalid_times = [
            "8:00",  # Missing seconds
            "08:00",  # Missing seconds
            "25:00:00",  # Invalid hour
            "08:60:00",  # Invalid minute
            "08:00:60",  # Invalid second
            "8am",  # Not 24-hour format
            "not a time",  # Garbage
        ]

        for time in invalid_times:
            with pytest.raises(InvalidShiftDataError):
                service.create({
                    "shift_number": 1,
                    "day_of_week": 0,
                    "duration_hours": 24,
                    "start_time": time
                })


class TestShiftServiceRead:
    """Tests for reading shifts."""

    def test_get_by_id_success(self, db_session: Session, sample_shift_data):
        """Test getting shift by ID."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        shift = service.get_by_id(created.id)

        assert shift.id == created.id
        assert shift.shift_number == created.shift_number

    def test_get_by_id_not_found(self, db_session: Session):
        """Test that getting non-existent shift raises error."""
        service = ShiftService(db_session)

        with pytest.raises(ShiftNotFoundError) as exc_info:
            service.get_by_id(99999)

        assert "not found" in str(exc_info.value).lower()

    def test_get_by_shift_number(self, db_session: Session, sample_shift_data):
        """Test getting shift by shift number."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        shift = service.get_by_shift_number(sample_shift_data["shift_number"])

        assert shift is not None
        assert shift.id == created.id

    def test_get_by_shift_number_not_found(self, db_session: Session):
        """Test getting shift by non-existent shift number."""
        service = ShiftService(db_session)

        shift = service.get_by_shift_number(999)

        assert shift is None

    def test_get_all_ordered(self, db_session: Session, sample_shift_data):
        """Test getting all shifts in order."""
        service = ShiftService(db_session)

        # Create multiple shifts
        days = ["Wednesday", "Tuesday", "Monday"]
        for i in range(3, 0, -1):  # Create in reverse order
            data = sample_shift_data.copy()
            data["shift_number"] = i
            data["day_of_week"] = days[3 - i]
            service.create(data)

        shifts = service.get_all(ordered=True)

        assert len(shifts) == 3
        assert shifts[0].shift_number == 1
        assert shifts[1].shift_number == 2
        assert shifts[2].shift_number == 3

    def test_get_weekend_shifts(self, db_session: Session, sample_shift_data):
        """Test getting weekend shifts."""
        service = ShiftService(db_session)

        # Create weekday shifts
        weekdays = ["Monday", "Tuesday", "Wednesday"]
        for i in range(1, 4):
            data = sample_shift_data.copy()
            data["shift_number"] = i
            data["day_of_week"] = weekdays[i - 1]
            service.create(data)

        # Create weekend shifts (Saturday=5, Sunday=6)
        sat_data = sample_shift_data.copy()
        sat_data["shift_number"] = 5
        sat_data["day_of_week"] = "Saturday"
        service.create(sat_data)

        sun_data = sample_shift_data.copy()
        sun_data["shift_number"] = 6
        sun_data["day_of_week"] = "Sunday"
        service.create(sun_data)

        weekend_shifts = service.get_weekend_shifts()

        assert len(weekend_shifts) == 2
        shift_numbers = [s.shift_number for s in weekend_shifts]
        assert 5 in shift_numbers
        assert 6 in shift_numbers

    def test_get_by_duration_24h(self, db_session: Session, sample_shift_data):
        """Test getting 24-hour shifts."""
        service = ShiftService(db_session)

        # Create 24h shifts
        days = ["Monday", "Tuesday"]
        for i in range(2):
            data = sample_shift_data.copy()
            data["shift_number"] = i + 1
            data["day_of_week"] = days[i]
            data["duration_hours"] = 24
            service.create(data)

        # Create 48h shift
        data_48h = sample_shift_data.copy()
        data_48h["shift_number"] = 3
        data_48h["day_of_week"] = "Wednesday"
        data_48h["duration_hours"] = 48
        service.create(data_48h)

        shifts_24h = service.get_by_duration(24)

        assert len(shifts_24h) == 2
        assert all(s.duration_hours == 24 for s in shifts_24h)

    def test_get_by_duration_48h(self, db_session: Session, sample_shift_data):
        """Test getting 48-hour shifts."""
        service = ShiftService(db_session)

        # Create 24h shift
        data_24h = sample_shift_data.copy()
        data_24h["shift_number"] = 1
        data_24h["duration_hours"] = 24
        service.create(data_24h)

        # Create 48h shifts
        days = ["Tuesday-Wednesday", "Thursday"]
        for i in range(2):
            data = sample_shift_data.copy()
            data["shift_number"] = i + 2
            data["day_of_week"] = days[i]
            data["duration_hours"] = 48
            service.create(data)

        shifts_48h = service.get_by_duration(48)

        assert len(shifts_48h) == 2
        assert all(s.duration_hours == 48 for s in shifts_48h)

    def test_get_by_duration_invalid(self, db_session: Session):
        """Test that invalid duration raises error."""
        service = ShiftService(db_session)

        with pytest.raises(InvalidShiftDataError):
            service.get_by_duration(12)

    def test_get_by_day_of_week(self, db_session: Session, sample_shift_data):
        """Test getting shifts by day of week."""
        service = ShiftService(db_session)

        # Create shifts on different days
        days = ["Monday", "Tuesday", "Wednesday"]
        for i, day in enumerate(days):
            data = sample_shift_data.copy()
            data["shift_number"] = i + 1
            data["day_of_week"] = day
            service.create(data)

        monday_shifts = service.get_by_day_of_week("Monday")

        assert len(monday_shifts) == 1
        assert monday_shifts[0].day_of_week == "Monday"

    def test_get_by_day_of_week_invalid(self, db_session: Session):
        """Test that invalid day_of_week raises error."""
        service = ShiftService(db_session)

        with pytest.raises(InvalidShiftDataError):
            service.get_by_day_of_week("InvalidDay")


class TestShiftServiceUpdate:
    """Tests for updating shifts."""

    def test_update_shift_number(self, db_session: Session, sample_shift_data):
        """Test updating shift number."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        updated = service.update(created.id, {"shift_number": 10})

        assert updated.shift_number == 10

    def test_update_day_of_week(self, db_session: Session, sample_shift_data):
        """Test updating day of week."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        updated = service.update(created.id, {"day_of_week": "Friday"})

        assert updated.day_of_week == "Friday"

    def test_update_duration(self, db_session: Session, sample_shift_data):
        """Test updating duration."""
        service = ShiftService(db_session)
        sample_shift_data["duration_hours"] = 24
        created = service.create(sample_shift_data)

        updated = service.update(created.id, {"duration_hours": 48})

        assert updated.duration_hours == 48

    def test_update_start_time(self, db_session: Session, sample_shift_data):
        """Test updating start time."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        updated = service.update(created.id, {"start_time": "20:00:00"})

        assert updated.start_time == "20:00:00"

    def test_update_duplicate_shift_number_fails(self, db_session: Session, sample_shift_data):
        """Test that updating to duplicate shift number raises error."""
        service = ShiftService(db_session)

        # Create two shifts
        shift1 = service.create(sample_shift_data)

        shift2_data = sample_shift_data.copy()
        shift2_data["shift_number"] = 2
        shift2_data["day_of_week"] = "Tuesday"
        shift2 = service.create(shift2_data)

        # Try to update shift2 with shift1's number
        with pytest.raises(DuplicateShiftNumberError):
            service.update(shift2.id, {"shift_number": shift1.shift_number})

    def test_update_invalid_data(self, db_session: Session, sample_shift_data):
        """Test that updating with invalid data raises error."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        # Invalid day_of_week
        with pytest.raises(InvalidShiftDataError):
            service.update(created.id, {"day_of_week": "InvalidDay"})

        # Invalid duration
        with pytest.raises(InvalidShiftDataError):
            service.update(created.id, {"duration_hours": 12})

    def test_update_non_existent_shift(self, db_session: Session):
        """Test that updating non-existent shift raises error."""
        service = ShiftService(db_session)

        with pytest.raises(ShiftNotFoundError):
            service.update(99999, {"shift_number": 10})


class TestShiftServiceDelete:
    """Tests for deleting shifts."""

    def test_delete_success(self, db_session: Session, sample_shift_data):
        """Test successful shift deletion."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        success = service.delete(created.id)

        assert success is True

        # Verify deletion
        with pytest.raises(ShiftNotFoundError):
            service.get_by_id(created.id)

    def test_delete_non_existent_shift(self, db_session: Session):
        """Test that deleting non-existent shift raises error."""
        service = ShiftService(db_session)

        with pytest.raises(ShiftNotFoundError):
            service.delete(99999)


class TestShiftServiceValidation:
    """Tests for validation methods."""

    def test_shift_number_exists_true(self, db_session: Session, sample_shift_data):
        """Test shift_number_exists returns True for existing number."""
        service = ShiftService(db_session)
        service.create(sample_shift_data)

        exists = service.shift_number_exists(sample_shift_data["shift_number"])

        assert exists is True

    def test_shift_number_exists_false(self, db_session: Session):
        """Test shift_number_exists returns False for non-existent number."""
        service = ShiftService(db_session)

        exists = service.shift_number_exists(999)

        assert exists is False

    def test_shift_number_exists_with_exclusion(self, db_session: Session, sample_shift_data):
        """Test shift_number_exists with shift ID exclusion."""
        service = ShiftService(db_session)
        created = service.create(sample_shift_data)

        # Should return False when excluding the shift with this number
        exists = service.shift_number_exists(
            sample_shift_data["shift_number"],
            exclude_id=created.id
        )

        assert exists is False

    def test_is_weekend_shift_saturday(self, db_session: Session):
        """Test identifying Saturday as weekend shift."""
        service = ShiftService(db_session)

        assert service.is_weekend_shift(5) is True

    def test_is_weekend_shift_sunday(self, db_session: Session):
        """Test identifying Sunday as weekend shift."""
        service = ShiftService(db_session)

        assert service.is_weekend_shift(6) is True

    def test_is_weekend_shift_weekday(self, db_session: Session):
        """Test identifying weekday as not weekend shift."""
        service = ShiftService(db_session)

        for shift_num in [1, 2, 3, 4]:
            assert service.is_weekend_shift(shift_num) is False


class TestShiftServiceQueries:
    """Tests for query methods."""

    def test_get_max_shift_number(self, db_session: Session, sample_shift_data):
        """Test getting maximum shift number."""
        service = ShiftService(db_session)

        # Create shifts with different numbers
        days = ["Monday", "Friday", "Wednesday"]
        for i, shift_num in enumerate([1, 5, 3]):
            data = sample_shift_data.copy()
            data["shift_number"] = shift_num
            data["day_of_week"] = days[i]
            service.create(data)

        max_number = service.get_max_shift_number()

        assert max_number == 5

    def test_get_max_shift_number_empty(self, db_session: Session):
        """Test getting max shift number when no shifts exist."""
        service = ShiftService(db_session)

        max_number = service.get_max_shift_number()

        assert max_number == 0

    def test_get_count(self, db_session: Session, sample_shift_data):
        """Test getting total shift count."""
        service = ShiftService(db_session)

        # Create shifts
        days = ["Monday", "Tuesday", "Wednesday"]
        for i in range(3):
            data = sample_shift_data.copy()
            data["shift_number"] = i + 1
            data["day_of_week"] = days[i]
            service.create(data)

        count = service.get_count()

        assert count == 3

    def test_get_count_empty(self, db_session: Session):
        """Test count when no shifts exist."""
        service = ShiftService(db_session)

        count = service.get_count()

        assert count == 0


class TestShiftServiceExtraPaths:

    def test_get_all_unordered(self, db_session: Session, sample_shift_data):
        """get_all(ordered=False) uses repository.get_all() path."""
        service = ShiftService(db_session)
        service.create(sample_shift_data)
        result = service.get_all(ordered=False)
        assert len(result) == 1

    def test_create_invalid_start_time_non_string(self, db_session: Session, sample_shift_data):
        """Non-string start_time raises InvalidShiftDataError."""
        from src.services.shift_service import InvalidShiftDataError
        service = ShiftService(db_session)
        sample_shift_data["start_time"] = 800
        with pytest.raises(InvalidShiftDataError, match="must be a string"):
            service.create(sample_shift_data)

    def test_create_invalid_start_time_bad_values(self, db_session: Session, sample_shift_data):
        """Out-of-range start_time raises InvalidShiftDataError."""
        from src.services.shift_service import InvalidShiftDataError
        service = ShiftService(db_session)
        sample_shift_data["start_time"] = "25:99:00"
        with pytest.raises(InvalidShiftDataError):
            service.create(sample_shift_data)

    def test_create_invalid_start_time_non_integer_parts(self, db_session: Session, sample_shift_data):
        """Non-integer start_time parts raise InvalidShiftDataError."""
        from src.services.shift_service import InvalidShiftDataError
        service = ShiftService(db_session)
        sample_shift_data["start_time"] = "ab:cd:ef"
        with pytest.raises(InvalidShiftDataError):
            service.create(sample_shift_data)

    def test_create_invalid_start_time_wrong_segment_count(self, db_session: Session, sample_shift_data):
        """start_time without HH:MM:SS format (wrong segment count) raises InvalidShiftDataError."""
        from src.services.shift_service import InvalidShiftDataError
        service = ShiftService(db_session)
        sample_shift_data["start_time"] = "0800"
        with pytest.raises(InvalidShiftDataError, match="HH:MM:SS format"):
            service.create(sample_shift_data)
