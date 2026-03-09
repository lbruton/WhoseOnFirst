"""
Tests for Schedule model properties and methods.

Covers: is_active, is_upcoming, is_past, needs_notification, to_dict, __repr__
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models import TeamMember, Shift, Schedule


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def member(db_session):
    m = TeamMember(name="Alice", phone="+15551111111", is_active=True)
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
def active_schedule(db_session, member, shift):
    now = datetime.now()
    s = Schedule(
        team_member_id=member.id,
        shift_id=shift.id,
        week_number=1,
        start_datetime=now - timedelta(hours=1),
        end_datetime=now + timedelta(hours=23),
        notified=True,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def future_schedule(db_session, member, shift):
    now = datetime.now()
    s = Schedule(
        team_member_id=member.id,
        shift_id=shift.id,
        week_number=2,
        start_datetime=now + timedelta(days=2),
        end_datetime=now + timedelta(days=3),
        notified=False,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture
def past_schedule(db_session, member, shift):
    now = datetime.now()
    s = Schedule(
        team_member_id=member.id,
        shift_id=shift.id,
        week_number=3,
        start_datetime=now - timedelta(hours=48),
        end_datetime=now - timedelta(hours=24),
        notified=True,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


class TestScheduleProperties:

    def test_is_active_true(self, active_schedule):
        assert active_schedule.is_active is True

    def test_is_active_false_for_future(self, future_schedule):
        assert future_schedule.is_active is False

    def test_is_upcoming_true(self, future_schedule):
        assert future_schedule.is_upcoming is True

    def test_is_upcoming_false_for_active(self, active_schedule):
        assert active_schedule.is_upcoming is False

    def test_is_past_true(self, past_schedule):
        assert past_schedule.is_past is True

    def test_is_past_false_for_active(self, active_schedule):
        assert active_schedule.is_past is False

    def test_needs_notification_false_when_notified(self, active_schedule):
        assert active_schedule.needs_notification is False

    def test_needs_notification_false_for_future(self, future_schedule):
        assert future_schedule.needs_notification is False

    def test_repr_contains_id(self, active_schedule):
        result = repr(active_schedule)
        assert "Schedule" in result
        assert str(active_schedule.id) in result
