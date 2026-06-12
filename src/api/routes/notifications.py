"""
Notifications API Routes

FastAPI router for SMS notification management and history.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os
import math

from src.api.dependencies import get_db
from src.api.schemas.notification import (
    NotificationLogResponse,
    NotificationStatsResponse,
    ManualNotificationRequest,
    ManualNotificationResponse
)
from src.repositories.notification_log_repository import NotificationLogRepository
from src.repositories.team_member_repository import TeamMemberRepository
from src.api.routes.auth import require_auth, require_admin
from src.services.sms_service import SMSService


router = APIRouter()


@router.get("/recent")
def get_recent_notifications(
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-indexed)"
    ),
    per_page: int = Query(
        25,
        ge=10,
        le=100,
        description="Items per page (10-100)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Get recent notification logs with pagination support.

    Returns the most recent SMS notification attempts with pagination metadata,
    ordered by timestamp descending.

    Args:
        page: Page number, 1-indexed (default: 1)
        per_page: Items per page, 10-100 (default: 25)
        db: Database session (injected)

    Returns:
        Dictionary with:
        - notifications: List of notification log entries
        - pagination: Metadata (page, per_page, total, pages, has_prev, has_next)

    Backward Compatible:
        Calling without params defaults to page 1, 25 items

    Example:
        GET /api/v1/notifications/recent?page=1&per_page=25
    """
    repo = NotificationLogRepository(db)

    # Calculate offset from page number
    offset = (page - 1) * per_page

    # Fetch data
    logs = repo.get_recent_logs(limit=per_page, offset=offset, include_schedule=True)
    total_count = repo.count_all()

    # Calculate total pages
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    # Return paginated response (convert SQLAlchemy models to dicts)
    return {
        "notifications": jsonable_encoder(logs),
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
    }


@router.get("/stats", response_model=NotificationStatsResponse)
def get_notification_stats(
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to calculate stats for (1-365)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get notification statistics and success metrics.

    Calculates delivery rates, total counts, and status breakdowns
    for the specified time period.

    Args:
        days: Number of days to include in calculation (default 30)
        db: Database session (injected)

    Returns:
        Statistics summary including counts, rates, and trends

    Example:
        GET /api/v1/notifications/stats?days=30
    """
    repo = NotificationLogRepository(db)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Get success rate metrics
    stats = repo.get_success_rate(start_date=start_date, end_date=end_date)

    # Get this month's count
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = repo.get_by_date_range(month_start, end_date, include_schedule=False)

    return {
        "total_sent": stats["total"],
        "this_month": len(this_month),
        "delivery_rate": stats["success_rate"],
        "failed_count": stats["failed"] + stats["undelivered"],
        "sent_count": stats["sent"],
        "delivered_count": stats["delivered"],
        "pending_count": stats["pending"],
        "period_days": days
    }


@router.get("/failed", response_model=List[NotificationLogResponse])
def get_failed_notifications(
    hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Number of hours to look back (1-168)"
    ),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get failed notification attempts.

    Returns recent failed or undelivered notifications for troubleshooting.

    Args:
        hours: Number of hours to look back (default 24)
        db: Database session (injected)

    Returns:
        List of failed notification log entries

    Example:
        GET /api/v1/notifications/failed?hours=48
    """
    repo = NotificationLogRepository(db)
    failed = repo.get_failed_notifications(hours_ago=hours)
    return failed


@router.get("/{notification_id}", response_model=NotificationLogResponse)
def get_notification_by_id(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get a specific notification log by ID.

    Args:
        notification_id: Notification log ID
        db: Database session (injected)

    Returns:
        Notification log entry with schedule details

    Example:
        GET /api/v1/notifications/1
    """
    repo = NotificationLogRepository(db)
    log = repo.get_by_id(notification_id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification log not found: {notification_id}"
        )

    return log


@router.get("/{notification_id}/message")
def get_notification_message_from_twilio(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Fetch SMS message details from Twilio API.

    Retrieves comprehensive message information including body, status,
    timestamps, pricing, and delivery details directly from Twilio.

    Args:
        notification_id: Notification log ID
        db: Database session (injected)

    Returns:
        Dictionary with Twilio message details:
        - body: SMS message text
        - status: Current delivery status
        - direction: outbound-api
        - from: Sender phone number
        - to: Recipient phone number
        - date_sent: When message was sent
        - date_updated: Last status update
        - sid: Twilio message SID
        - num_segments: Number of SMS segments
        - price: Cost in USD
        - price_unit: Currency code
        - error_code: Twilio error code (if failed)
        - error_message: Error description (if failed)

    Raises:
        HTTPException 404: Notification not found
        HTTPException 400: No Twilio SID available
        HTTPException 502: Twilio API error

    Example:
        GET /api/v1/notifications/1/message
    """
    # Get notification record
    repo = NotificationLogRepository(db)
    log = repo.get_by_id(notification_id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification log not found: {notification_id}"
        )

    if not log.twilio_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Twilio SID available for this notification"
        )

    # Initialize SMS service to access Twilio client
    sms_service = SMSService(db)

    # In mock mode, twilio_client is None — return synthetic data instead of crashing
    if sms_service.mock_mode:
        return {
            "body": "[MOCK] Message body unavailable in mock mode",
            "status": "delivered",
            "direction": "outbound-api",
            "from": sms_service.from_phone,
            "to": log.recipient_phone,
            "date_sent": log.sent_at.isoformat() if log.sent_at else None,
            "date_updated": log.sent_at.isoformat() if log.sent_at else None,
            "sid": log.twilio_sid,
            "num_segments": 1,
            "price": None,
            "price_unit": "USD",
            "error_code": None,
            "error_message": None,
        }

    try:
        # Fetch message from Twilio API
        message = sms_service.twilio_client.messages(log.twilio_sid).fetch()

        # Return structured response
        return {
            "body": message.body,
            "status": message.status,
            "direction": message.direction,
            "from": message.from_,
            "to": message.to,
            "date_sent": message.date_sent.isoformat() if message.date_sent else None,
            "date_updated": message.date_updated.isoformat() if message.date_updated else None,
            "sid": message.sid,
            "num_segments": message.num_segments,
            "price": float(message.price) if message.price else None,
            "price_unit": message.price_unit,
            "error_code": message.error_code,
            "error_message": message.error_message,
        }

    except Exception as e:
        # Twilio API error
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch message from Twilio: {str(e)}"
        )


@router.post("/send-manual", response_model=ManualNotificationResponse)
def send_manual_notification(
    request: ManualNotificationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
) -> ManualNotificationResponse:
    """
    Send a manual SMS notification to a specific team member.

    This endpoint allows administrators to send custom SMS messages
    to any active team member, bypassing the schedule system entirely.
    Useful for testing, emergency notifications, or ad-hoc communications.

    **Features:**
    - Send to any active team member
    - Fully customizable message text
    - No schedule dependency
    - Logs as manual notification (schedule_id = NULL)
    - Supports message templates with {name} placeholder

    **Use Cases:**
    - Testing SMS delivery
    - Emergency notifications
    - Manual schedule changes
    - System announcements

    Args:
        request: Manual notification request (team_member_id, message)
        db: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        ManualNotificationResponse with send result and details

    Raises:
        HTTPException 400: Invalid team member or validation error
        HTTPException 404: Team member not found
        HTTPException 502: Twilio API error

    Example:
        POST /api/v1/notifications/send-manual
        {
            "team_member_id": 1,
            "message": "WhoseOnFirst Alert\\n\\nHi {name}, this is a test notification."
        }
    """
    # Get team member
    team_repo = TeamMemberRepository(db)
    member = team_repo.get_by_id(request.team_member_id)

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team member not found: {request.team_member_id}"
        )

    if not member.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team member {member.name} is not active"
        )

    # Replace {name} placeholder in message
    message_text = request.message.replace("{name}", member.name)

    # Send manual notification
    sms_service = SMSService(db)

    try:
        result = sms_service.send_manual_notification(
            team_member=member,
            message=message_text
        )

        # Mask phone number for response
        masked_phone = member.phone[:-4] + 'XXXX' if len(member.phone) >= 4 else member.phone

        if result['success']:
            return ManualNotificationResponse(
                success=True,
                notification_id=result.get('notification_id'),
                twilio_sid=result.get('twilio_sid'),
                status=result['status'],
                message=f"SMS sent successfully to {member.name}",
                recipient_name=member.name,
                recipient_phone=masked_phone,
                sent_at=datetime.now(),
                error=None
            )
        else:
            return ManualNotificationResponse(
                success=False,
                notification_id=result.get('notification_id'),
                twilio_sid=None,
                status=result['status'],
                message=f"Failed to send SMS to {member.name}",
                recipient_name=member.name,
                recipient_phone=masked_phone,
                sent_at=None,
                error=result.get('error')
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send manual notification: {str(e)}"
        )
