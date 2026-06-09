# System Architecture - WhoseOnFirst
**Version:** 1.0  
**Last Updated:** November 4, 2025  
**Status:** Design Phase

---

## Architecture Overview

WhoseOnFirst is designed as a monolithic application with a clear separation of concerns, allowing for future microservices decomposition if needed. The system follows a layered architecture pattern with dependency injection for testability and maintainability.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Client Layer                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Web UI     │  │  Mobile      │  │  API Clients │     │
│  │  (Browser)   │  │  (Future)    │  │  (Future)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Application                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API Layer (REST Endpoints)               │  │
│  │  - Team Member CRUD    - Schedule Management          │  │
│  │  - Shift Configuration - Notification History         │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Service Layer (Business Logic)           │  │
│  │  - Rotation Algorithm  - SMS Notification Service     │  │
│  │  - Schedule Generator  - Validation Service           │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Data Access Layer (SQLAlchemy ORM)           │  │
│  │  - Team Member Repository  - Schedule Repository      │  │
│  │  - Shift Repository        - Notification Log Repo    │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Background Scheduler (APScheduler)           │  │
│  │  - Daily 8am CST Job   - Schedule Generation Job      │  │
│  │  - Cleanup Jobs        - Health Check Job             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             │
                ┌────────────┴─────────────┐
                │                          │
                ▼                          ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│   SQLite Database        │  │   Twilio SMS Gateway     │
│  - team_members          │  │  - SMS Delivery          │
│  - shifts                │  │  - Delivery Status       │
│  - schedule              │  │  - Message Logs          │
│  - notification_log      │  └──────────────────────────┘
│  - job_store (scheduler) │
└──────────────────────────┘
```

---

## Component Architecture

### 1. API Layer

#### Responsibilities
- HTTP request handling
- Input validation (Pydantic models)
- Response serialization
- Error handling and status codes
- Authentication/Authorization (Phase 2)

#### Endpoints Structure

```
/api/
├── v1/
│   ├── team-members/
│   │   ├── GET /              # List all team members
│   │   ├── POST /             # Create new team member
│   │   ├── GET /{id}          # Get team member details
│   │   ├── PUT /{id}          # Update team member
│   │   ├── DELETE /{id}       # Deactivate team member
│   │   └── GET /{id}/history  # Get member's shift history
│   │
│   ├── shifts/
│   │   ├── GET /              # List all shift configurations
│   │   ├── POST /             # Create new shift
│   │   ├── PUT /{id}          # Update shift configuration
│   │   └── DELETE /{id}       # Delete shift
│   │
│   ├── schedule/
│   │   ├── GET /current       # Get current week schedule
│   │   ├── GET /upcoming      # Get next 4 weeks
│   │   ├── POST /generate     # Regenerate schedule
│   │   ├── PUT /{id}          # Override specific assignment
│   │   └── GET /by-date       # Get schedule for specific date range
│   │
│   └── notifications/
│       ├── GET /              # List notification history
│       ├── POST /send-test    # Send test notification
│       └── GET /{id}          # Get notification details
│
├── health                     # Health check endpoint
├── docs                       # Swagger UI (auto-generated)
└── redoc                      # ReDoc (auto-generated)
```

#### Example Endpoint Implementation

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/team-members", tags=["Team Members"])

@router.get("/", response_model=List[TeamMemberResponse])
async def list_team_members(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Retrieve all team members
    
    - **active_only**: Filter to only active members (default: true)
    """
    service = TeamMemberService(db)
    return service.get_all(active_only=active_only)

@router.post("/", 
             response_model=TeamMemberResponse,
             status_code=status.HTTP_201_CREATED)
async def create_team_member(
    member: TeamMemberCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new team member
    
    - **name**: Full name of team member
    - **phone**: Phone number in E.164 format (+1XXXXXXXXXX)
    """
    service = TeamMemberService(db)
    
    # Validate phone number is unique
    if service.phone_exists(member.phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    return service.create(member)
```

---

### 2. Service Layer

#### Purpose
Encapsulates business logic and coordinates between API layer and data layer. Services are stateless and can be easily tested in isolation.

#### Key Services

##### TeamMemberService
```python
class TeamMemberService:
    """Business logic for team member management"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TeamMemberRepository(db)
    
    def create(self, member_data: TeamMemberCreate) -> TeamMember:
        """Create new team member and regenerate schedule"""
        member = self.repository.create(member_data)
        
        # Trigger schedule regeneration
        schedule_service = ScheduleService(self.db)
        schedule_service.regenerate_from_date(datetime.now())
        
        return member
    
    def deactivate(self, member_id: int) -> TeamMember:
        """Deactivate member and regenerate schedule"""
        member = self.repository.update(
            member_id, 
            {"is_active": False}
        )
        
        # Regenerate schedule without this member
        schedule_service = ScheduleService(self.db)
        schedule_service.regenerate_from_date(datetime.now())
        
        return member
```

##### ScheduleService
```python
class ScheduleService:
    """Business logic for schedule generation and management"""
    
    def __init__(self, db: Session):
        self.db = db
        self.schedule_repo = ScheduleRepository(db)
        self.shift_repo = ShiftRepository(db)
        self.member_repo = TeamMemberRepository(db)
    
    def generate_schedule(
        self,
        start_date: datetime,
        weeks: int = 4
    ) -> List[Schedule]:
        """
        Generate fair circular rotation schedule

        Algorithm:
        1. Use RotationAlgorithmService to generate schedule entries
        2. Persist entries via ScheduleRepository.bulk_create()
        3. Return created Schedule objects
        """
        # Generate rotation using simple circular algorithm
        rotation_service = RotationAlgorithmService(self.db)
        schedule_entries = rotation_service.generate_rotation(
            start_date,
            weeks,
            active_members_only=True
        )

        # Persist to database
        schedules = self.schedule_repo.bulk_create(schedule_entries)

        return schedules
```

##### NotificationService
```python
class NotificationService:
    """Business logic for SMS notifications"""
    
    def __init__(self, db: Session, twilio_client: Client):
        self.db = db
        self.twilio = twilio_client
        self.log_repo = NotificationLogRepository(db)
    
    async def send_daily_notifications(self) -> Dict[str, int]:
        """
        Send notifications to all on-call personnel for today
        Returns count of successful/failed sends
        """
        # Get today's schedule entries
        today = datetime.now().date()
        entries = self.schedule_repo.get_by_date(today)
        
        results = {"success": 0, "failed": 0}
        
        for entry in entries:
            try:
                # Format message
                message = self._format_message(entry)
                
                # Send SMS
                result = await self._send_sms(
                    entry.team_member.phone, 
                    message
                )
                
                # Log result
                self.log_repo.create({
                    "schedule_id": entry.id,
                    "status": "sent" if result.success else "failed",
                    "twilio_sid": result.sid,
                    "sent_at": datetime.now()
                })
                
                results["success" if result.success else "failed"] += 1
                
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                results["failed"] += 1
        
        return results
```

##### RotationAlgorithm (Simple Circular Rotation)
```python
class RotationAlgorithmService:
    """
    Implements simple circular rotation for fair on-call scheduling

    Core Principle:
    - Each week, every team member moves forward one position
    - Person on Shift N this week → Shift N+1 next week
    - Person on last shift wraps to Shift 1 the following week
    - No special weekend logic needed (double shift Tue-Wed handles fairness)

    Algorithm: member_index = (shift_index + week_offset) % team_size

    Example (7 members, 6 shifts):
    Week 1: [Alice, Bob, Carol, Dave, Eve, Fran] (Greg off)
    Week 2: [Bob, Carol, Dave, Eve, Fran, Greg] (Alice off)
    Week 3: [Carol, Dave, Eve, Fran, Greg, Alice] (Bob off)
    """

    def __init__(self, db: Session):
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
        Generate fair rotation schedule for specified weeks.

        Returns list of dicts ready for ScheduleRepository.bulk_create()
        """
        # Get team members (sorted by ID for consistency)
        members = self._get_team_members(active_members_only)
        if not members:
            raise InsufficientMembersError("No active team members")

        # Get shifts (ordered by shift_number)
        shifts = self.shift_repo.get_all_ordered()
        if not shifts:
            raise NoShiftsConfiguredError("No shifts configured")

        # Normalize to Monday of start week
        monday = self._get_week_start(start_date)

        # Generate schedule entries
        schedule_entries = []

        for week in range(weeks):
            # Calculate rotation offset for this week
            week_offset = week % len(members)

            # Assign members to shifts (circular rotation)
            for shift_index, shift in enumerate(shifts):
                member_index = (shift_index + week_offset) % len(members)
                member = members[member_index]

                # Calculate shift start/end times
                shift_start = self._calculate_shift_start(monday, week, shift)
                shift_end = shift_start + timedelta(hours=shift.duration_hours)

                # Create entry
                entry = {
                    "team_member_id": member.id,
                    "shift_id": shift.id,
                    "week_number": shift_start.isocalendar()[1],
                    "start_datetime": shift_start,
                    "end_datetime": shift_end,
                    "notified": False
                }
                schedule_entries.append(entry)

        return schedule_entries
```

---

### 3. Data Access Layer

#### Repository Pattern

Each entity has a corresponding repository that encapsulates all database operations.

```python
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

class BaseRepository:
    """Base repository with common CRUD operations"""
    
    def __init__(self, db: Session, model):
        self.db = db
        self.model = model
    
    def get_by_id(self, id: int) -> Optional[Any]:
        return self.db.query(self.model).filter(
            self.model.id == id
        ).first()
    
    def get_all(self) -> List[Any]:
        return self.db.query(self.model).all()
    
    def create(self, data: Dict) -> Any:
        instance = self.model(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
    
    def update(self, id: int, data: Dict) -> Optional[Any]:
        instance = self.get_by_id(id)
        if instance:
            for key, value in data.items():
                setattr(instance, key, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance
    
    def delete(self, id: int) -> bool:
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False

class TeamMemberRepository(BaseRepository):
    """Team member specific operations"""
    
    def __init__(self, db: Session):
        super().__init__(db, TeamMember)
    
    def get_active(self) -> List[TeamMember]:
        return self.db.query(self.model).filter(
            self.model.is_active == True
        ).all()
    
    def get_by_phone(self, phone: str) -> Optional[TeamMember]:
        return self.db.query(self.model).filter(
            self.model.phone == phone
        ).first()
    
    def phone_exists(self, phone: str) -> bool:
        return self.get_by_phone(phone) is not None
```

---

### 4. Database Schema

#### Entity Relationship Diagram

```
┌──────────────────┐
│  team_members    │
├──────────────────┤
│ id (PK)          │
│ name             │
│ phone (UNIQUE)   │
│ is_active        │
│ created_at       │
│ updated_at       │
└──────────────────┘
         │
         │ 1
         │
         │ *
         │
         ▼
┌──────────────────┐         ┌──────────────────┐
│   schedule       │    *    │     shifts       │
├──────────────────┤────────│├──────────────────┤
│ id (PK)          │    1    │ id (PK)          │
│ team_member_id   │────────▶│ shift_number     │
│ shift_id (FK)    │         │ day_of_week      │
│ week_number      │         │ duration_hours   │
│ start_datetime   │         │ start_time       │
│ end_datetime     │         │ created_at       │
│ notified         │         └──────────────────┘
│ created_at       │
└──────────────────┘
         │
         │ 1
         │
         │ *
         │
         ▼
┌──────────────────┐
│ notification_log │
├──────────────────┤
│ id (PK)          │
│ schedule_id (FK) │
│ sent_at          │
│ status           │
│ twilio_sid       │
│ error_message    │
└──────────────────┘
```

#### DDL Schema

```sql
-- Team Members Table
CREATE TABLE team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_team_members_active ON team_members(is_active);
CREATE INDEX idx_team_members_phone ON team_members(phone);

-- Shifts Table
CREATE TABLE shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_number INTEGER NOT NULL UNIQUE,
    day_of_week TEXT NOT NULL,  -- 'Monday', 'Tuesday', etc.
    duration_hours INTEGER NOT NULL,  -- 24 or 48
    start_time TEXT NOT NULL DEFAULT '08:00',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shifts_number ON shifts(shift_number);

-- Schedule Table
CREATE TABLE schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_member_id INTEGER NOT NULL,
    shift_id INTEGER NOT NULL,
    week_number INTEGER NOT NULL,  -- Week number since epoch
    start_datetime TIMESTAMP NOT NULL,
    end_datetime TIMESTAMP NOT NULL,
    notified BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_member_id) REFERENCES team_members(id),
    FOREIGN KEY (shift_id) REFERENCES shifts(id)
);

CREATE INDEX idx_schedule_date ON schedule(start_datetime);
CREATE INDEX idx_schedule_member ON schedule(team_member_id);
CREATE INDEX idx_schedule_week ON schedule(week_number);
CREATE INDEX idx_schedule_notified ON schedule(notified, start_datetime);

-- Notification Log Table
CREATE TABLE notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    sent_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL,  -- 'sent', 'failed', 'pending'
    twilio_sid TEXT,
    error_message TEXT,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id)
);

CREATE INDEX idx_notification_log_schedule ON notification_log(schedule_id);
CREATE INDEX idx_notification_log_status ON notification_log(status);
CREATE INDEX idx_notification_log_date ON notification_log(sent_at);
```

---

### 5. Scheduling Architecture

#### APScheduler Integration

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from pytz import timezone

class SchedulerManager:
    """Manages APScheduler lifecycle and job registration"""
    
    def __init__(self, database_url: str):
        jobstores = {
            'default': SQLAlchemyJobStore(url=database_url)
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone=timezone('America/Chicago')
        )
        
        # Register event listeners
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error_listener,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._job_missed_listener,
            EVENT_JOB_MISSED
        )
    
    def start(self):
        """Start the scheduler and register jobs"""
        self._register_jobs()
        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    def shutdown(self):
        """Gracefully shutdown scheduler"""
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")
    
    def _register_jobs(self):
        """Register all scheduled jobs"""
        
        # Daily SMS notifications at 8:00 AM CST
        self.scheduler.add_job(
            func=self._send_daily_notifications,
            trigger=CronTrigger(hour=8, minute=0),
            id='daily_oncall_notifications',
            name='Send daily on-call SMS notifications',
            replace_existing=True,
            misfire_grace_time=300  # 5 minutes grace period
        )
        
        # Weekly schedule generation (Sunday at 11:00 PM)
        self.scheduler.add_job(
            func=self._generate_weekly_schedule,
            trigger=CronTrigger(day_of_week='sun', hour=23, minute=0),
            id='weekly_schedule_generation',
            name='Generate upcoming week schedule',
            replace_existing=True
        )
        
        # Daily cleanup of old logs (midnight)
        self.scheduler.add_job(
            func=self._cleanup_old_logs,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_log_cleanup',
            name='Clean up old notification logs',
            replace_existing=True
        )
    
    async def _send_daily_notifications(self):
        """Job: Send SMS to on-call personnel"""
        logger.info("Starting daily notification job")
        
        # Get database session
        db = SessionLocal()
        try:
            service = NotificationService(
                db, 
                get_twilio_client()
            )
            results = await service.send_daily_notifications()
            
            logger.info(
                f"Notification job complete: "
                f"{results['success']} sent, {results['failed']} failed"
            )
        except Exception as e:
            logger.error(f"Notification job failed: {e}")
            raise
        finally:
            db.close()
    
    def _job_executed_listener(self, event):
        """Handle successful job execution"""
        logger.info(
            f"Job {event.job_id} executed successfully at {event.scheduled_run_time}"
        )
    
    def _job_error_listener(self, event):
        """Handle job execution errors"""
        logger.error(
            f"Job {event.job_id} failed: {event.exception}",
            exc_info=True
        )
        # Could send alert to admin here
    
    def _job_missed_listener(self, event):
        """Handle missed job executions"""
        logger.warning(
            f"Job {event.job_id} missed scheduled run at {event.scheduled_run_time}"
        )
        # Could trigger catch-up logic here
```

---

### 6. Application Initialization

#### Startup Sequence

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    
    # Startup
    logger.info("Application starting up...")
    
    # 1. Initialize database
    init_database()
    
    # 2. Start scheduler
    scheduler_manager = SchedulerManager(
        database_url=settings.DATABASE_URL
    )
    scheduler_manager.start()
    
    # 3. Verify Twilio connection
    verify_twilio_connection()
    
    # 4. Load configuration
    load_shift_configuration()
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Application shutting down...")
    
    # 1. Stop scheduler
    scheduler_manager.shutdown()
    
    # 2. Close database connections
    close_database_connections()
    
    logger.info("Application shutdown complete")

# Create FastAPI app with lifespan
app = FastAPI(
    title="WhoseOnFirst",
    description="On-Call Team SMS Notifier",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(team_members_router)
app.include_router(shifts_router)
app.include_router(schedule_router)
app.include_router(notifications_router)
```

---

## Deployment Architecture

### Docker Container Structure

```
┌─────────────────────────────────────┐
│     Docker Container (RHEL 10)      │
│                                     │
│  ┌───────────────────────────────┐ │
│  │   Uvicorn ASGI Server         │ │
│  │   (Port 8000)                 │ │
│  └───────────────────────────────┘ │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐ │
│  │   FastAPI Application         │ │
│  │   + APScheduler               │ │
│  └───────────────────────────────┘ │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐ │
│  │   SQLite Database Files       │ │
│  │   - whoseonfirst.db           │ │
│  │   - jobs.db (scheduler)       │ │
│  └───────────────────────────────┘ │
│              │                      │
│        (Volume Mount)               │
└─────────────┼───────────────────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Host Filesystem    │
   │  /opt/whoseonfirst/ │
   │  └── data/          │
   │      ├── whoseonfirst.db
   │      ├── jobs.db     │
   │      └── backups/    │
   └─────────────────────┘
```

### Network Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Internet                               │
└──────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS (443)
                          ▼
┌──────────────────────────────────────────────────────────┐
│         Twilio API (api.twilio.com)                      │
│         - Receives SMS requests                          │
│         - Returns delivery status                        │
└──────────────────────────────────────────────────────────┘
                          ▲
                          │
                          │ HTTPS
                          │
┌─────────────────────────┼────────────────────────────────┐
│     Corporate Network   │                                │
│                         │                                │
│  ┌──────────────────────┼──────────────────┐            │
│  │  RHEL 10 VM          │                  │            │
│  │                      │                  │            │
│  │  ┌───────────────────▼────────────┐    │            │
│  │  │   Firewall / Security Group    │    │            │
│  │  │   - Allow outbound 443         │    │            │
│  │  │   - Allow inbound 8000 (LAN)   │    │            │
│  │  └────────────────────────────────┘    │            │
│  │              │                          │            │
│  │              ▼                          │            │
│  │  ┌─────────────────────────────────┐   │            │
│  │  │  WhoseOnFirst Container         │   │            │
│  │  │  (Port 8000)                    │   │            │
│  │  └─────────────────────────────────┘   │            │
│  │                                         │            │
│  └─────────────────────────────────────────┘            │
│                         ▲                                │
│                         │ HTTP (8000)                    │
│                         │                                │
│             ┌───────────┴───────────┐                    │
│             │                       │                    │
│  ┌──────────▼─────────┐  ┌─────────▼────────┐          │
│  │  Admin Workstation │  │  Team Devices    │          │
│  │  (Web Browser)     │  │  (Receive SMS)   │          │
│  └────────────────────┘  └──────────────────┘          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Security Architecture

### Authentication & Authorization (Phase 2)

```
┌──────────────────────────────────────────────────────────┐
│                   Authentication Flow                     │
└──────────────────────────────────────────────────────────┘

User                    FastAPI              Database
 │                         │                      │
 │  POST /api/auth/login  │                      │
 │  {username, password}  │                      │
 ├────────────────────────▶                      │
 │                         │  Query user         │
 │                         ├─────────────────────▶
 │                         │                      │
 │                         │  User record        │
 │                         ◀─────────────────────┤
 │                         │                      │
 │                         │ Verify password     │
 │                         │ (bcrypt)            │
 │                         │                      │
 │                         │ Generate JWT        │
 │                         │                      │
 │  JWT Token              │                      │
 ◀────────────────────────┤                      │
 │                         │                      │
 │  GET /api/schedule      │                      │
 │  Authorization: Bearer  │                      │
 │  <JWT>                  │                      │
 ├────────────────────────▶                      │
 │                         │ Validate JWT        │
 │                         │ Extract user info   │
 │                         │                      │
 │                         │  Query schedule     │
 │                         ├─────────────────────▶
 │                         │                      │
 │                         │  Schedule data      │
 │                         ◀─────────────────────┤
 │                         │                      │
 │  Schedule response      │                      │
 ◀────────────────────────┤                      │
```

### Security Controls

#### 1. Input Validation
- Pydantic models validate all API inputs
- Phone numbers validated against E.164 format
- SQL injection prevented by SQLAlchemy ORM
- XSS prevention through proper output encoding

#### 2. Secrets Management
```python
# .env file (never committed)
DATABASE_URL=sqlite:///./whoseonfirst.db
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+15551234567
SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # JWT signing

# File permissions: 600 (owner read/write only)
```

#### 3. Transport Security
- HTTPS enforced in production (nginx reverse proxy)
- TLS 1.2+ only
- Strong cipher suites
- HSTS headers enabled

#### 4. Data Protection
- Passwords hashed with bcrypt (Phase 2+)
- JWT tokens for session management (Phase 2+)
- Database backups encrypted
- Phone numbers sanitized in logs

---

## Scalability Considerations

### Vertical Scaling (Phase 1)
Current architecture supports vertical scaling:
- Increase CPU: More Uvicorn workers
- Increase Memory: Larger database cache
- Increase Disk: More storage for logs, backups

### Horizontal Scaling (Phase 2+)

#### Load Balancer Architecture
```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │   (nginx/HAProxy)│
                    └─────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │ FastAPI  │   │ FastAPI  │   │ FastAPI  │
      │Instance 1│   │Instance 2│   │Instance 3│
      └──────────┘   └──────────┘   └──────────┘
              │             │             │
              └─────────────┼─────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │  (Primary/Replica)│
                    └─────────────────┘
```

#### Scheduler in Multi-Instance Setup
**Problem:** APScheduler runs in each instance → duplicate jobs

**Solution Options:**
1. **Leader Election:** Only one instance runs scheduler
2. **Separate Scheduler Service:** Dedicated container for scheduling
3. **Distributed Scheduler:** Use APScheduler's distributed mode

**Recommended:** Separate scheduler service (simple, reliable)

---

## Monitoring & Observability

### Logging Architecture

```
Application
    │
    │ (Structured JSON logs)
    ▼
┌────────────────┐
│  Log Files     │
│  /var/log/     │
│  whoseonfirst/ │
└────────────────┘
    │
    │ (Optional: Phase 2+)
    ▼
┌────────────────┐
│  Log           │
│  Aggregation   │
│  (ELK Stack)   │
└────────────────┘
```

### Metrics Collection (Future)

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
sms_sent_total = Counter(
    'whoseonfirst_sms_sent_total',
    'Total SMS messages sent',
    ['status']
)

notification_duration = Histogram(
    'whoseonfirst_notification_duration_seconds',
    'Time to send notification'
)

active_team_members = Gauge(
    'whoseonfirst_active_team_members',
    'Number of active team members'
)

# Instrument code
with notification_duration.time():
    result = send_sms(phone, message)
    sms_sent_total.labels(status='success' if result.success else 'failed').inc()
```

---

## Disaster Recovery

### Backup Strategy

#### Automated Daily Backups
```bash
#!/bin/bash
# /opt/whoseonfirst/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/whoseonfirst/backups"
DB_FILE="/opt/whoseonfirst/data/whoseonfirst.db"

# Create backup
sqlite3 $DB_FILE ".backup '$BACKUP_DIR/whoseonfirst_$DATE.db'"

# Compress
gzip "$BACKUP_DIR/whoseonfirst_$DATE.db"

# Delete backups older than 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

# Copy to remote storage (optional)
# rsync -avz $BACKUP_DIR remote-server:/backups/whoseonfirst/
```

#### Recovery Procedures

**Scenario 1: Database Corruption**
```bash
# Stop application
podman stop whoseonfirst

# Restore from latest backup
cp /opt/whoseonfirst/backups/whoseonfirst_latest.db.gz /tmp/
gunzip /tmp/whoseonfirst_latest.db.gz
mv /tmp/whoseonfirst_latest.db /opt/whoseonfirst/data/whoseonfirst.db

# Restart application
podman start whoseonfirst

# Verify schedule integrity
curl http://localhost:8000/health
```

**Scenario 2: Complete System Failure**
1. Provision new RHEL 10 VM
2. Install Docker/Podman
3. Clone repository
4. Restore database from backup
5. Configure environment variables
6. Start container

**RTO (Recovery Time Objective):** 30 minutes  
**RPO (Recovery Point Objective):** 24 hours (daily backups)

---

## Technology Decision Records

### ADR-001: Use FastAPI over Flask

**Status:** Accepted  
**Date:** 2025-11-04

**Context:**  
Need to choose web framework for REST API and web interface.

**Decision:**  
Use FastAPI instead of Flask.

**Rationale:**
- Native async/await support for Twilio API calls
- Automatic OpenAPI documentation (Swagger UI)
- Type safety reduces bugs
- Better performance (ASGI vs WSGI)
- Modern Python practices (3.7+)

**Consequences:**
- Team must learn FastAPI (minimal learning curve)
- Better documentation for future integrations
- Easier to add async features later

---

### ADR-002: Start with SQLite, Plan PostgreSQL Migration

**Status:** Accepted  
**Date:** 2025-11-04

**Context:**  
Need database for storing team members, schedule, notification logs.

**Decision:**  
Use SQLite for Phase 1, with clear migration path to PostgreSQL.

**Rationale:**
- SQLite perfect for 5-10 users, low concurrency
- Zero configuration overhead
- Easy backups (single file)
- SQLAlchemy makes migration trivial

**Consequences:**
- Must monitor for write contention issues
- Plan migration when reaching ~10 team members
- Design schema with PostgreSQL compatibility in mind

---

### ADR-003: APScheduler for Job Scheduling

**Status:** Accepted  
**Date:** 2025-11-04

**Context:**  
Need to send daily SMS notifications at 8:00 AM CST.

**Decision:**  
Use APScheduler embedded in FastAPI application.

**Rationale:**
- Cross-platform (works on macOS, Proxmox, RHEL)
- Timezone support (critical for CST)
- Persistent job store (survives restarts)
- Easier testing than system cron

**Consequences:**
- Scheduler runs in application process
- Need separate strategy for multi-instance deployment (Phase 2+)
- Simpler deployment (no external dependencies)

---

## Appendix: System Diagrams

### Data Flow: Daily Notification Process

```
Time: 8:00 AM CST Daily

┌──────────────┐
│  APScheduler │
│  Cron Trigger│
└──────┬───────┘
       │
       │ (1) Trigger job
       ▼
┌──────────────────┐
│ NotificationService│
└──────┬───────────┘
       │
       │ (2) Query today's on-call
       ▼
┌──────────────────┐
│   Database       │
│  (schedule table)│
└──────┬───────────┘
       │
       │ (3) Return schedule entries
       ▼
┌──────────────────┐
│ For each entry:  │
│ - Format message │
│ - Send via Twilio│
│ - Log result     │
└──────┬───────────┘
       │
       │ (4) Send SMS
       ▼
┌──────────────────┐
│   Twilio API     │
└──────┬───────────┘
       │
       │ (5) SMS delivered
       ▼
┌──────────────────┐
│  Team Member     │
│  (Phone)         │
└──────────────────┘
       │
       │ (6) Log result
       ▼
┌──────────────────┐
│   Database       │
│(notification_log)│
└──────────────────┘
```

---

*Document Version: 1.0*  
*Last Updated: November 4, 2025*  
*Next Review: End of Phase 1 Development*
