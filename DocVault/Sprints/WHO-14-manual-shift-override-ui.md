---
tags: []
doc_type: sprint
project: whoseonfirst
source: migrated
aliases: ["WHO-14 Manual Shift Override UI"]
created: "2025-11-25"
updated: "2026-06-09"
migrated_from: "repo:docs/sprints/WHO-14-manual-shift-override-ui.md"
---

# WHO-14: Manual Shift Override UI - Sprint Document

**Linear Issue:** [WHO-14](https://linear.app/hextrackr/issue/WHO-14/req-037-manual-shift-override-ui)
**PRD Reference:** REQ-037 (docs/planning/PRD.md)
**Target Version:** v1.4.0
**Priority:** Medium (High User Value)
**Estimated Time:** 6-8 hours
**Status:** In Progress
**Started:** 2025-11-25

---

## 🎯 Objective

Provide admin UI for manual shift overrides to handle one-time exceptions (vacation, sick days, shift swaps, emergency coverage) without affecting the rotation algorithm.

**User Story:**
> "As an admin, when Gary K is on vacation next Tuesday, I need to assign Matt C to cover his shift without regenerating the entire schedule or breaking the rotation pattern."

---

## 🔍 Research Summary

**Research Completed:** 2025-11-25
**Research Agent:** Explore (codebase analysis) + Chrome DevTools (live UI inspection)
**Research Duration:** 20 minutes

### Key Findings

1. **All UI patterns exist** - 100% pattern reuse from existing pages
2. **Database conventions are consistent** - Foreign keys, audit fields, snapshots
3. **Modal forms are standardized** - Bootstrap 5 patterns from team-members.html
4. **Calendar rendering is well-structured** - Easy to extend with override logic
5. **Pagination pattern is established** - Reuse from notifications.html v1.3.1

**Risk Assessment:** LOW - No new paradigms, all patterns proven in production

---

## 📊 UX/UI Specifications

### User Requirements (from discussion with Lonnie)

1. **New Page:** "Schedule Override" in sidebar (admin-only)
   - Form to create overrides
   - Table showing audit trail of all overrides (past and future)

2. **Dashboard Display Pattern:**
   - Original scheduled person: Grayed out, truncated to `[Name ...]`, hover shows full info
   - Override person: Normal colored card with icon (🔄) indicating override
   - Example: Nov 21st shows Gary K (colored) covering for Lonnie B (grayed)

3. **Override Form Fields:**
   - Date selector
   - Shift selector
   - Original person (auto-populated from schedule lookup)
   - Replacement person (dropdown of active team members)
   - Notes/Reason field (for audit trail)

4. **Audit Trail Table:**
   - Columns: Date, Shift, Original Person, Override Person, Reason, Status, Created Date, Actions
   - Shows past and future overrides
   - Filterable by status (active, completed, cancelled)

5. **Simplicity Focus:**
   - Admin-only (no self-service needed yet)
   - Core functionality: Create, view, cancel overrides
   - Clear visual distinction on dashboard

### Visual Mockup

**Dashboard Calendar Card (with override):**
```
┌─────────────────────┐
│ 🔄 Gary K           │  ← Override (colored card, icon indicator)
│ +19187019714        │
│ Covering for:       │
│ Lonnie B ...        │  ← Original (grayed, truncated, hover for full details)
└─────────────────────┘
```

**Hover Tooltip on "Lonnie B ...":**
```
Originally scheduled: Lonnie B
Phone: +19186053854
Reason: Vacation
Override by: admin on Nov 18, 2025
```

---

## 🗄️ Database Schema

### New Table: `schedule_overrides`

**File:** `src/models/schedule_override.py` (NEW)

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class ScheduleOverride(Base):
    """
    Manual schedule overrides for vacation, sick days, swaps.

    Overrides layer on top of generated schedules without modifying rotation algorithm.
    When override exists for a date+shift, notification goes to override member.
    """
    __tablename__ = "schedule_overrides"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    schedule_id = Column(
        Integer,
        ForeignKey("schedule.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Original schedule entry being overridden"
    )

    override_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Team member covering the shift"
    )

    # Snapshot Fields (preserve historical accuracy if members change)
    original_member_name = Column(String(100), nullable=False, comment="Original assignee at time of override")
    override_member_name = Column(String(100), nullable=False, comment="Override assignee at time of override")

    # Override Details
    reason = Column(Text, nullable=True, comment="Reason for override (vacation, sick, swap, etc.)")
    status = Column(
        String(20),
        nullable=False,
        default="active",
        index=True,
        comment="active, cancelled, completed"
    )

    # Audit Fields (standard WhoseOnFirst pattern)
    created_by = Column(String(100), nullable=False, comment="Admin username who created override")
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    cancelled_at = Column(DateTime, nullable=True, comment="When override was cancelled (if applicable)")

    # Relationships
    schedule = relationship("Schedule", back_populates="overrides")
    override_member = relationship("TeamMember", foreign_keys=[override_member_id])

    # Indexes for common queries
    __table_args__ = (
        Index('idx_override_schedule_status', 'schedule_id', 'status'),
        Index('idx_override_date_range', 'created_at'),
    )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "override_member_id": self.override_member_id,
            "original_member_name": self.original_member_name,
            "override_member_name": self.override_member_name,
            "reason": self.reason,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
        }
```

### Update to Existing Table: `schedule`

**File:** `src/models/schedule.py` (UPDATE)

Add relationship to Schedule model (around line 70):
```python
# Add this relationship
overrides = relationship(
    "ScheduleOverride",
    back_populates="schedule",
    cascade="all, delete-orphan"
)
```

### Migration

**Command:** `alembic revision --autogenerate -m "add schedule overrides table for manual shift coverage"`

**Expected SQL (SQLite):**
```sql
CREATE TABLE schedule_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    override_member_id INTEGER NOT NULL,
    original_member_name VARCHAR(100) NOT NULL,
    override_member_name VARCHAR(100) NOT NULL,
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at DATETIME,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id) ON DELETE CASCADE,
    FOREIGN KEY (override_member_id) REFERENCES team_members(id) ON DELETE CASCADE
);

CREATE INDEX idx_override_schedule_id ON schedule_overrides(schedule_id);
CREATE INDEX idx_override_member_id ON schedule_overrides(override_member_id);
CREATE INDEX idx_override_status ON schedule_overrides(status);
CREATE INDEX idx_override_schedule_status ON schedule_overrides(schedule_id, status);
CREATE INDEX idx_override_date_range ON schedule_overrides(created_at);
```

---

## 🏗️ Implementation Plan

### Phase 1: Database & Models (1-2 hours)

**Files to Create/Modify:**
1. `src/models/schedule_override.py` (NEW)
2. `src/models/schedule.py` (UPDATE - add relationship)
3. `alembic/versions/[timestamp]_add_schedule_overrides.py` (NEW - migration)

**Tasks:**
- [ ] Create `ScheduleOverride` model with schema above
- [ ] Update `Schedule` model to add `overrides` relationship
- [ ] Generate migration: `alembic revision --autogenerate -m "add schedule overrides table"`
- [ ] Review migration SQL (verify indexes, foreign keys, defaults)
- [ ] Test migration up/down in local environment
- [ ] Apply migration in Docker: `docker exec whoseonfirst-dev alembic upgrade head`
- [ ] Verify table created: `docker exec whoseonfirst-dev sqlite3 /app/data/whoseonfirst.db ".schema schedule_overrides"`

**Git Checkpoint:** `git commit -m "feat: add schedule_overrides database table (WHO-14)"`

**Verification:**
```bash
# Check migration applied
docker exec whoseonfirst-dev alembic current

# Check table structure
docker exec whoseonfirst-dev sqlite3 /app/data/whoseonfirst.db ".schema schedule_overrides"

# Check indexes
docker exec whoseonfirst-dev sqlite3 /app/data/whoseonfirst.db ".indexes schedule_overrides"
```

---

### Phase 2: Backend API (2-3 hours)

#### Task 2.1: Repository Layer (30 min)

**File:** `src/repositories/schedule_override_repository.py` (NEW)

**Pattern:** Extend `BaseRepository` (see `team_member_repository.py` for reference)

**Methods:**
```python
class ScheduleOverrideRepository(BaseRepository[ScheduleOverride]):
    def __init__(self, db: Session):
        super().__init__(db, ScheduleOverride)

    def get_active_overrides(self) -> List[ScheduleOverride]:
        """Get all active overrides (status='active')."""
        return self.db.query(self.model).filter(
            self.model.status == 'active'
        ).order_by(self.model.created_at.desc()).all()

    def get_override_for_schedule(self, schedule_id: int) -> Optional[ScheduleOverride]:
        """Check if active override exists for schedule."""
        return self.db.query(self.model).filter(
            self.model.schedule_id == schedule_id,
            self.model.status == 'active'
        ).first()

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[str] = None
    ) -> List[ScheduleOverride]:
        """Get overrides in date range, optionally filtered by status."""
        query = self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        )

        if status:
            query = query.filter(self.model.status == status)

        return query.order_by(self.model.created_at.desc()).all()

    def cancel_override(self, override_id: int) -> Optional[ScheduleOverride]:
        """Soft delete: Set status='cancelled' and record timestamp."""
        override = self.get_by_id(override_id)
        if override:
            override.status = 'cancelled'
            override.cancelled_at = func.now()
            self.db.commit()
            self.db.refresh(override)
        return override

    def get_paginated(
        self,
        page: int = 1,
        per_page: int = 25,
        status: Optional[str] = None
    ) -> tuple[List[ScheduleOverride], int]:
        """Get paginated overrides with total count."""
        query = self.db.query(self.model)

        if status:
            query = query.filter(self.model.status == status)

        total = query.count()
        offset = (page - 1) * per_page

        overrides = query.order_by(
            self.model.created_at.desc()
        ).limit(per_page).offset(offset).all()

        return overrides, total
```

**Reference:** See `notification_log_repository.py:321-375` for pagination pattern

---

#### Task 2.2: Service Layer (45 min)

**File:** `src/services/schedule_override_service.py` (NEW)

**Pattern:** Coordinate between API and repositories, handle business logic

**Methods:**
```python
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from src.repositories.schedule_override_repository import ScheduleOverrideRepository
from src.repositories.schedule_repository import ScheduleRepository
from src.repositories.team_member_repository import TeamMemberRepository

class ScheduleOverrideService:
    """Business logic for schedule overrides."""

    def __init__(self, db: Session):
        self.db = db
        self.override_repo = ScheduleOverrideRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.team_member_repo = TeamMemberRepository(db)

    def create_override(
        self,
        schedule_id: int,
        override_member_id: int,
        reason: Optional[str],
        created_by: str
    ) -> ScheduleOverride:
        """
        Create schedule override with validation.

        Validations:
        1. Schedule exists
        2. Override member exists and is active
        3. No duplicate active override for same schedule
        4. Override member is different from original assignee

        Raises:
            ValueError: If validation fails
        """
        # Validation 1: Schedule exists
        schedule = self.schedule_repo.get_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule not found: {schedule_id}")

        # Validation 2: Override member exists and is active
        override_member = self.team_member_repo.get_by_id(override_member_id)
        if not override_member:
            raise ValueError(f"Team member not found: {override_member_id}")
        if not override_member.is_active:
            raise ValueError(f"Team member is inactive: {override_member.name}")

        # Validation 3: No duplicate active override
        existing = self.override_repo.get_override_for_schedule(schedule_id)
        if existing:
            raise ValueError(f"Active override already exists for this schedule (override ID: {existing.id})")

        # Validation 4: Different from original
        if schedule.team_member_id == override_member_id:
            raise ValueError("Override member must be different from original assignee")

        # Create override with snapshots
        override_data = {
            "schedule_id": schedule_id,
            "override_member_id": override_member_id,
            "original_member_name": schedule.team_member.name,
            "override_member_name": override_member.name,
            "reason": reason,
            "status": "active",
            "created_by": created_by,
        }

        return self.override_repo.create(override_data)

    def cancel_override(self, override_id: int) -> Optional[ScheduleOverride]:
        """Cancel override (soft delete)."""
        return self.override_repo.cancel_override(override_id)

    def get_override_display(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        """
        Get override display info for calendar rendering.

        Returns:
            Dict with override_member, original_member, reason, icon
            None if no active override
        """
        override = self.override_repo.get_override_for_schedule(schedule_id)
        if not override:
            return None

        return {
            "override_member": override.override_member.to_dict(),
            "original_member_name": override.original_member_name,
            "reason": override.reason,
            "icon": "🔄",
            "created_by": override.created_by,
            "created_at": override.created_at.isoformat()
        }

    def get_all_active_overrides_map(self) -> Dict[int, ScheduleOverride]:
        """
        Get all active overrides as map: schedule_id -> ScheduleOverride.

        Useful for dashboard calendar rendering (check overrides in bulk).
        """
        overrides = self.override_repo.get_active_overrides()
        return {o.schedule_id: o for o in overrides}
```

**Reference:** See `settings_service.py` for service layer patterns

---

#### Task 2.3: Pydantic Schemas (30 min)

**File:** `src/api/schemas/schedule_override.py` (NEW)

**Pattern:** Request/Response schemas with validation (see `schedule.py` for reference)

**Schemas:**
```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class ScheduleOverrideRequest(BaseModel):
    """Request body for creating schedule override."""
    schedule_id: int = Field(..., description="Schedule ID to override", examples=[123])
    override_member_id: int = Field(..., description="Team member ID covering shift", examples=[5])
    reason: Optional[str] = Field(None, max_length=500, description="Reason for override", examples=["Vacation", "Sick day", "Swap with Matt"])

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Trim whitespace from reason."""
        return v.strip() if v else None

class ScheduleOverrideResponse(BaseModel):
    """Response for schedule override."""
    id: int = Field(..., description="Override ID")
    schedule_id: int = Field(..., description="Original schedule ID")
    override_member_id: int = Field(..., description="Covering member ID")
    original_member_name: str = Field(..., description="Original assignee name (snapshot)")
    override_member_name: str = Field(..., description="Covering member name (snapshot)")
    reason: Optional[str] = Field(None, description="Override reason")
    status: str = Field(..., description="active, cancelled, completed")
    created_by: str = Field(..., description="Admin username who created")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation timestamp")

    # Include related schedule and member details (optional enhancement)
    schedule: Optional[dict] = Field(None, description="Full schedule details")
    override_member: Optional[dict] = Field(None, description="Full override member details")

    class Config:
        from_attributes = True

class ScheduleOverrideListResponse(BaseModel):
    """Paginated list of overrides."""
    overrides: list[ScheduleOverrideResponse] = Field(..., description="List of overrides")
    pagination: dict = Field(..., description="Pagination metadata")
    # pagination = {page, per_page, total, pages, has_prev, has_next}
```

**Reference:** See `schedule.py:17-168` for schema patterns with validators

---

#### Task 2.4: API Routes (45 min)

**File:** `src/api/routes/schedule_overrides.py` (NEW)

**Pattern:** FastAPI router with admin-only endpoints (see `schedules.py` for reference)

**Endpoints:**
```python
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import math

from src.api.dependencies import get_db
from src.api.routes.auth import require_admin
from src.api.schemas.schedule_override import (
    ScheduleOverrideRequest,
    ScheduleOverrideResponse,
    ScheduleOverrideListResponse
)
from src.services.schedule_override_service import ScheduleOverrideService

router = APIRouter()

@router.post("/", response_model=ScheduleOverrideResponse, status_code=status.HTTP_201_CREATED)
def create_override(
    request: ScheduleOverrideRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create schedule override (admin-only).

    Allows admin to manually override a schedule assignment for vacation, sick days, swaps.
    Override does not affect rotation algorithm.
    """
    service = ScheduleOverrideService(db)

    try:
        override = service.create_override(
            schedule_id=request.schedule_id,
            override_member_id=request.override_member_id,
            reason=request.reason,
            created_by=current_user.username
        )
        return override
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=ScheduleOverrideListResponse)
def list_overrides(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(25, ge=10, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Filter by status: active, cancelled, completed"),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    List all overrides with pagination (admin-only).
    """
    service = ScheduleOverrideService(db)
    overrides, total = service.override_repo.get_paginated(page, per_page, status_filter)

    total_pages = math.ceil(total / per_page) if total > 0 else 1

    return {
        "overrides": overrides,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
    }

@router.get("/active", response_model=List[ScheduleOverrideResponse])
def get_active_overrides(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Get all active overrides (admin-only).

    Used by dashboard to check for overrides when rendering calendar.
    """
    service = ScheduleOverrideService(db)
    return service.override_repo.get_active_overrides()

@router.get("/{override_id}", response_model=ScheduleOverrideResponse)
def get_override(
    override_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get single override by ID (admin-only)."""
    service = ScheduleOverrideService(db)
    override = service.override_repo.get_by_id(override_id)

    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Override not found: {override_id}"
        )

    return override

@router.delete("/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_override(
    override_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Cancel override (admin-only).

    Soft delete: Sets status='cancelled' and records cancelled_at timestamp.
    """
    service = ScheduleOverrideService(db)
    override = service.cancel_override(override_id)

    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Override not found: {override_id}"
        )

    return None  # 204 No Content
```

**Reference:** See `notifications.py:31-92` for pagination pattern, `schedules.py` for admin-only patterns

---

#### Task 2.5: Register Router (5 min)

**File:** `src/main.py` (UPDATE)

Add router registration (around line 60, after other routers):
```python
from src.api.routes import schedule_overrides

# Register schedule overrides router
app.include_router(
    schedule_overrides.router,
    prefix="/api/v1/schedule-overrides",
    tags=["Schedule Overrides"]
)
```

**Verification:**
- Visit `http://localhost:8900/docs` after Docker rebuild
- Verify "Schedule Overrides" section appears with 5 endpoints

**Git Checkpoint:** `git commit -m "feat: add schedule override API endpoints (WHO-14)"`

---

### Phase 3: Frontend - New Page (2 hours)

#### Task 3.1: Create Schedule Overrides Page (90 min)

**File:** `frontend/schedule-overrides.html` (NEW)

**Pattern:** Based on `notifications.html` structure (stats cards + table)

**Structure:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Schedule Overrides - WhoseOnFirst</title>
    <link href="/static/css/tabler.min.css" rel="stylesheet">
    <link href="/static/css/tabler-icons.min.css" rel="stylesheet">
    <style>
        /* Override-specific styles */
        .override-badge {
            position: relative;
            padding-left: 24px;
        }
        .override-badge::before {
            content: "🔄";
            position: absolute;
            left: 4px;
            font-size: 14px;
        }
        .status-active { color: #10b981; }
        .status-cancelled { color: #6c757d; }
        .status-completed { color: #3b82f6; }
    </style>
</head>
<body>
    <div class="page">
        <!-- Sidebar (reuse from other pages) -->
        <aside class="navbar navbar-vertical">
            <!-- Same sidebar as other pages -->
        </aside>

        <div class="page-wrapper">
            <!-- Page Header -->
            <div class="page-header">
                <div class="container-xl">
                    <div class="row align-items-center">
                        <div class="col">
                            <div class="page-pretitle">MANAGEMENT</div>
                            <h2 class="page-title">Schedule Overrides</h2>
                        </div>
                        <div class="col-auto ms-auto">
                            <button class="btn btn-primary admin-only"
                                    data-bs-toggle="modal"
                                    data-bs-target="#createOverrideModal">
                                <i class="ti ti-plus"></i> Create Override
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Page Body -->
            <div class="page-body">
                <div class="container-xl">
                    <!-- Stats Cards Row (Optional) -->
                    <div class="row row-cards mb-3">
                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-body">
                                    <div class="d-flex align-items-center">
                                        <div class="subheader">Total Overrides</div>
                                        <div class="ms-auto">
                                            <span class="badge bg-blue"><i class="ti ti-calendar-x"></i></span>
                                        </div>
                                    </div>
                                    <div class="h1 mb-0" id="totalOverrides">-</div>
                                    <div class="text-muted">All time</div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-body">
                                    <div class="d-flex align-items-center">
                                        <div class="subheader">Active Overrides</div>
                                        <div class="ms-auto">
                                            <span class="badge bg-green"><i class="ti ti-check"></i></span>
                                        </div>
                                    </div>
                                    <div class="h1 mb-0" id="activeOverrides">-</div>
                                    <div class="text-muted">Current</div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-body">
                                    <div class="d-flex align-items-center">
                                        <div class="subheader">Completed</div>
                                        <div class="ms-auto">
                                            <span class="badge bg-secondary"><i class="ti ti-circle-check"></i></span>
                                        </div>
                                    </div>
                                    <div class="h1 mb-0" id="completedOverrides">-</div>
                                    <div class="text-muted">Past shifts</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Override Table -->
                    <div class="card">
                        <div class="card-header">
                            <h3 class="card-title"><i class="ti ti-history"></i> Override History</h3>
                            <div class="card-actions">
                                <button class="btn btn-sm" id="refreshTable">
                                    <i class="ti ti-refresh"></i> Refresh
                                </button>
                            </div>
                        </div>
                        <div class="table-responsive">
                            <table class="table card-table table-vcenter">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Shift</th>
                                        <th>Original Member</th>
                                        <th>Override Member</th>
                                        <th>Reason</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th class="w-1">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="overrideTableBody">
                                    <tr>
                                        <td colspan="8" class="text-center text-muted">Loading...</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <!-- Pagination -->
                        <div class="card-footer d-flex align-items-center">
                            <p class="m-0 text-muted" id="paginationInfo">Showing 0 overrides</p>
                            <ul class="pagination m-0 ms-auto" id="paginationControls"></ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Create Override Modal (see Task 3.2) -->

    <script src="/static/js/tabler.min.js"></script>
    <script src="/static/js/team-colors.js"></script>
    <script>
        // JavaScript implementation (see below)
    </script>
</body>
</html>
```

**JavaScript Implementation:**
```javascript
const API_BASE = '/api/v1';
let currentPage = 1;
let perPage = 25;
let totalPages = 1;
let totalCount = 0;

// Load overrides on page load
document.addEventListener('DOMContentLoaded', async () => {
    await checkAuth();
    await loadOverrides();
    await loadStats();
});

async function loadOverrides(page = 1) {
    try {
        const response = await fetch(
            `${API_BASE}/schedule-overrides/?page=${page}&per_page=${perPage}`,
            { credentials: 'include' }
        );

        if (!response.ok) throw new Error('Failed to fetch overrides');

        const data = await response.json();
        const overrides = data.overrides;
        const pagination = data.pagination;

        currentPage = pagination.page;
        totalPages = pagination.pages;
        totalCount = pagination.total;

        renderTable(overrides);
        updatePaginationInfo(pagination);
        renderPaginationControls(pagination);

    } catch (error) {
        console.error('Error loading overrides:', error);
        document.getElementById('overrideTableBody').innerHTML = `
            <tr><td colspan="8" class="text-center text-danger">Error loading overrides</td></tr>
        `;
    }
}

function renderTable(overrides) {
    const tbody = document.getElementById('overrideTableBody');

    if (overrides.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="8" class="text-center text-muted">No overrides found</td></tr>
        `;
        return;
    }

    tbody.innerHTML = overrides.map(override => {
        const date = new Date(override.schedule.start_datetime).toLocaleDateString();
        const statusClass = `status-${override.status}`;
        const statusBadge = override.status === 'active'
            ? '<span class="badge bg-success">Active</span>'
            : override.status === 'cancelled'
            ? '<span class="badge bg-secondary">Cancelled</span>'
            : '<span class="badge bg-blue">Completed</span>';

        const cancelBtn = override.status === 'active'
            ? `<button class="btn btn-sm btn-ghost-danger" onclick="cancelOverride(${override.id})">
                 <i class="ti ti-x"></i> Cancel
               </button>`
            : '';

        return `
            <tr>
                <td>${date}</td>
                <td>Shift ${override.schedule.shift_id}</td>
                <td>${override.original_member_name}</td>
                <td class="override-badge">${override.override_member_name}</td>
                <td>${override.reason || '<em class="text-muted">No reason provided</em>'}</td>
                <td>${statusBadge}</td>
                <td>${new Date(override.created_at).toLocaleString()}</td>
                <td>${cancelBtn}</td>
            </tr>
        `;
    }).join('');
}

async function cancelOverride(overrideId) {
    if (!confirm('Cancel this override? The original schedule assignment will be restored.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/schedule-overrides/${overrideId}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (!response.ok) throw new Error('Failed to cancel override');

        alert('Override cancelled successfully');
        await loadOverrides(currentPage);
        await loadStats();

    } catch (error) {
        console.error('Error cancelling override:', error);
        alert('Failed to cancel override: ' + error.message);
    }
}

async function loadStats() {
    // Load all overrides to calculate stats
    // This is a simple implementation - could be optimized with dedicated endpoints
    try {
        const [allRes, activeRes] = await Promise.all([
            fetch(`${API_BASE}/schedule-overrides/?per_page=1000`, { credentials: 'include' }),
            fetch(`${API_BASE}/schedule-overrides/active`, { credentials: 'include' })
        ]);

        const allData = await allRes.json();
        const activeData = await activeRes.json();

        const total = allData.pagination.total;
        const active = activeData.length;
        const completed = allData.overrides.filter(o => o.status === 'completed').length;

        document.getElementById('totalOverrides').textContent = total;
        document.getElementById('activeOverrides').textContent = active;
        document.getElementById('completedOverrides').textContent = completed;

    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Pagination helpers (reuse from notifications.html)
function updatePaginationInfo(pagination) {
    const start = (pagination.page - 1) * pagination.per_page + 1;
    const end = Math.min(pagination.page * pagination.per_page, pagination.total);
    document.getElementById('paginationInfo').textContent =
        pagination.total === 0 ? 'No overrides' : `Showing ${start}-${end} of ${pagination.total} overrides`;
}

function renderPaginationControls(pagination) {
    // Reuse pattern from notifications.html (lines 710-771)
    // Implementation omitted for brevity - see notifications.html for reference
}

// Refresh button
document.getElementById('refreshTable').addEventListener('click', () => {
    loadOverrides(currentPage);
});

// Auth check (reuse from other pages)
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
        if (!response.ok) {
            window.location.href = '/login.html';
            return;
        }
        const user = await response.json();

        // Hide admin-only elements for viewers
        if (user.role === 'viewer') {
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
        }
    } catch (error) {
        window.location.href = '/login.html';
    }
}
```

**Reference Patterns:**
- Page structure: `notifications.html:1-250`
- Table rendering: `notifications.html:560-690`
- Pagination: `notifications.html:710-771`
- Auth check: `index.html:806-820`

---

#### Task 3.2: Create Override Modal (30 min)

Add to `schedule-overrides.html` before closing `</body>`:

```html
<!-- Create Override Modal -->
<div class="modal fade" id="createOverrideModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Create Schedule Override</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form id="createOverrideForm">
                <div class="modal-body">
                    <!-- Date Picker -->
                    <div class="mb-3">
                        <label class="form-label required">Date</label>
                        <input type="date" class="form-control" id="overrideDate" required>
                        <small class="form-hint">Select the date of the shift to override</small>
                    </div>

                    <!-- Shift Selector -->
                    <div class="mb-3">
                        <label class="form-label required">Shift</label>
                        <select class="form-select" id="overrideShift" required>
                            <option value="">Loading shifts...</option>
                        </select>
                        <small class="form-hint">Which shift on this date?</small>
                    </div>

                    <!-- Original Member (Read-only, auto-populated) -->
                    <div class="mb-3">
                        <label class="form-label">Original Assignment</label>
                        <input type="text" class="form-control" id="originalMember" readonly disabled>
                        <small class="form-hint">Currently scheduled team member</small>
                    </div>

                    <!-- Override Member Selector -->
                    <div class="mb-3">
                        <label class="form-label required">Replacement Member</label>
                        <select class="form-select" id="overrideMember" required>
                            <option value="">Select replacement...</option>
                        </select>
                        <small class="form-hint">Who will cover this shift?</small>
                    </div>

                    <!-- Reason/Notes -->
                    <div class="mb-3">
                        <label class="form-label">Reason</label>
                        <textarea class="form-control" id="overrideReason" rows="3"
                                  placeholder="e.g., Vacation, Sick day, Emergency swap with Matt..."></textarea>
                        <small class="form-hint">Optional: Explain why this override is needed</small>
                    </div>

                    <!-- Hidden field for schedule_id -->
                    <input type="hidden" id="scheduleId">
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn" data-bs-dismiss="modal">Cancel</button>
                    <button type="submit" class="btn btn-primary">
                        <i class="ti ti-check"></i> Create Override
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
// Modal logic
const createOverrideModal = document.getElementById('createOverrideModal');

createOverrideModal.addEventListener('show.bs.modal', async () => {
    // Load team members and shifts when modal opens
    await loadShifts();
    await loadTeamMembers();
});

async function loadShifts() {
    try {
        const response = await fetch(`${API_BASE}/shifts/`, { credentials: 'include' });
        const shifts = await response.json();

        const select = document.getElementById('overrideShift');
        select.innerHTML = '<option value="">Select shift...</option>' +
            shifts.map(shift => `
                <option value="${shift.id}">
                    Shift ${shift.shift_number}: ${shift.day_of_week} (${shift.duration_hours}h)
                </option>
            `).join('');
    } catch (error) {
        console.error('Error loading shifts:', error);
    }
}

async function loadTeamMembers() {
    try {
        const response = await fetch(`${API_BASE}/team-members/?active_only=true`, { credentials: 'include' });
        const members = await response.json();

        const select = document.getElementById('overrideMember');
        select.innerHTML = '<option value="">Select replacement...</option>' +
            members.map(member => `
                <option value="${member.id}">${member.name} (${member.phone})</option>
            `).join('');
    } catch (error) {
        console.error('Error loading team members:', error);
    }
}

// When date and shift selected, lookup original assignment
document.getElementById('overrideShift').addEventListener('change', async () => {
    const date = document.getElementById('overrideDate').value;
    const shiftId = document.getElementById('overrideShift').value;

    if (!date || !shiftId) return;

    // Lookup schedule for this date + shift
    try {
        const response = await fetch(
            `${API_BASE}/schedules/lookup?date=${date}&shift_id=${shiftId}`,
            { credentials: 'include' }
        );

        if (response.ok) {
            const schedule = await response.json();
            document.getElementById('originalMember').value = schedule.team_member.name;
            document.getElementById('scheduleId').value = schedule.id;
        } else {
            document.getElementById('originalMember').value = 'No schedule found for this date';
            document.getElementById('scheduleId').value = '';
        }
    } catch (error) {
        console.error('Error looking up schedule:', error);
    }
});

// Form submission
document.getElementById('createOverrideForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const scheduleId = document.getElementById('scheduleId').value;
    const overrideMemberId = document.getElementById('overrideMember').value;
    const reason = document.getElementById('overrideReason').value.trim();

    if (!scheduleId) {
        alert('No schedule found for the selected date/shift. Please check your selection.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/schedule-overrides/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                schedule_id: parseInt(scheduleId),
                override_member_id: parseInt(overrideMemberId),
                reason: reason || null
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create override');
        }

        // Success
        alert('Override created successfully');

        // Close modal
        const modal = bootstrap.Modal.getInstance(createOverrideModal);
        modal.hide();

        // Reset form
        document.getElementById('createOverrideForm').reset();
        document.getElementById('scheduleId').value = '';
        document.getElementById('originalMember').value = '';

        // Refresh table
        await loadOverrides(currentPage);
        await loadStats();

    } catch (error) {
        console.error('Error creating override:', error);
        alert('Failed to create override: ' + error.message);
    }
});
</script>
```

**Reference:** Modal pattern from `team-members.html:202-237`, form submission from `team-members.html:641-715`

---

#### Task 3.3: Add Sidebar Navigation (10 min)

**Files to Update:** All HTML files with inline sidebar, OR `frontend/components/sidebar.html` if sidebar is componentized

**Pattern:** Based on `sidebar.html:39-43` (admin-only nav item)

**Add this before Help menu item:**
```html
<li class="nav-item admin-only" data-page="schedule-overrides">
    <a class="nav-link" href="schedule-overrides.html">
        <span class="nav-link-icon"><i class="ti ti-calendar-x"></i></span>
        <span class="nav-link-title">Schedule Overrides</span>
    </a>
</li>
```

**Files to update (if sidebar is inline):**
- `frontend/index.html`
- `frontend/team-members.html`
- `frontend/shifts.html`
- `frontend/schedule.html`
- `frontend/notifications.html`
- `frontend/change-password.html`
- `frontend/help.html`
- `frontend/schedule-overrides.html` (new)

**OR** if sidebar is componentized (check for sidebar.html include pattern):
- `frontend/components/sidebar.html`

**Git Checkpoint:** `git commit -m "feat: add schedule overrides page with modal form (WHO-14)"`

---

### Phase 4: Dashboard Integration (1 hour)

#### Task 4.1: Modify Calendar Rendering (45 min)

**File:** `frontend/index.html` (UPDATE)

**Location:** Modify `buildCalendar()` function (lines 654-741)

**Changes:**

1. **Fetch active overrides on calendar load** (before `buildCalendar()` call):
```javascript
let activeOverridesMap = {};  // Global variable to store overrides

async function loadCalendar() {
    try {
        // Fetch data in parallel
        const [schedulesRes, membersRes, shiftsRes, overridesRes] = await Promise.all([
            fetch(`${API_BASE}/schedules/upcoming?weeks=8`, { credentials: 'include' }),
            fetch(`${API_BASE}/team-members/`, { credentials: 'include' }),
            fetch(`${API_BASE}/shifts/`, { credentials: 'include' }),
            fetch(`${API_BASE}/schedule-overrides/active`, { credentials: 'include' })  // NEW
        ]);

        const schedules = await schedulesRes.json();
        const members = await membersRes.json();
        const shifts = await shiftsRes.json();
        const overrides = await overridesRes.json();  // NEW

        // Build override map: schedule_id -> override
        activeOverridesMap = {};
        overrides.forEach(override => {
            activeOverridesMap[override.schedule_id] = override;
        });

        buildCalendar(schedules, members, shifts);

    } catch (error) {
        console.error('Error loading calendar:', error);
    }
}
```

2. **Check for override before rendering each day** (inside `buildCalendar()` loop, around line 716):
```javascript
// Find schedule for this day (existing code)
const daySchedule = schedules.find(s => {
    const start = new Date(s.start_datetime);
    const end = new Date(s.end_datetime);
    return date >= new Date(start.toDateString()) && date < new Date(end.toDateString());
});

if (daySchedule) {
    // NEW: Check for override
    const override = activeOverridesMap[daySchedule.id];

    if (override) {
        // Render OVERRIDE card + grayed original
        const overrideMember = members.find(m => m.id === override.override_member_id);
        const originalMember = members.find(m => m.id === daySchedule.team_member_id);

        if (overrideMember && originalMember) {
            const overrideCard = createOverrideCard(overrideMember, originalMember, override, members);
            dayCell.appendChild(overrideCard);
        }
    } else {
        // Render NORMAL card (existing code)
        const member = members.find(m => m.id === daySchedule.team_member_id);
        const shift = shifts.find(s => s.id === daySchedule.shift_id);

        if (member && shift) {
            const badge = createNormalCard(member, shift, members);
            dayCell.appendChild(badge);
        }
    }
}
```

3. **Create override card rendering function** (new function):
```javascript
function createOverrideCard(overrideMember, originalMember, override, allMembers) {
    const container = document.createElement('div');
    container.className = 'on-call-badges';

    // Override card (colored, with icon)
    const overrideBadge = document.createElement('div');
    const overrideColor = getTeamColor(overrideMember.id, allMembers.filter(m => m.is_active));
    overrideBadge.className = `on-call-badge ${overrideColor} override-badge`;
    overrideBadge.title = `Override: ${override.reason || 'No reason provided'}\nCreated by: ${override.created_by}`;
    overrideBadge.innerHTML = `
        <span class="badge-icon">🔄</span>
        <span class="badge-name">${overrideMember.name}</span>
        <span class="badge-phone">${overrideMember.phone}</span>
    `;

    // Original card (grayed out, truncated)
    const originalBadge = document.createElement('div');
    originalBadge.className = 'on-call-badge original-grayed';
    originalBadge.title = `Originally scheduled: ${originalMember.name}\nPhone: ${originalMember.phone}`;
    originalBadge.innerHTML = `
        <span class="badge-label">Originally:</span>
        <span class="badge-name-truncated">${originalMember.name} ...</span>
    `;

    container.appendChild(overrideBadge);
    container.appendChild(originalBadge);

    return container;
}

function createNormalCard(member, shift, allMembers) {
    // Existing card rendering logic (unchanged)
    // See index.html:716-734 for reference
    const badge = document.createElement('div');
    const colorClass = member.is_active
        ? getTeamColor(member.id, allMembers.filter(m => m.is_active))
        : 'bg-secondary';
    badge.className = `on-call-badge ${colorClass}`;
    // ... rest of existing code
    return badge;
}
```

**Reference:** Calendar rendering logic in `index.html:654-741`

---

#### Task 4.2: Add CSS for Override Display (15 min)

**File:** `frontend/index.html` (UPDATE)

**Location:** Add to `<style>` section (around line 28, after existing calendar styles)

```css
/* Override Badge Styles */
.override-badge {
    position: relative;
    padding-left: 28px;
}

.override-badge .badge-icon {
    position: absolute;
    left: 6px;
    top: 6px;
    font-size: 16px;
}

.original-grayed {
    background-color: #6c757d !important; /* Gray */
    opacity: 0.7;
    font-size: 0.85em;
    margin-top: 6px;
    border-top: 1px solid rgba(255,255,255,0.3);
    padding-top: 6px;
    cursor: help;
}

.original-grayed .badge-label {
    font-size: 0.75em;
    opacity: 0.8;
    display: block;
    margin-bottom: 2px;
}

.original-grayed .badge-name-truncated::after {
    content: "";
    /* Truncation handled by text content */
}

.on-call-badges {
    display: flex;
    flex-direction: column;
    gap: 0;
}

/* Tooltip enhancement for override cards */
.override-badge:hover,
.original-grayed:hover {
    opacity: 1;
    transform: scale(1.02);
    transition: all 0.2s ease;
}
```

**Git Checkpoint:** `git commit -m "feat: add override display to dashboard calendar (WHO-14)"`

---

### Phase 5: Notification Logic Update (30 min)

**File:** `src/services/sms_service.py` (UPDATE)

**Location:** Modify `send_notification()` method (around line 187)

**Changes:**

1. **Import ScheduleOverrideRepository:**
```python
# Add to imports at top of file
from src.repositories.schedule_override_repository import ScheduleOverrideRepository
```

2. **Check for override before sending SMS:**
```python
def send_notification(self, schedule: Schedule, retry_attempt: int = 0) -> dict:
    """
    Send SMS notification for schedule, checking for override first.

    If active override exists:
    - Send SMS to override member instead of scheduled member
    - Log notification with note about override

    Otherwise:
    - Send SMS to scheduled member normally
    """
    # NEW: Check for override
    override_repo = ScheduleOverrideRepository(self.db)
    override = override_repo.get_override_for_schedule(schedule.id)

    # Determine recipient
    if override:
        # Send to override member
        recipient_member = override.override_member
        note = f"Override: Sent to {override.override_member_name} instead of {override.original_member_name}. Reason: {override.reason or 'Not specified'}"
        logger.info(f"Schedule {schedule.id} has override: {note}")
    else:
        # Send to scheduled member (normal flow)
        recipient_member = schedule.team_member
        note = None

    # Validate recipient
    if not recipient_member:
        error_msg = "No recipient found (neither scheduled member nor override member)"
        logger.error(f"Schedule {schedule.id}: {error_msg}")
        return {
            'success': False,
            'status': 'failed',
            'error': error_msg
        }

    # Rest of existing send_notification() logic
    # (message composition, Twilio API call, retry logic, notification logging)
    # ...

    # When logging notification, include override note if applicable
    if override:
        # Append override note to log entry
        # (Implementation depends on notification_log schema - may need error_message field)
        pass

    return result
```

**Alternative Approach:** If notification logging doesn't support notes, add override info to error_message field:
```python
self.notification_repo.log_notification_attempt(
    schedule_id=schedule.id,
    status=status,
    twilio_sid=twilio_sid,
    error_message=note if override else error_message,  # NEW
    recipient_name=recipient_member.name,
    recipient_phone=recipient_member.phone
)
```

**Reference:** SMS service structure in `sms_service.py:187-355`

**Git Checkpoint:** `git commit -m "feat: update notification logic to check for overrides (WHO-14)"`

---

### Phase 6: Docker Rebuild & Testing (30-60 min)

#### Rebuild Docker Container

```bash
# Stop container
docker-compose -f docker-compose.dev.yml down

# Rebuild with latest code
docker-compose -f docker-compose.dev.yml build

# Start container
docker-compose -f docker-compose.dev.yml up -d

# Check logs for startup
docker-compose -f docker-compose.dev.yml logs -f
```

#### Apply Database Migration

```bash
# Apply migration
docker exec whoseonfirst-dev alembic upgrade head

# Verify table created
docker exec whoseonfirst-dev sqlite3 /app/data/whoseonfirst.db ".schema schedule_overrides"
```

---

## ✅ Testing Checklist

### Database Tests
- [ ] Migration applies cleanly (alembic upgrade head)
- [ ] Migration rolls back cleanly (alembic downgrade -1)
- [ ] Table created with correct schema
- [ ] Indexes created: schedule_id, override_member_id, status, (schedule_id, status), created_at
- [ ] Foreign key constraints work (cascade delete)
- [ ] Default values work (status='active', created_at=now())

### API Tests
- [ ] **POST /api/v1/schedule-overrides/** creates override (201 Created)
- [ ] Validation works: invalid schedule_id returns 400
- [ ] Validation works: inactive member returns 400
- [ ] Validation works: duplicate override returns 400
- [ ] **GET /api/v1/schedule-overrides/** returns paginated list
- [ ] **GET /api/v1/schedule-overrides/active** returns only active overrides
- [ ] **GET /api/v1/schedule-overrides/{id}** returns single override
- [ ] **DELETE /api/v1/schedule-overrides/{id}** cancels override (204 No Content)
- [ ] Cancelled override has status='cancelled' and cancelled_at timestamp
- [ ] Admin-only authorization enforced (viewer gets 403 Forbidden)
- [ ] API docs show "Schedule Overrides" section at /docs

### Frontend Tests - Schedule Overrides Page
- [ ] New sidebar nav item "Schedule Overrides" appears for admin
- [ ] Nav item hidden for viewer role
- [ ] Page loads at /schedule-overrides.html
- [ ] Stats cards display correct counts (Total, Active, Completed)
- [ ] Override table loads with pagination
- [ ] Table displays all columns correctly
- [ ] Status badges show correct colors (green=active, gray=cancelled, blue=completed)
- [ ] "Create Override" button opens modal
- [ ] Modal form validates required fields
- [ ] Date picker works correctly
- [ ] Shift selector populates from API
- [ ] Original member auto-populates when date+shift selected
- [ ] Replacement member selector shows only active members
- [ ] Form submission creates override successfully
- [ ] Success message shows and modal closes
- [ ] Table refreshes after creation
- [ ] Stats update after creation
- [ ] "Cancel" button on active override works
- [ ] Confirmation dialog appears before cancel
- [ ] Override status changes to "cancelled" after cancel
- [ ] Pagination works (Prev, Next, page numbers)
- [ ] Refresh button reloads table

### Frontend Tests - Dashboard Integration
- [ ] Dashboard calendar loads overrides on page load
- [ ] Override card shows 🔄 icon before member name
- [ ] Override card uses correct team color
- [ ] Override card shows override member name and phone
- [ ] Original member shows as grayed card below override
- [ ] Original member shows truncated name "Name ..."
- [ ] Hover on override card shows tooltip with reason and created_by
- [ ] Hover on original card shows full original assignment info
- [ ] Calendar without overrides renders normally (no visual regression)
- [ ] Calendar with multiple overrides in same month renders correctly
- [ ] 48-hour shifts with overrides render correctly (override + continuation)

### Integration Tests - End-to-End Scenarios

**Test Case 1: Create Override for Single Day**
- [ ] Navigate to Schedule Overrides page
- [ ] Click "Create Override"
- [ ] Select date: Nov 21st, 2025
- [ ] Select shift: Shift 1 (24h)
- [ ] Original member auto-populates: Lonnie B
- [ ] Select replacement: Gary K
- [ ] Enter reason: "Vacation"
- [ ] Submit form
- [ ] Verify success message
- [ ] Verify override appears in table as "Active"
- [ ] Navigate to Dashboard
- [ ] Verify Nov 21st shows:
  - 🔄 Gary K (colored card)
  - Lonnie B ... (grayed card below)
- [ ] Hover on Lonnie B, verify tooltip shows "Originally scheduled: Lonnie B, Phone: +19186053854, Reason: Vacation"

**Test Case 2: SMS Notification to Override Member**
- [ ] Create override for tomorrow's shift (Original: Ben D, Override: Matt C)
- [ ] Wait for or manually trigger daily SMS at 8:00 AM CST
- [ ] Verify SMS sent to Matt C (not Ben D)
- [ ] Check notification log: recipient should be Matt C
- [ ] Verify notification log error_message contains override note

**Test Case 3: Cancel Override**
- [ ] Create override (Active status)
- [ ] Navigate to Schedule Overrides page
- [ ] Click "Cancel" button on override
- [ ] Confirm cancellation dialog
- [ ] Verify override status changes to "Cancelled"
- [ ] Verify cancelled_at timestamp is set
- [ ] Navigate to Dashboard
- [ ] Verify calendar shows original member (no override card)

**Test Case 4: Override for 48-Hour Shift**
- [ ] Create override for Shift 2 (48h Tue-Wed)
- [ ] Original: Ben D, Override: Clark M
- [ ] Navigate to Dashboard
- [ ] Verify Tuesday shows:
  - 🔄 Clark M (48h)
  - Ben D ... (grayed)
- [ ] Verify Wednesday shows:
  - 🔄 Clark M (continues)
  - Ben D ... (grayed)

**Test Case 5: Validation - Duplicate Override**
- [ ] Create override for Nov 25th, Shift 1
- [ ] Try to create ANOTHER override for same schedule
- [ ] Verify error: "Active override already exists for this schedule"
- [ ] Verify first override still active, second not created

**Test Case 6: Validation - Inactive Member**
- [ ] Deactivate a team member (e.g., Ken U)
- [ ] Try to create override with Ken U as replacement
- [ ] Verify error: "Team member is inactive: Ken U"
- [ ] Verify override not created

**Test Case 7: Authorization - Viewer Role**
- [ ] Log in as viewer (username: viewer, password: viewer)
- [ ] Verify "Schedule Overrides" nav item is HIDDEN
- [ ] Navigate directly to /schedule-overrides.html via URL
- [ ] Verify page loads but "Create Override" button is HIDDEN
- [ ] Try API call: POST /api/v1/schedule-overrides/ (via browser console)
- [ ] Verify 403 Forbidden response

**Test Case 8: Audit Trail**
- [ ] Create 3 overrides with different reasons
- [ ] Cancel 1 override
- [ ] Wait for 1 override to complete (shift date passes)
- [ ] Navigate to Schedule Overrides page
- [ ] Verify table shows all 3 overrides
- [ ] Verify status badges: Active (green), Cancelled (gray), Completed (blue)
- [ ] Verify created_at timestamps are correct
- [ ] Verify created_by shows admin username
- [ ] Verify cancelled override has cancelled_at timestamp

---

## 📈 Performance Considerations

### Database Queries
- **Indexes:** All foreign keys indexed for fast lookups
- **Eager Loading:** Use `joinedload()` to avoid N+1 queries when fetching overrides with schedule/member details
- **Pagination:** Limit queries to 25-100 records per page (never load all overrides at once)

### Frontend Rendering
- **Override Map:** Build `schedule_id -> override` map once, reuse for entire calendar (O(1) lookups)
- **Active Overrides Only:** Dashboard only fetches active overrides (not cancelled/completed)
- **Caching:** Consider caching override map for calendar month (refresh on Create/Cancel)

### SMS Service
- **Single Query:** Check override with single DB query per notification (indexed lookup by schedule_id)
- **No Blocking:** Override check adds <5ms to notification send time

---

## 🔄 Future Enhancements (Out of Scope for v1.4.0)

### Phase 2 Enhancements (v1.5.0+)
1. **Bulk Override Creation**
   - Create multiple overrides at once (e.g., entire week vacation)
   - Import overrides from CSV

2. **Override Templates**
   - Save common override patterns (e.g., "Gary K covers all Mondays in December")
   - Recurring overrides

3. **Self-Service Portal**
   - Team members request overrides via portal
   - Admin approval workflow
   - Email/SMS notifications for approvals

4. **Calendar UI Enhancements**
   - Click calendar day to create override directly (inline form)
   - Drag-and-drop to reassign shifts
   - Visual calendar view on Schedule Overrides page (not just table)

5. **Advanced Filtering**
   - Filter by date range
   - Filter by team member
   - Filter by reason keywords
   - Export to CSV

6. **Audit Trail Enhancements**
   - Show who cancelled override
   - Show modification history (if override is edited)
   - Integration with notification history (link override to sent SMS)

---

## 📝 Documentation Updates

### Files to Update After Implementation

1. **CHANGELOG.md** - Add v1.4.0 section:
```markdown
## [1.4.0] - 2025-11-XX

### Added

- **Manual Shift Override UI** - Admin interface for handling vacation, sick days, and shift swaps ([WHO-14](https://linear.app/hextrackr/issue/WHO-14))
  - **Purpose**: Allow admins to manually override schedule assignments without affecting rotation algorithm
  - **Features**:
    - New "Schedule Overrides" page in admin sidebar
    - Create override form with date picker, shift selector, replacement member, and reason field
    - Override audit table showing all past and future overrides with status (active, cancelled, completed)
    - Dashboard calendar displays override with 🔄 icon + grayed original member below
    - SMS notifications automatically sent to override member instead of originally scheduled member
    - Cancel override functionality (soft delete with audit trail)
  - **Implementation**:
    - **Database**: New `schedule_overrides` table with foreign keys to `schedule` and `team_members`
    - **Backend**: Repository, service, and API layers following WhoseOnFirst patterns
    - **Frontend**: New page (`schedule-overrides.html`) with modal form and paginated table
    - **Dashboard**: Modified calendar rendering to check for overrides and display dual cards
    - **Notifications**: Updated SMS service to check for overrides before sending
  - **Use Cases**:
    - Vacation coverage: "Gary K on vacation Dec 15-20, Matt C covering"
    - Sick day: "Ben D called in sick, Clark M covering tonight"
    - Emergency swap: "Lonnie B has training Friday, Lance B swapping shifts"
  - **Audit Trail**: All overrides logged with reason, created_by, timestamps, and status changes
  - **Authorization**: Admin-only feature (viewers cannot create/cancel overrides)

### Technical Notes

- **Database Schema**: `schedule_overrides` table with 11 columns, 5 indexes, 2 foreign keys
- **API Endpoints**: 5 new endpoints under `/api/v1/schedule-overrides/`
- **Pattern Reuse**: 100% reuse of existing UI patterns (modals, tables, pagination, calendar cards)
- **Snapshot Fields**: `original_member_name` and `override_member_name` preserve historical accuracy
- **Status Lifecycle**: active → cancelled (manual) OR active → completed (automatic after shift date passes)
```

2. **README.md** - Update features list:
```markdown
## Features

- ✅ Circular rotation algorithm (supports any team size)
- ✅ Automated daily SMS notifications via Twilio
- ✅ Dual-device SMS support (primary + secondary phone)
- ✅ Weekly escalation contact summaries
- ✅ Manual shift overrides (NEW in v1.4.0)
  - Admin interface for vacation, sick days, and shift swaps
  - Dashboard displays overrides with visual indicators
  - Audit trail for all override activities
```

3. **CLAUDE.md** - Update Known Limitations section:
```markdown
### Known Limitations

- ~~**No PTO/Vacation Management**~~ ✅ RESOLVED in v1.4.0
  - **Current**: Manual shift override UI allows admins to create overrides for vacation, sick days, swaps
  - **Limitation**: No self-service portal for team members (admin must create overrides)
  - **Future Enhancement (v1.5.0+)**: Self-service portal with approval workflow
```

4. **PRD.md** - Mark REQ-037 as complete:
```markdown
### REQ-037: Manual Shift Override UI ✅ COMPLETE (v1.4.0)

**Status**: Implemented
**Version**: v1.4.0
**Linear Issue**: [WHO-14](https://linear.app/hextrackr/issue/WHO-14)

**Implementation Summary**:
- Admin-only UI for creating/cancelling overrides
- Dashboard calendar integration with visual indicators
- SMS notification routing to override member
- Comprehensive audit trail with pagination
```

---

## 🎯 Success Criteria

WHO-14 is considered **COMPLETE** when:

✅ All 6 implementation phases committed with git checkpoints
✅ All 50+ test cases pass
✅ Admin can create override via UI
✅ Dashboard shows override with 🔄 icon + grayed original
✅ SMS sent to override member (not original)
✅ Override audit table shows all overrides with pagination
✅ Viewer role cannot access override features
✅ Documentation updated (CHANGELOG, README, CLAUDE.md)
✅ Linear issue WHO-14 marked as Done
✅ No regressions in existing features

---

## 📊 Metrics & Analytics (Post-Launch)

After v1.4.0 launches, track:
- **Override Usage**: How many overrides created per month?
- **Override Reasons**: Most common reasons (vacation, sick, swap)?
- **Override Duration**: Average time between creation and completion?
- **Cancellation Rate**: What % of overrides get cancelled?
- **User Feedback**: Are admins satisfied with the workflow?

Use these metrics to inform v1.5.0 self-service enhancements.

---

## 📅 Sprint Timeline

**Estimated Duration:** 6-8 hours over 1-2 days

**Suggested Schedule:**
- **Day 1 (4 hours):**
  - Phase 1: Database & Models (1-2 hours)
  - Phase 2: Backend API (2-3 hours)

- **Day 2 (4 hours):**
  - Phase 3: Frontend Page (2 hours)
  - Phase 4: Dashboard Integration (1 hour)
  - Phase 5: Notification Logic (30 min)
  - Phase 6: Testing & Documentation (30 min)

**Checkpoints:**
- After each phase: Git commit
- After Phase 2: Docker rebuild, test API endpoints via /docs
- After Phase 3: Test new page UI
- After Phase 4: Test dashboard calendar display
- After Phase 6: Full integration testing, mark WHO-14 as Done

---

## 🔗 References

### Linear
- **Issue**: [WHO-14](https://linear.app/hextrackr/issue/WHO-14/req-037-manual-shift-override-ui)
- **PRD**: REQ-037 (docs/planning/PRD.md)

### Codebase Patterns (File:Line References)
- **Database Models**: `src/models/notification_log.py:1-100`
- **Repositories**: `src/repositories/notification_log_repository.py:18-376`
- **Services**: `src/services/settings_service.py:1-398`
- **API Routes**: `src/api/routes/notifications.py:1-404`
- **Schemas**: `src/api/schemas/schedule.py:1-168`
- **Frontend Modal**: `frontend/team-members.html:202-237`
- **Frontend Table**: `frontend/notifications.html:252-279`
- **Frontend Pagination**: `frontend/notifications.html:271-278, 710-771`
- **Calendar Rendering**: `frontend/index.html:654-741`
- **Sidebar Navigation**: `frontend/components/sidebar.html:39-43` OR inline in each HTML file

### Documentation
- **Architecture**: `docs/planning/architecture.md`
- **Tech Stack**: `docs/planning/technical-stack.md`
- **Code Patterns**: `docs/reference/code-patterns.md`
- **RPI Process**: `docs/RPI_PROCESS.md`

---

**Sprint Created:** 2025-11-25
**Sprint Owner:** Claude Code + Lonnie B
**Linear Issue:** [WHO-14](https://linear.app/hextrackr/issue/WHO-14)
**Target Version:** v1.4.0
**Status:** Ready to implement Phase 1
