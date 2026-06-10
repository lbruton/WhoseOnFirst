"""
Schedule Pydantic Schemas

Request and response models for schedule API endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from pytz import timezone


# Chicago timezone for validation
CHICAGO_TZ = timezone('America/Chicago')


class ScheduleResponse(BaseModel):
    """
    Schema for schedule assignment responses.

    Includes full schedule details with nested team member and shift information.
    """
    id: int = Field(
        ...,
        description="Unique schedule assignment ID",
        examples=[1]
    )
    team_member_id: int = Field(
        ...,
        description="ID of the assigned team member",
        examples=[1]
    )
    team_member_name: Optional[str] = Field(
        None,
        description="Name of the assigned team member",
        examples=["John Doe"]
    )
    shift_id: int = Field(
        ...,
        description="ID of the shift configuration",
        examples=[1]
    )
    shift_number: Optional[int] = Field(
        None,
        description="Shift number for display",
        examples=[1]
    )
    week_number: int = Field(
        ...,
        description="ISO week number for this assignment",
        examples=[1]
    )
    start_datetime: datetime = Field(
        ...,
        description="When this assignment starts (timezone-aware)",
        examples=["2025-01-06T08:00:00-06:00"]
    )
    end_datetime: datetime = Field(
        ...,
        description="When this assignment ends (timezone-aware)",
        examples=["2025-01-07T08:00:00-06:00"]
    )
    notified: bool = Field(
        ...,
        description="Whether SMS notification has been sent",
        examples=[False]
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when assignment was created",
        examples=["2025-01-01T00:00:00"]
    )

    @field_validator('start_datetime', 'end_datetime', mode='before')
    @classmethod
    def localize_datetime(cls, v):
        """
        Ensure datetime is timezone-aware (America/Chicago).

        Database stores naive datetimes, so we need to localize them
        when returning from the API.

        Args:
            v: Datetime value (naive or aware)

        Returns:
            datetime: Timezone-aware datetime in America/Chicago
        """
        if v and not hasattr(v, 'tzinfo') or (hasattr(v, 'tzinfo') and v.tzinfo is None):
            # Naive datetime from database - localize to Chicago
            return CHICAGO_TZ.localize(v)
        return v

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "team_member_id": 1,
                "team_member_name": "John Doe",
                "shift_id": 1,
                "shift_number": 1,
                "week_number": 1,
                "start_datetime": "2025-01-06T08:00:00-06:00",
                "end_datetime": "2025-01-07T08:00:00-06:00",
                "notified": False,
                "created_at": "2025-01-01T00:00:00"
            }
        }


class ScheduleGenerateResponse(BaseModel):
    """
    Schema for schedule generation responses (WOF-9).

    Wraps the generated assignments together with non-blocking warnings —
    e.g. the start date is today but the daily 8:00 AM notification has
    already run, or no shift covers the chosen start date because it fell
    mid-way through a multi-day shift.
    """
    schedules: List[ScheduleResponse] = Field(
        ...,
        description="The generated schedule assignments"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-blocking warnings about the generated period",
        examples=[[
            "Today's 8:00 AM notification has already run; today's on-call "
            "will not receive an SMS unless notifications are triggered "
            "manually."
        ]]
    )


class ScheduleGenerateRequest(BaseModel):
    """
    Schema for schedule generation requests.

    Used to generate new schedules for a specified time period.
    """
    start_date: datetime = Field(
        ...,
        description="Start date for schedule generation (must be timezone-aware)",
        examples=["2025-01-06T08:00:00-06:00"]
    )
    weeks: int = Field(
        4,
        ge=1,
        le=52,
        description="Number of weeks to generate (1-52)",
        examples=[4]
    )
    force: bool = Field(
        False,
        description="Force regeneration even if schedules already exist",
        examples=[False]
    )

    @field_validator('start_date')
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """
        Validate that start_date is timezone-aware.

        Args:
            v: Datetime value

        Returns:
            datetime: Validated timezone-aware datetime

        Raises:
            ValueError: If datetime is naive (no timezone)
        """
        if v.tzinfo is None:
            raise ValueError(
                'start_date must be timezone-aware. '
                'Use America/Chicago timezone. '
                'Example: 2025-01-06T08:00:00-06:00'
            )
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "start_date": "2025-01-06T08:00:00-06:00",
                "weeks": 4,
                "force": False
            }
        }


class ScheduleRegenerateRequest(BaseModel):
    """
    Schema for schedule regeneration requests.

    Used to regenerate schedules from a specific date forward,
    typically after team composition changes.
    """
    from_date: datetime = Field(
        ...,
        description="Date to regenerate from (must be timezone-aware)",
        examples=["2025-01-06T08:00:00-06:00"]
    )
    weeks: int = Field(
        4,
        ge=1,
        le=52,
        description="Number of weeks to regenerate (1-52)",
        examples=[4]
    )

    @field_validator('from_date')
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """
        Validate that from_date is timezone-aware.

        Args:
            v: Datetime value

        Returns:
            datetime: Validated timezone-aware datetime

        Raises:
            ValueError: If datetime is naive (no timezone)
        """
        if v.tzinfo is None:
            raise ValueError(
                'from_date must be timezone-aware. '
                'Use America/Chicago timezone. '
                'Example: 2025-01-06T08:00:00-06:00'
            )
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "from_date": "2025-01-06T08:00:00-06:00",
                "weeks": 4
            }
        }


class ScheduleQueryParams(BaseModel):
    """
    Schema for schedule query parameters.

    Used for filtering schedules by date range.
    """
    start_date: Optional[datetime] = Field(
        None,
        description="Filter schedules starting on or after this date",
        examples=["2025-01-01T00:00:00-06:00"]
    )
    end_date: Optional[datetime] = Field(
        None,
        description="Filter schedules ending on or before this date",
        examples=["2025-12-31T23:59:59-06:00"]
    )

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Validate that dates are timezone-aware if provided.

        Args:
            v: Datetime value or None

        Returns:
            Optional[datetime]: Validated timezone-aware datetime or None

        Raises:
            ValueError: If datetime is naive (no timezone)
        """
        if v is not None and v.tzinfo is None:
            raise ValueError(
                'Dates must be timezone-aware. '
                'Use America/Chicago timezone. '
                'Example: 2025-01-01T00:00:00-06:00'
            )
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "start_date": "2025-01-01T00:00:00-06:00",
                "end_date": "2025-12-31T23:59:59-06:00"
            }
        }
