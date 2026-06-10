"""
Schedule Manager - APScheduler Integration

This module manages the background scheduler for automated daily notifications.
It configures APScheduler to send SMS notifications at 8:00 AM CST daily.

Key responsibilities:
- Initialize and configure BackgroundScheduler
- Schedule daily notification job at 8:00 AM America/Chicago
- Provide lifecycle management (start, stop, shutdown)
- Query pending notifications and trigger SMS delivery
"""

import logging
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from pytz import timezone

from src.models.database import SessionLocal
from src.repositories.team_member_repository import TeamMemberRepository
from src.services.schedule_service import ScheduleService, DAILY_NOTIFICATION_HOUR
from src.services.sms_service import SMSService
from src.services.settings_service import SettingsService
from src.services.schedule_override_service import ScheduleOverrideService


# Configure logging
logger = logging.getLogger(__name__)


# Chicago timezone for scheduler
CHICAGO_TZ = timezone('America/Chicago')


class ScheduleManager:
    """
    Manager for scheduling automated notifications.

    This class wraps APScheduler's BackgroundScheduler and provides
    methods to start, stop, and manage the daily notification job.

    Attributes:
        scheduler: APScheduler BackgroundScheduler instance
        is_running: Whether the scheduler is currently running
    """

    def __init__(self):
        """
        Initialize the schedule manager.

        Creates a BackgroundScheduler configured with:
        - America/Chicago timezone
        - Memory job store (can be upgraded to SQLAlchemy store later)
        - Coalesce for missed jobs
        """
        self.scheduler = BackgroundScheduler(
            jobstores={'default': MemoryJobStore()},
            timezone=CHICAGO_TZ,
            job_defaults={
                'coalesce': True,  # Combine multiple missed runs into one
                'max_instances': 1,  # Only one instance of job can run at a time
                'misfire_grace_time': 300  # 5 minute grace period for missed jobs
            }
        )
        self.is_running = False
        logger.info("ScheduleManager initialized with timezone: %s", CHICAGO_TZ)

    def add_daily_notification_job(self) -> None:
        """
        Add the daily notification job to the scheduler.

        Configures a CronTrigger to run send_daily_notifications()
        every day at 8:00 AM Chicago time.

        The job will:
        - Query schedules that start today and haven't been notified
        - Send SMS notifications via Twilio
        - Mark schedules as notified
        """
        self.scheduler.add_job(
            func=send_daily_notifications,
            trigger=CronTrigger(
                hour=DAILY_NOTIFICATION_HOUR, minute=0, timezone=CHICAGO_TZ
            ),
            id='daily_oncall_notifications',
            name='Daily On-Call SMS Notifications',
            replace_existing=True
        )
        logger.info(
            "Added daily notification job: %d:00 AM %s",
            DAILY_NOTIFICATION_HOUR,
            CHICAGO_TZ
        )

    def add_auto_renewal_job(self) -> None:
        """
        Add the auto-renewal check job to the scheduler.

        Configures a CronTrigger to run check_auto_renewal()
        every day at 2:00 AM Chicago time.

        The job will:
        - Check if auto-renewal is enabled
        - Find the furthest schedule date
        - If less than threshold weeks remain, generate new schedules
        - Log auto-renewal events
        """
        self.scheduler.add_job(
            func=check_auto_renewal,
            trigger=CronTrigger(hour=2, minute=0, timezone=CHICAGO_TZ),
            id='auto_renewal_check',
            name='Auto-Renewal Schedule Check',
            replace_existing=True
        )
        logger.info("Added auto-renewal job: 2:00 AM %s", CHICAGO_TZ)

    def add_weekly_escalation_job(self) -> None:
        """
        Add the weekly escalation summary job to the scheduler.

        Configures a CronTrigger to run send_weekly_escalation_summary()
        every Monday at 8:00 AM Chicago time.

        The job will:
        - Check if weekly escalation summary is enabled
        - Get escalation contact configuration
        - Query schedules for next 7 days (Mon-Sun)
        - Compose weekly summary message with 48h shift handling
        - Send SMS to all configured escalation contacts
        - Log the weekly summary event
        """
        self.scheduler.add_job(
            func=send_weekly_escalation_summary,
            trigger=CronTrigger(day_of_week='mon', hour=8, minute=0, timezone=CHICAGO_TZ),
            id='weekly_escalation_summary',
            name='Weekly Escalation Contact Schedule Summary',
            replace_existing=True
        )
        logger.info("Added weekly escalation summary job: Monday 8:00 AM %s", CHICAGO_TZ)

    def add_override_completion_job(self) -> None:
        """
        Add the override completion job to the scheduler.

        Configures a CronTrigger to run complete_past_overrides()
        every day at 8:05 AM Chicago time (5 minutes after daily notifications).

        The job will:
        - Find all active overrides where schedule.end_datetime has passed
        - Transition them from 'active' to 'completed' status
        - Set completed_at timestamp
        - Log how many overrides were completed

        Runs at 8:05 AM to ensure daily notifications process first,
        then cleanup happens after schedules have definitely ended.
        """
        self.scheduler.add_job(
            func=complete_past_overrides,
            trigger=CronTrigger(hour=8, minute=5, timezone=CHICAGO_TZ),
            id='override_completion',
            name='Complete Past Schedule Overrides',
            replace_existing=True
        )
        logger.info("Added override completion job: 8:05 AM %s", CHICAGO_TZ)

    def start(self) -> None:
        """
        Start the scheduler.

        This should be called during application startup (e.g., in FastAPI lifespan).

        Raises:
            RuntimeError: If scheduler is already running
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        self.add_daily_notification_job()
        self.add_auto_renewal_job()
        self.add_weekly_escalation_job()
        self.add_override_completion_job()
        self.scheduler.start()
        self.is_running = True
        logger.info("Scheduler started successfully")

        # Log scheduled jobs
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info("Scheduled job: %s (next run: %s)", job.name, job.next_run_time)

    def stop(self, wait: bool = True) -> None:
        """
        Stop the scheduler.

        This should be called during application shutdown.

        Args:
            wait: If True, wait for currently executing jobs to finish
        """
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        self.scheduler.shutdown(wait=wait)
        self.is_running = False
        logger.info("Scheduler stopped")

    def trigger_job_now(self, job_id: str = 'daily_oncall_notifications') -> None:
        """
        Manually trigger a scheduled job immediately.

        Useful for testing and manual execution.

        Args:
            job_id: ID of the job to trigger

        Raises:
            LookupError: If job with given ID doesn't exist
        """
        job = self.scheduler.get_job(job_id)
        if not job:
            raise LookupError(f"Job with ID '{job_id}' not found")

        logger.info("Manually triggering job: %s", job_id)
        job.modify(next_run_time=datetime.now(CHICAGO_TZ))

    def get_job_status(self, job_id: str = 'daily_oncall_notifications') -> Optional[dict]:
        """
        Get the status of a scheduled job.

        Args:
            job_id: ID of the job to check

        Returns:
            Dictionary with job information, or None if job not found
        """
        job = self.scheduler.get_job(job_id)
        if not job:
            return None

        return {
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        }


# Singleton instance
_schedule_manager: Optional[ScheduleManager] = None


def get_schedule_manager() -> ScheduleManager:
    """
    Get the global ScheduleManager instance (singleton pattern).

    Returns:
        ScheduleManager: The global scheduler instance
    """
    global _schedule_manager
    if _schedule_manager is None:
        _schedule_manager = ScheduleManager()
    return _schedule_manager


@contextmanager
def get_db_session():
    """
    Context manager for database sessions in scheduled jobs.

    Ensures proper session cleanup even if job fails.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def send_daily_notifications(force: bool = False) -> dict:
    """
    Send daily on-call notifications via SMS.

    This function is executed by APScheduler every day at 8:00 AM CST.

    Process:
    1. Get today's date in America/Chicago timezone
    2. Query schedules that start today and haven't been notified
    3. For each schedule, send SMS notification via Twilio
    4. Mark schedule as notified in database
    5. Log results

    Args:
        force: If True, resend notifications even if already sent (for testing)

    Returns:
        dict: Result summary with counts (successful, failed, skipped, total)

    Note: This function runs in a background thread, so it must manage
    its own database session.
    """
    logger.info("Starting daily notification job (force=%s)", force)

    # Get current date in Chicago timezone
    now = datetime.now(CHICAGO_TZ)
    today = now.date()

    logger.info("Processing notifications for date: %s", today)

    # Use context manager for database session
    with get_db_session() as db:
        try:
            # Get schedules that need notifications
            service = ScheduleService(db)
            pending_schedules = service.get_pending_notifications(target_date=now, force=force)

            if not pending_schedules:
                logger.info("No pending notifications for today")
                return {
                    'successful': 0,
                    'failed': 0,
                    'skipped': 0,
                    'total': 0
                }

            logger.info("Found %d schedules requiring notification", len(pending_schedules))

            # Initialize SMS service
            sms_service = SMSService(db)

            # Send notifications using batch method
            result = sms_service.send_batch_notifications(pending_schedules, force=force)

            logger.info(
                "Notification job complete: %d successful, %d failed, %d skipped out of %d total",
                result['successful'],
                result['failed'],
                result['skipped'],
                result['total']
            )

            return result

        except Exception as e:
            logger.error("Error in daily notification job: %s", str(e), exc_info=True)
            raise


def trigger_notifications_manually(force: bool = False) -> dict:
    """
    Manually trigger the notification job for testing.

    This function can be called from an API endpoint to test
    the notification system without waiting for the scheduled time.

    Args:
        force: If True, resend notifications even if already sent (for testing)

    Returns:
        dict: Result summary with counts (successful, failed, skipped, total) and status
    """
    logger.info("Manual notification trigger requested (force=%s)", force)

    try:
        result = send_daily_notifications(force=force)
        return {
            'status': 'success',
            'message': 'Notifications processed successfully',
            'timestamp': datetime.now(CHICAGO_TZ).isoformat(),
            'successful': result['successful'],
            'failed': result['failed'],
            'skipped': result['skipped'],
            'total': result['total']
        }
    except Exception as e:
        logger.error("Manual notification trigger failed: %s", str(e), exc_info=True)
        return {
            'status': 'error',
            'message': 'Daily notification job failed - see server logs',
            'timestamp': datetime.now(CHICAGO_TZ).isoformat(),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0
        }


def check_auto_renewal() -> None:
    """
    Check if schedule auto-renewal is needed and generate new schedules.

    This function is executed by APScheduler every day at 2:00 AM CST.

    Process:
    1. Check if auto-renewal is enabled in settings
    2. Find the furthest (maximum) schedule end date
    3. Calculate weeks remaining until that date
    4. If weeks remaining < threshold, generate new schedules
    5. Log the auto-renewal event

    Note: This function runs in a background thread, so it must manage
    its own database session.
    """
    logger.info("Starting auto-renewal check job")

    with get_db_session() as db:
        try:
            # Check if auto-renewal is enabled
            settings_service = SettingsService(db)

            if not settings_service.is_auto_renew_enabled():
                logger.info("Auto-renewal is disabled, skipping check")
                return

            threshold_weeks = settings_service.get_auto_renew_threshold_weeks()
            renew_weeks = settings_service.get_auto_renew_weeks()

            logger.info(
                "Auto-renewal enabled: threshold=%d weeks, renew=%d weeks",
                threshold_weeks,
                renew_weeks
            )

            # Get schedule service to find furthest date
            schedule_service = ScheduleService(db)

            # Get all schedules and find the maximum end date
            all_schedules = schedule_service.schedule_repo.get_all()

            if not all_schedules:
                logger.warning("No schedules found, cannot determine auto-renewal need")
                return

            # Find the furthest end date
            furthest_date = max(schedule.end_datetime for schedule in all_schedules)

            # Calculate weeks until furthest date
            now = datetime.now(CHICAGO_TZ)
            days_remaining = (furthest_date.replace(tzinfo=None) - now.replace(tzinfo=None)).days
            weeks_remaining = days_remaining / 7.0

            logger.info(
                "Current schedule extends to %s (%d days / %.1f weeks remaining)",
                furthest_date.date(),
                days_remaining,
                weeks_remaining
            )

            # Check if renewal is needed
            if weeks_remaining < threshold_weeks:
                logger.info(
                    "Auto-renewal triggered: %.1f weeks < %d week threshold",
                    weeks_remaining,
                    threshold_weeks
                )

                # Generate new schedules starting from furthest date.
                # The DB stores naive Chicago wall time; generate_schedule
                # rejects naive datetimes, so localize first (WOF-15).
                renewal_start = (
                    furthest_date
                    if furthest_date.tzinfo is not None
                    else CHICAGO_TZ.localize(furthest_date, is_dst=False)
                )
                try:
                    new_schedules = schedule_service.generate_schedule(
                        start_date=renewal_start,
                        weeks=renew_weeks,
                        force=False  # Don't overwrite existing
                    )

                    logger.info(
                        "Auto-renewal successful: generated %d new schedule assignments for %d weeks",
                        len(new_schedules),
                        renew_weeks
                    )

                except Exception as gen_error:
                    logger.error(
                        "Auto-renewal generation failed: %s",
                        str(gen_error),
                        exc_info=True
                    )
                    raise

            else:
                logger.info(
                    "Auto-renewal not needed: %.1f weeks >= %d week threshold",
                    weeks_remaining,
                    threshold_weeks
                )

        except Exception as e:
            logger.error("Error in auto-renewal check job: %s", str(e), exc_info=True)
            raise


def collect_weekly_digest_recipients(db) -> list:
    """
    Build the Monday weekly-digest recipient list (WOF-10).

    Recipients are the union of:
    1. Escalation contacts (when escalation display is enabled) whose
       per-contact ``*_weekly_digest`` flag is on — flags default True so
       pre-WOF-10 escalation contacts keep receiving the digest.
    2. Active team members with ``weekly_digest_optin`` set — independent
       of escalation status, so e.g. a supervisor pushed out of the
       escalation pair can still opt in.

    Duplicates are removed by phone number; the escalation listing wins the
    label because it is collected first.

    Args:
        db: SQLAlchemy database session

    Returns:
        List of recipient dicts: {"name": str, "phone": str, "label": str}
    """
    settings_service = SettingsService(db)
    escalation_config = settings_service.get_escalation_config()

    recipients = []
    seen_phones = set()

    if escalation_config.get('enabled'):
        contact_slots = (
            ("primary", "Primary Escalation Contact"),
            ("secondary", "Secondary Escalation Contact"),
        )
        for slot, label in contact_slots:
            name = escalation_config.get(f'{slot}_name')
            phone = escalation_config.get(f'{slot}_phone')
            # Missing flag (config predating WOF-10) means opted in
            wants_digest = escalation_config.get(f'{slot}_weekly_digest', True)
            if name and phone and wants_digest and phone not in seen_phones:
                recipients.append({"name": name, "phone": phone, "label": label})
                seen_phones.add(phone)

    for member in TeamMemberRepository(db).get_digest_recipients():
        if member.phone not in seen_phones:
            recipients.append({
                "name": member.name,
                "phone": member.phone,
                "label": "Team Member Digest"
            })
            seen_phones.add(member.phone)

    return recipients


def send_weekly_escalation_summary() -> dict:
    """
    Send the weekly schedule digest SMS to all opted-in recipients.

    This function is executed by APScheduler every Monday at 8:00 AM CST.

    Process:
    1. Check if the weekly digest is enabled in settings
    2. Collect recipients: opted-in escalation contacts + opted-in team
       members (WOF-10 — decoupled from escalation grouping)
    3. Calculate next Monday 00:00 to following Sunday 23:59
    4. Query schedules for the 7-day period
    5. Compose weekly summary message with 48h shift handling
    6. Send SMS to every recipient
    7. Return summary dict with successful/failed counts

    Returns:
        Dictionary with send results:
        {
            "successful": int,
            "failed": int,
            "total": int,
            "timestamp": ISO datetime string
        }

    Note: This function runs in a background thread, so it must manage
    its own database session.
    """
    from datetime import timedelta

    logger.info("Starting weekly escalation summary job")

    with get_db_session() as db:
        try:
            # Check if weekly summary is enabled
            settings_service = SettingsService(db)

            if not settings_service.is_escalation_weekly_enabled():
                logger.info("Weekly escalation summary is disabled, skipping")
                return {
                    "successful": 0,
                    "failed": 0,
                    "total": 0,
                    "timestamp": datetime.now(CHICAGO_TZ).isoformat(),
                    "message": "Feature disabled"
                }

            # Collect recipients: escalation contacts honoring per-contact
            # digest flags + opted-in active team members (WOF-10)
            recipients = collect_weekly_digest_recipients(db)

            if not recipients:
                logger.warning("Weekly digest enabled but no recipients opted in")
                return {
                    "successful": 0,
                    "failed": 0,
                    "total": 0,
                    "timestamp": datetime.now(CHICAGO_TZ).isoformat(),
                    "message": "No digest recipients"
                }

            logger.info("Weekly digest recipients: %d", len(recipients))

            # Calculate date range for 7 days starting from THIS Monday
            # (or next Monday if today is Monday and it's AFTER 8 AM - for manual triggers)
            now = datetime.now(CHICAGO_TZ)

            # Find this Monday (0 = Monday)
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour > 8:
                # Already Monday and PAST 8 AM (manual trigger), use next Monday
                # Note: Use > not >= so scheduled 8:00 AM job gets THIS week
                days_until_monday = 7

            next_monday = (now + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            following_sunday = next_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

            logger.info(
                "Querying schedules for week: %s to %s",
                next_monday.date(),
                following_sunday.date()
            )

            # Query schedules for the 7-day period
            schedule_service = ScheduleService(db)
            schedules = schedule_service.schedule_repo.get_by_date_range(
                start_date=next_monday,
                end_date=following_sunday,
                include_relationships=True  # Load team_member and shift
            )

            logger.info(f"Found {len(schedules)} schedules for the week")

            # Compose weekly summary message
            sms_service = SMSService(db)
            message = sms_service._compose_weekly_summary(schedules)

            logger.info(f"Composed weekly summary message ({len(message)} chars)")

            # Send to all opted-in recipients (escalation contacts + members)
            result = sms_service.send_weekly_digest(
                message=message,
                recipients=recipients
            )

            logger.info(
                "Weekly escalation summary complete: %d successful, %d failed, %d total",
                result['successful'],
                result['failed'],
                result['total']
            )

            return {
                "successful": result['successful'],
                "failed": result['failed'],
                "total": result['total'],
                "timestamp": datetime.now(CHICAGO_TZ).isoformat()
            }

        except Exception as e:
            logger.error("Error in weekly escalation summary job: %s", str(e), exc_info=True)
            raise


def trigger_weekly_summary_manually() -> dict:
    """
    Manually trigger the weekly escalation summary job for testing.

    This function can be called from an API endpoint to test the
    weekly summary system without waiting for Monday 8:00 AM.

    Returns:
        dict: Result summary with counts (successful, failed, total) and status

    Example:
        >>> result = trigger_weekly_summary_manually()
        >>> print(f"Status: {result['status']}, Sent: {result['successful']}/{result['total']}")
    """
    logger.info("Manual weekly summary trigger requested")

    try:
        result = send_weekly_escalation_summary()
        return {
            'status': 'success',
            'message': 'Weekly escalation summary processed successfully',
            'timestamp': result.get('timestamp', datetime.now(CHICAGO_TZ).isoformat()),
            'successful': result.get('successful', 0),
            'failed': result.get('failed', 0),
            'total': result.get('total', 0)
        }
    except Exception as e:
        logger.error("Manual weekly summary trigger failed: %s", str(e), exc_info=True)
        return {
            'status': 'error',
            'message': 'Weekly summary job failed - see server logs',
            'timestamp': datetime.now(CHICAGO_TZ).isoformat(),
            'successful': 0,
            'failed': 0,
            'total': 0
        }


def complete_past_overrides() -> dict:
    """
    Mark active overrides as 'completed' if their schedule has ended.

    This function is executed by APScheduler every day at 8:05 AM CST.

    Process:
    1. Query all active overrides where schedule.end_datetime < now
    2. Transition each from 'active' to 'completed' status
    3. Set completed_at timestamp
    4. Log how many overrides were completed

    Returns:
        dict: Result summary with completed count and status

    Note: This function runs in a background thread, so it must manage
    its own database session.
    """
    logger.info("Starting override completion job")

    with get_db_session() as db:
        try:
            override_service = ScheduleOverrideService(db)
            completed_count = override_service.complete_past_overrides()

            if completed_count > 0:
                logger.info(
                    "Override completion job: marked %d overrides as completed",
                    completed_count
                )
            else:
                logger.info("Override completion job: no overrides to complete")

            return {
                'completed_count': completed_count,
                'timestamp': datetime.now(CHICAGO_TZ).isoformat()
            }

        except Exception as e:
            logger.error("Error in override completion job: %s", str(e), exc_info=True)
            raise


def trigger_override_completion_manually() -> dict:
    """
    Manually trigger the override completion job for testing.

    This function can be called from an API endpoint to test the
    override completion system without waiting for 8:05 AM.

    Returns:
        dict: Result summary with completed count and status

    Example:
        >>> result = trigger_override_completion_manually()
        >>> print(f"Status: {result['status']}, Completed: {result['completed_count']}")
    """
    logger.info("Manual override completion trigger requested")

    try:
        result = complete_past_overrides()
        return {
            'status': 'success',
            'message': 'Override completion processed successfully',
            'timestamp': result.get('timestamp', datetime.now(CHICAGO_TZ).isoformat()),
            'completed_count': result.get('completed_count', 0)
        }
    except Exception as e:
        logger.error("Manual override completion trigger failed: %s", str(e), exc_info=True)
        return {
            'status': 'error',
            'message': 'Override completion job failed - see server logs',
            'timestamp': datetime.now(CHICAGO_TZ).isoformat(),
            'completed_count': 0
        }
