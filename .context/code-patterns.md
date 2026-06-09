# Code Patterns Reference

This document contains detailed code examples and implementation patterns for WhoseOnFirst. Reference this when implementing features, but keep CLAUDE.md lean.

## Table of Contents

1. [Repository Pattern](#repository-pattern)
2. [Service Layer Pattern](#service-layer-pattern)
3. [APScheduler Configuration](#apscheduler-configuration)
4. [Twilio Integration](#twilio-integration)
5. [Database Session Management](#database-session-management)
6. [API Endpoint Structure](#api-endpoint-structure)
7. [Test Fixtures](#test-fixtures)
8. [Pydantic Validation](#pydantic-validation)

---

## Repository Pattern

### Base Repository

Generic repository with common CRUD operations:

```python
from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""
    
    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """Retrieve a record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: Optional[int] = None) -> List[ModelType]:
        """Retrieve all records with optional pagination."""
        query = self.db.query(self.model).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, data: dict) -> ModelType:
        """Create a new record."""
        instance = self.model(**data)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, id: int, data: dict) -> Optional[ModelType]:
        """Update an existing record."""
        instance = self.get_by_id(id)
        if not instance:
            return None
        
        for key, value in data.items():
            setattr(instance, key, value)
        
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        instance = self.get_by_id(id)
        if not instance:
            return False
        
        self.db.delete(instance)
        self.db.commit()
        return True
```

### Specific Repository (Team Members)

Extend BaseRepository with domain-specific queries:

```python
from src.repositories.base_repository import BaseRepository
from src.models.team_member import TeamMember
from sqlalchemy.orm import Session
from typing import List, Optional

class TeamMemberRepository(BaseRepository[TeamMember]):
    """Repository for team member operations."""
    
    def __init__(self, db: Session):
        super().__init__(db, TeamMember)

    def get_active(self) -> List[TeamMember]:
        """Get all active team members."""
        return (
            self.db.query(self.model)
            .filter(self.model.is_active == True)
            .all()
        )

    def get_by_phone(self, phone: str) -> Optional[TeamMember]:
        """Find member by phone number."""
        return (
            self.db.query(self.model)
            .filter(self.model.phone == phone)
            .first()
        )

    def phone_exists(self, phone: str, exclude_id: Optional[int] = None) -> bool:
        """Check if phone number is already registered."""
        query = self.db.query(self.model).filter(self.model.phone == phone)
        
        if exclude_id:
            query = query.filter(self.model.id != exclude_id)
        
        return query.first() is not None

    def get_ordered_for_rotation(self) -> List[TeamMember]:
        """Get active members sorted by rotation_order for scheduling."""
        return (
            self.db.query(self.model)
            .filter(self.model.is_active == True)
            .order_by(self.model.rotation_order.asc().nulls_last(), self.model.id.asc())
            .all()
        )

    def get_max_rotation_order(self) -> Optional[int]:
        """Get the highest rotation_order value."""
        result = (
            self.db.query(self.model.rotation_order)
            .filter(self.model.is_active == True)
            .order_by(self.model.rotation_order.desc())
            .first()
        )
        return result[0] if result else None

    def update_rotation_orders(self, order_mapping: dict) -> None:
        """Bulk update rotation_order for multiple members."""
        for member_id, order in order_mapping.items():
            self.db.query(self.model).filter(
                self.model.id == int(member_id)
            ).update({"rotation_order": order})
        
        self.db.commit()

    def deactivate(self, member_id: int) -> TeamMember:
        """Deactivate a team member (soft delete)."""
        member = self.get_by_id(member_id)
        member.is_active = False
        self.db.commit()
        self.db.refresh(member)
        return member

    def activate(self, member_id: int) -> TeamMember:
        """Activate a previously deactivated team member."""
        member = self.get_by_id(member_id)
        member.is_active = True
        self.db.commit()
        self.db.refresh(member)
        return member
```

---

## Service Layer Pattern

### Service Structure

Services coordinate between API and repositories, implementing business logic:

```python
from sqlalchemy.orm import Session
from src.repositories.team_member_repository import TeamMemberRepository
from src.api.schemas.team_member import TeamMemberCreate, TeamMemberUpdate
from src.models.team_member import TeamMember
from fastapi import HTTPException
from typing import List, Optional

class TeamMemberService:
    """Business logic for team member management."""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TeamMemberRepository(db)

    def get_all(self, active_only: bool = False) -> List[TeamMember]:
        """Get all team members, optionally filtered by active status."""
        if active_only:
            return self.repository.get_active()
        return self.repository.get_all()

    def get_by_id(self, member_id: int) -> TeamMember:
        """Get a team member by ID."""
        member = self.repository.get_by_id(member_id)
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")
        return member

    def create(self, member_data: TeamMemberCreate) -> TeamMember:
        """Create a new team member with validation."""
        # Check for duplicate phone
        if self.repository.phone_exists(member_data.phone):
            raise HTTPException(
                status_code=400,
                detail="Phone number already exists"
            )
        
        # Create member
        member_dict = member_data.dict()
        member = self.repository.create(member_dict)
        
        # Auto-assign rotation order if active
        if member.is_active:
            max_order = self.repository.get_max_rotation_order()
            next_order = 0 if max_order is None else max_order + 1
            self.repository.update(member.id, {"rotation_order": next_order})
            self.db.refresh(member)
        
        return member

    def update(self, member_id: int, member_data: TeamMemberUpdate) -> TeamMember:
        """Update a team member with validation."""
        member = self.get_by_id(member_id)
        
        # Check for duplicate phone (excluding current member)
        if member_data.phone:
            if self.repository.phone_exists(member_data.phone, exclude_id=member_id):
                raise HTTPException(
                    status_code=400,
                    detail="Phone number already exists"
                )
        
        # Update member
        update_dict = member_data.dict(exclude_unset=True)
        updated_member = self.repository.update(member_id, update_dict)
        
        return updated_member

    def deactivate(self, member_id: int) -> TeamMember:
        """Deactivate a team member and renumber rotation."""
        member = self.get_by_id(member_id)
        
        if not member.is_active:
            return member  # Already inactive
        
        # Deactivate and clear rotation order
        deactivated = self.repository.deactivate(member_id)
        self.repository.update(member_id, {"rotation_order": None})
        self.db.refresh(deactivated)
        
        # Renumber remaining active members
        active_members = self.repository.get_ordered_for_rotation()
        order_mapping = {str(m.id): i for i, m in enumerate(active_members)}
        if order_mapping:
            self.repository.update_rotation_orders(order_mapping)
        
        return deactivated

    def activate(self, member_id: int) -> TeamMember:
        """Activate a team member and assign rotation order."""
        member = self.get_by_id(member_id)
        
        if member.is_active:
            return member  # Already active
        
        # Activate the member
        activated = self.repository.activate(member_id)
        
        # Assign next available rotation order
        max_order = self.repository.get_max_rotation_order()
        next_order = 0 if max_order is None else max_order + 1
        self.repository.update(member_id, {"rotation_order": next_order})
        self.db.refresh(activated)
        
        return activated

    def update_rotation_orders(self, order_mapping: dict) -> None:
        """Update rotation order for multiple members (drag-drop)."""
        # Validate all member IDs exist
        for member_id in order_mapping.keys():
            self.get_by_id(int(member_id))
        
        # Update orders
        self.repository.update_rotation_orders(order_mapping)

    def delete(self, member_id: int) -> bool:
        """Hard delete a team member (use with caution)."""
        member = self.get_by_id(member_id)
        return self.repository.delete(member_id)
```

---

## APScheduler Configuration

### Scheduler Setup with FastAPI Lifespan

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from pytz import timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

def get_scheduler() -> BackgroundScheduler:
    """Get the global scheduler instance."""
    return scheduler

def init_scheduler(database_url: str) -> BackgroundScheduler:
    """Initialize APScheduler with SQLAlchemy job store."""
    jobstores = {
        'default': SQLAlchemyJobStore(url=database_url)
    }
    
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        timezone=timezone('America/Chicago')
    )
    
    return scheduler

def start_scheduler(scheduler: BackgroundScheduler):
    """Start the scheduler and register jobs."""
    if scheduler.running:
        logger.warning("Scheduler already running")
        return
    
    # Register daily notification job
    scheduler.add_job(
        func=send_daily_notifications,
        trigger=CronTrigger(hour=8, minute=0),
        id='daily_oncall_sms',
        name='Send Daily On-Call SMS Notifications',
        replace_existing=True,
        misfire_grace_time=300  # 5 minutes
    )
    
    # Register auto-renewal check job
    scheduler.add_job(
        func=check_auto_renewal,
        trigger=CronTrigger(hour=2, minute=0),
        id='auto_renewal_check',
        name='Check Schedule Auto-Renewal',
        replace_existing=True,
        misfire_grace_time=300
    )
    
    scheduler.start()
    logger.info("APScheduler started successfully")

def stop_scheduler(scheduler: BackgroundScheduler):
    """Gracefully shut down the scheduler."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("APScheduler shut down successfully")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context for scheduler management."""
    global scheduler
    
    # Startup
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/whoseonfirst.db')
    scheduler = init_scheduler(database_url)
    start_scheduler(scheduler)
    
    yield
    
    # Shutdown
    stop_scheduler(scheduler)

# Use in FastAPI app
app = FastAPI(lifespan=lifespan)
```

### Scheduled Job Function

```python
from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.services.sms_service import SMSService
from src.repositories.schedule_repository import ScheduleRepository
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def send_daily_notifications():
    """Send SMS notifications for shifts starting today at 8:00 AM CST."""
    db: Session = SessionLocal()
    
    try:
        # Get schedules starting today (8:00 AM CST check)
        schedule_repo = ScheduleRepository(db)
        today = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        
        pending_schedules = schedule_repo.get_pending_notifications(today)
        
        if not pending_schedules:
            logger.info("No pending notifications for today")
            return
        
        # Send SMS via Twilio
        sms_service = SMSService(db)
        results = sms_service.send_batch_notifications(pending_schedules)
        
        success_count = sum(1 for r in results if r['success'])
        logger.info(f"Sent {success_count}/{len(results)} notifications successfully")
        
    except Exception as e:
        logger.error(f"Error sending daily notifications: {str(e)}", exc_info=True)
    finally:
        db.close()
```

---

## Twilio Integration

### SMS Service with Retry Logic

```python
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from sqlalchemy.orm import Session
from src.models.schedule import Schedule
from src.repositories.notification_log_repository import NotificationLogRepository
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Dict

logger = logging.getLogger(__name__)

class SMSService:
    """Service for sending SMS notifications via Twilio."""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_log_repo = NotificationLogRepository(db)
        
        # Initialize Twilio client
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not all([account_sid, auth_token, self.from_number]):
            raise ValueError("Twilio credentials not configured in environment")
        
        self.client = Client(account_sid, auth_token)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    def send_sms(self, to_number: str, message: str) -> Dict:
        """Send SMS with retry logic."""
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            return {
                'success': True,
                'sid': message.sid,
                'status': message.status
            }
        
        except TwilioRestException as e:
            logger.error(f"Twilio error: {e.code} - {e.msg}")
            return {
                'success': False,
                'error': f"{e.code}: {e.msg}"
            }
    
    def compose_message(self, schedule: Schedule) -> str:
        """Compose SMS message for on-call notification."""
        member_name = schedule.team_member.name
        duration = schedule.shift.duration_hours
        end_time = schedule.end_datetime.strftime('%I:%M %p %Z')
        
        # Keep under 160 characters for single SMS
        message = (
            f"WhoseOnFirst: Your {duration}h on-call shift has started.\n"
            f"Until {end_time}. Questions? Contact admin."
        )
        
        return message
    
    def send_notification(self, schedule: Schedule) -> Dict:
        """Send notification for a specific schedule."""
        to_number = schedule.team_member.phone
        message = self.compose_message(schedule)
        
        # Send SMS
        result = self.send_sms(to_number, message)
        
        # Log notification
        log_data = {
            'schedule_id': schedule.id,
            'sent_at': datetime.now(),
            'status': 'success' if result['success'] else 'failed',
            'twilio_sid': result.get('sid'),
            'error_message': result.get('error')
        }
        
        self.notification_log_repo.create(log_data)
        
        # Mark schedule as notified if successful
        if result['success']:
            schedule.notified = True
            self.db.commit()
        
        return result
    
    def send_batch_notifications(self, schedules: List[Schedule]) -> List[Dict]:
        """Send notifications for multiple schedules."""
        results = []
        
        for schedule in schedules:
            result = self.send_notification(schedule)
            results.append({
                'schedule_id': schedule.id,
                'member_name': schedule.team_member.name,
                'success': result['success']
            })
        
        return results
```

### Environment Variables

```bash
# .env file
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15551234567
```

---

## Database Session Management

### Dependency Injection for FastAPI

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import os

# Database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/whoseonfirst.db')

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """Context manager for database sessions (use in background jobs)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Using Database Session in API

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.team_member_service import TeamMemberService

router = APIRouter()

@router.get("/team-members/")
def list_team_members(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all team members."""
    service = TeamMemberService(db)
    members = service.get_all(active_only=active_only)
    return members
```

---

## API Endpoint Structure

### Complete CRUD Endpoint Example

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.database import get_db
from src.services.team_member_service import TeamMemberService
from src.api.schemas.team_member import (
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamMemberResponse,
    TeamMemberReorderRequest
)

router = APIRouter(prefix="/api/v1/team-members", tags=["team-members"])

@router.get("/", response_model=List[TeamMemberResponse])
def list_team_members(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get all team members."""
    service = TeamMemberService(db)
    return service.get_all(active_only=active_only)

@router.get("/{member_id}", response_model=TeamMemberResponse)
def get_team_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific team member by ID."""
    service = TeamMemberService(db)
    return service.get_by_id(member_id)

@router.post("/", response_model=TeamMemberResponse, status_code=201)
def create_team_member(
    member: TeamMemberCreate,
    db: Session = Depends(get_db)
):
    """Create a new team member."""
    service = TeamMemberService(db)
    return service.create(member)

@router.put("/{member_id}", response_model=TeamMemberResponse)
def update_team_member(
    member_id: int,
    member: TeamMemberUpdate,
    db: Session = Depends(get_db)
):
    """Update a team member."""
    service = TeamMemberService(db)
    return service.update(member_id, member)

@router.delete("/{member_id}")
def deactivate_team_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """Deactivate a team member (soft delete)."""
    service = TeamMemberService(db)
    service.deactivate(member_id)
    return {"message": "Team member deactivated successfully"}

@router.post("/{member_id}/activate", response_model=TeamMemberResponse)
def activate_team_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """Activate a previously deactivated team member."""
    service = TeamMemberService(db)
    return service.activate(member_id)

@router.delete("/{member_id}/permanent")
def permanently_delete_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """Permanently delete a team member (HARD DELETE)."""
    service = TeamMemberService(db)
    success = service.delete(member_id)
    if not success:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"message": "Team member permanently deleted"}

@router.put("/reorder")
def reorder_team_members(
    reorder_data: TeamMemberReorderRequest,
    db: Session = Depends(get_db)
):
    """Update rotation order for multiple team members (drag-drop)."""
    service = TeamMemberService(db)
    service.update_rotation_orders(reorder_data.order_mapping)
    return {"message": "Rotation order updated successfully"}
```

---

## Test Fixtures

### Database Session Fixture

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.models.base import Base

@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a test database session."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    yield session
    
    # Rollback and close
    session.rollback()
    session.close()
```

### Mock Twilio Client

```python
from unittest.mock import Mock, MagicMock
import pytest

@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client for testing SMS."""
    mock_client = Mock()
    mock_message = MagicMock()
    mock_message.sid = 'SM1234567890abcdef'
    mock_message.status = 'queued'
    
    mock_client.messages.create.return_value = mock_message
    
    return mock_client
```

### Test Data Factories

```python
from src.models.team_member import TeamMember
from src.models.shift import Shift

def create_test_member(
    db: Session,
    name: str = "Test User",
    phone: str = "+15551234567",
    is_active: bool = True,
    rotation_order: int = 0
) -> TeamMember:
    """Create a test team member."""
    member = TeamMember(
        name=name,
        phone=phone,
        is_active=is_active,
        rotation_order=rotation_order
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member

def create_test_shift(
    db: Session,
    shift_number: int = 1,
    day_of_week: str = "Monday",
    duration_hours: int = 24,
    start_time: str = "08:00"
) -> Shift:
    """Create a test shift."""
    shift = Shift(
        shift_number=shift_number,
        day_of_week=day_of_week,
        duration_hours=duration_hours,
        start_time=start_time
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift
```

---

## Pydantic Validation

### Custom Validators

```python
from pydantic import BaseModel, validator, Field
import re

class TeamMemberCreate(BaseModel):
    """Schema for creating a team member."""
    
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., regex=r'^\+1\d{10}$')
    is_active: bool = True
    
    @validator('phone')
    def validate_phone_format(cls, v):
        """Validate phone number is in E.164 format."""
        if not re.match(r'^\+1\d{10}$', v):
            raise ValueError('Phone must be in E.164 format: +1XXXXXXXXXX')
        return v
    
    @validator('name')
    def validate_name_not_empty(cls, v):
        """Ensure name is not just whitespace."""
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "phone": "+15551234567",
                "is_active": True
            }
        }

class TeamMemberUpdate(BaseModel):
    """Schema for updating a team member."""
    
    name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, regex=r'^\+1\d{10}$')
    is_active: bool | None = None
    rotation_order: int | None = Field(None, ge=0)
    
    @validator('phone')
    def validate_phone_format(cls, v):
        """Validate phone number if provided."""
        if v and not re.match(r'^\+1\d{10}$', v):
            raise ValueError('Phone must be in E.164 format: +1XXXXXXXXXX')
        return v
    
    class Config:
        # Allow partial updates
        schema_extra = {
            "example": {
                "name": "Jane Doe"
            }
        }

class TeamMemberResponse(BaseModel):
    """Schema for team member responses."""
    
    id: int
    name: str
    phone: str
    is_active: bool
    rotation_order: int | None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True
```

---

## Additional Resources

- **Architecture Documentation:** `/docs/planning/architecture.md`
- **Technology Stack:** `/docs/planning/technical-stack.md`
- **Development Workflow:** `/docs/RPI_PROCESS.md`
- **Testing Guide:** `/tests/README.md` (if it exists)

**Last Updated:** 2025-11-10
**Version:** 1.0.0
