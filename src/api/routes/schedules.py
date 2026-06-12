"""
Schedules API Routes

FastAPI router for schedule management operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.api.dependencies import get_db
from src.api.schemas.schedule import (
    ScheduleResponse,
    ScheduleGenerateRequest,
    ScheduleGenerateResponse,
    ScheduleRegenerateRequest
)
from src.services import (
    ScheduleService,
    ScheduleAlreadyExistsError,
    InvalidDateRangeError,
    InsufficientMembersError,
    NoShiftsConfiguredError
)
from src.scheduler import trigger_notifications_manually, trigger_weekly_summary_manually, get_schedule_manager
from src.api.routes.auth import require_auth, require_admin


router = APIRouter()


@router.get("/current", response_model=List[ScheduleResponse])
def get_current_week_schedule(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get the current week's schedule.

    Returns all schedule assignments for the current week.

    Args:
        db: Database session (injected)

    Returns:
        List of schedule assignments for current week

    Example:
        GET /api/v1/schedules/current
    """
    service = ScheduleService(db)
    schedules = service.get_current_week_schedule()
    return schedules


@router.get("/upcoming", response_model=List[ScheduleResponse])
def get_upcoming_schedules(
    weeks: int = Query(
        4,
        ge=1,
        le=104,
        description="Number of weeks to retrieve (1-104)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get upcoming schedules for the next N weeks.

    Args:
        weeks: Number of weeks to retrieve (default: 4)
        db: Database session (injected)

    Returns:
        List of schedule assignments for upcoming weeks

    Example:
        GET /api/v1/schedules/upcoming?weeks=8
    """
    service = ScheduleService(db)
    schedules = service.get_upcoming_schedules(weeks=weeks)
    return schedules


@router.get("/", response_model=List[ScheduleResponse])
def get_schedules_by_date_range(
    start_date: Optional[datetime] = Query(
        None,
        description="Filter schedules starting on or after this date (ISO format with timezone)"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Filter schedules ending on or before this date (ISO format with timezone)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get schedules filtered by date range.

    Both start_date and end_date are optional. If neither is provided,
    returns all schedules.

    Args:
        start_date: Filter schedules starting on or after this date
        end_date: Filter schedules ending on or before this date
        db: Database session (injected)

    Returns:
        List of schedule assignments matching the date range

    Raises:
        HTTPException: 400 if date range is invalid

    Example:
        GET /api/v1/schedules/?start_date=2025-01-01T00:00:00-06:00&end_date=2025-01-31T23:59:59-06:00
    """
    service = ScheduleService(db)

    try:
        if start_date or end_date:
            schedules = service.get_schedule_by_date_range(
                start_date=start_date,
                end_date=end_date
            )
        else:
            # No filters - return all schedules
            schedules = service.schedule_repo.get_all()
        return schedules
    except InvalidDateRangeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/member/{member_id}", response_model=List[ScheduleResponse])
def get_member_schedules(
    member_id: int,
    start_date: Optional[datetime] = Query(
        None,
        description="Filter schedules starting on or after this date"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Filter schedules ending on or before this date"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get all schedules for a specific team member.

    Optionally filter by date range.

    Args:
        member_id: Team member ID
        start_date: Optional start date filter
        end_date: Optional end date filter
        db: Database session (injected)

    Returns:
        List of schedule assignments for the team member

    Example:
        GET /api/v1/schedules/member/1
        GET /api/v1/schedules/member/1?start_date=2025-01-01T00:00:00-06:00
    """
    service = ScheduleService(db)
    schedules = service.get_schedule_by_member(
        team_member_id=member_id,
        start_date=start_date,
        end_date=end_date
    )
    return schedules


@router.post("/generate", response_model=ScheduleGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_schedule(
    request: ScheduleGenerateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Generate new schedules for a specified period.

    By default, fails if schedules already exist for the period.
    Use force=true to regenerate existing schedules.

    The rotation is anchored at start_date (WOF-9): the first member in
    rotation order goes on call on the chosen start date, and no entries
    are created for earlier days of that week. The response carries
    non-blocking warnings — e.g. when the start date is today but the
    daily 8:00 AM notification has already run.

    Args:
        request: Schedule generation request parameters
        db: Database session (injected)

    Returns:
        Envelope with the generated schedule assignments and any warnings

    Raises:
        HTTPException: 400 if schedules already exist (without force=true) or validation fails

    Example:
        POST /api/v1/schedules/generate
        {
            "start_date": "2025-01-06T08:00:00-06:00",
            "weeks": 4,
            "force": false
        }
    """
    service = ScheduleService(db)

    try:
        schedules = service.generate_schedule(
            start_date=request.start_date,
            weeks=request.weeks,
            force=request.force
        )
        warnings = service.get_generation_warnings(request.start_date, schedules)
        return ScheduleGenerateResponse(
            schedules=schedules,
            warnings=warnings
        )
    except ScheduleAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (InsufficientMembersError, NoShiftsConfiguredError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except InvalidDateRangeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/regenerate", response_model=List[ScheduleResponse])
def regenerate_schedule(
    request: ScheduleRegenerateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Regenerate schedules from a specific date forward.

    This is typically used after team composition changes.
    Deletes existing schedules from the date forward and generates new ones.

    Args:
        request: Schedule regeneration request parameters
        db: Database session (injected)

    Returns:
        List of regenerated schedule assignments

    Raises:
        HTTPException: 400 if validation fails

    Example:
        POST /api/v1/schedules/regenerate
        {
            "from_date": "2025-02-01T08:00:00-06:00",
            "weeks": 4
        }
    """
    service = ScheduleService(db)

    try:
        schedules = service.regenerate_from_date(
            from_date=request.from_date,
            weeks=request.weeks
        )
        return schedules
    except (InsufficientMembersError, NoShiftsConfiguredError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except InvalidDateRangeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/member/{member_id}/next", response_model=Optional[ScheduleResponse])
def get_next_assignment(
    member_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get the next upcoming assignment for a specific team member.

    Returns the next schedule assignment that hasn't started yet,
    or None if no future assignments exist.

    Args:
        member_id: Team member ID
        db: Database session (injected)

    Returns:
        Next schedule assignment or None

    Example:
        GET /api/v1/schedules/member/1/next
    """
    service = ScheduleService(db)
    schedule = service.get_next_assignment(team_member_id=member_id)
    return schedule


@router.post("/notifications/trigger", tags=["notifications"])
def trigger_notifications(
    force: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Manually trigger the daily notification job.

    This endpoint allows testing the notification system without waiting
    for the scheduled 8:00 AM run time. It processes all pending notifications
    for today.

    **Note:** This is primarily for testing and manual execution.
    In production, notifications are sent automatically by APScheduler.

    Args:
        force: If True, resend notifications even if already sent (for testing)
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        dict: Result summary with status and counts

    Example:
        POST /api/v1/schedules/notifications/trigger?force=true
    """
    result = trigger_notifications_manually(force=force)
    return result


@router.post("/notifications/weekly-summary/trigger", tags=["notifications"])
def trigger_weekly_summary(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Manually trigger the weekly escalation contact schedule summary.

    This endpoint allows testing the weekly summary feature without waiting
    for the scheduled Monday 8:00 AM CST run time. It sends the next 7-day
    schedule summary to all configured escalation contacts.

    **Note:** This is primarily for testing and manual execution.
    In production, weekly summaries are sent automatically by APScheduler
    every Monday at 8:00 AM CST.

    Args:
        db: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        dict: Result summary with status, message, and send counts

    Example:
        POST /api/v1/schedules/notifications/weekly-summary/trigger
    """
    result = trigger_weekly_summary_manually()
    return result


@router.get("/notifications/status", tags=["notifications"])
def get_notification_job_status(
    current_user = Depends(require_auth)
):
    """
    Get the status of the scheduled notification job.

    Returns information about the daily notification job including
    next scheduled run time.

    Returns:
        dict: Job status information

    Example:
        GET /api/v1/schedules/notifications/status
    """
    scheduler = get_schedule_manager()
    job_status = scheduler.get_job_status()

    if not job_status:
        return {
            "status": "not_found",
            "message": "Notification job not found or scheduler not started"
        }

    return {
        "status": "scheduled",
        "job": job_status,
        "scheduler_running": scheduler.is_running
    }
