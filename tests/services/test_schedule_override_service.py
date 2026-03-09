"""
Tests for ScheduleOverrideService.

Covers: create_override (with validation), cancel_override, get_override_by_id,
        get_override_display, get_all_active_overrides_map, get_paginated_overrides,
        complete_past_overrides
"""

import pytest
from datetime import datetime, timedelta
from pytz import timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models import TeamMember, Shift, Schedule
from src.services.schedule_override_service import ScheduleOverrideService

CHICAGO_TZ = timezone('America/Chicago')


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def service(db_session):
    return ScheduleOverrideService(db_session)


@pytest.fixture
def member_a(db_session):
    m = TeamMember(name="Alice", phone="+15551111111", is_active=True)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def member_b(db_session):
    m = TeamMember(name="Bob", phone="+15552222222", is_active=True)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def shift(db_session):
    s = Shift(shift_number=1, day_of_week="Monday", start_time="08:00:00", duration_hours=24)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def schedule(db_session, member_a, shift):
    now = datetime.now(CHICAGO_TZ)
    sched = Schedule(
        team_member_id=member_a.id,
        shift_id=shift.id,
        week_number=1,
        start_datetime=now + timedelta(hours=1),
        end_datetime=now + timedelta(hours=25),
        notified=False
    )
    db_session.add(sched)
    db_session.commit()
    db_session.refresh(sched)
    return sched


@pytest.fixture
def past_schedule(db_session, member_a, shift):
    now = datetime.now(CHICAGO_TZ)
    sched = Schedule(
        team_member_id=member_a.id,
        shift_id=shift.id,
        week_number=2,
        start_datetime=now - timedelta(hours=48),
        end_datetime=now - timedelta(hours=24),
        notified=True
    )
    db_session.add(sched)
    db_session.commit()
    db_session.refresh(sched)
    return sched


class TestCreateOverride:

    def test_valid_override_creates_successfully(self, service, schedule, member_b):
        override = service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="vacation",
            created_by="admin"
        )
        assert override.id is not None
        assert override.override_member_name == "Bob"
        assert override.original_member_name == "Alice"

    def test_schedule_not_found_raises_value_error(self, service, member_b):
        with pytest.raises(ValueError, match="Schedule not found"):
            service.create_override(
                schedule_id=99999,
                override_member_id=member_b.id,
                reason="test",
                created_by="admin"
            )

    def test_override_member_not_found_raises_value_error(self, service, schedule):
        with pytest.raises(ValueError, match="Team member not found"):
            service.create_override(
                schedule_id=schedule.id,
                override_member_id=99999,
                reason="test",
                created_by="admin"
            )

    def test_same_member_raises_value_error(self, service, schedule, member_a):
        with pytest.raises(ValueError, match="different from original"):
            service.create_override(
                schedule_id=schedule.id,
                override_member_id=member_a.id,
                reason="test",
                created_by="admin"
            )

    def test_duplicate_override_raises_value_error(self, service, schedule, member_b):
        service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="first",
            created_by="admin"
        )
        with pytest.raises(ValueError, match="Active override already exists"):
            service.create_override(
                schedule_id=schedule.id,
                override_member_id=member_b.id,
                reason="second",
                created_by="admin"
            )


class TestCancelOverride:

    def test_cancel_existing_override(self, service, schedule, member_b):
        override = service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="vacation",
            created_by="admin"
        )
        result = service.cancel_override(override.id)
        assert result is not None

    def test_cancel_nonexistent_returns_none(self, service):
        result = service.cancel_override(99999)
        assert result is None


class TestGetOverrideById:

    def test_returns_override_when_found(self, service, schedule, member_b):
        override = service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="test",
            created_by="admin"
        )
        result = service.get_override_by_id(override.id)
        assert result.id == override.id

    def test_returns_none_when_not_found(self, service):
        result = service.get_override_by_id(99999)
        assert result is None


class TestGetOverrideDisplay:

    def test_no_override_returns_none(self, service, schedule):
        result = service.get_override_display(schedule.id)
        assert result is None

    def test_active_override_returns_dict(self, service, schedule, member_b):
        service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="sick",
            created_by="admin"
        )
        result = service.get_override_display(schedule.id)
        assert result is not None
        assert result["original_member_name"] == "Alice"
        assert result["reason"] == "sick"
        assert result["created_by"] == "admin"


class TestGetAllActiveOverridesMap:

    def test_empty_returns_empty_dict(self, service):
        result = service.get_all_active_overrides_map()
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_active_override_in_map(self, service, schedule, member_b):
        override = service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="test",
            created_by="admin"
        )
        result = service.get_all_active_overrides_map()
        assert schedule.id in result


class TestGetPaginatedOverrides:

    def test_returns_empty_page_when_no_overrides(self, service):
        overrides, pagination = service.get_paginated_overrides()
        assert overrides == []
        assert pagination["total"] == 0
        assert pagination["page"] == 1

    def test_returns_pagination_metadata(self, service, schedule, member_b):
        service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="test",
            created_by="admin"
        )
        overrides, pagination = service.get_paginated_overrides(page=1, per_page=10)
        assert pagination["per_page"] == 10
        assert "has_next" in pagination
        assert "has_prev" in pagination


class TestGetByDateRange:

    def test_no_overrides_returns_empty(self, service):
        from datetime import datetime, timedelta
        now = datetime.now(CHICAGO_TZ)
        # Use the underlying repo directly via service
        result = service.override_repo.get_by_date_range(
            start_date=now - timedelta(days=7),
            end_date=now + timedelta(days=1)
        )
        assert result == []

    def test_override_in_range_returned(self, service, schedule, member_b):
        from datetime import datetime, timedelta
        service.create_override(
            schedule_id=schedule.id,
            override_member_id=member_b.id,
            reason="range test",
            created_by="admin"
        )
        # Use naive datetime — created_at column stores naive values
        now = datetime.utcnow()
        result = service.override_repo.get_by_date_range(
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1)
        )
        assert len(result) == 1


class TestCompletePastOverrides:

    def test_returns_count_of_completed(self, service):
        # No past overrides exist — should return 0
        count = service.complete_past_overrides()
        assert isinstance(count, int)
        assert count >= 0

    def test_completes_override_for_past_schedule(self, service, past_schedule, member_b, db_session):
        # Create an active override for a past schedule
        override = service.create_override(
            schedule_id=past_schedule.id,
            override_member_id=member_b.id,
            reason="past test",
            created_by="admin"
        )
        assert override.status == "active"
        count = service.complete_past_overrides()
        assert count >= 1
        db_session.refresh(override)
        assert override.status == "completed"
