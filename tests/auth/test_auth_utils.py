"""
Tests for auth/utils.py

Covers: verify_password, authenticate_user, generate_session_token,
        create_session_cookie, get_current_user
"""

import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.user import User, UserRole
from src.auth.utils import (
    hash_password,
    verify_password,
    authenticate_user,
    generate_session_token,
    create_session_cookie,
    get_current_user,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """In-memory SQLite session for auth tests."""
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
def active_user(db_session):
    """Create and persist an active user with a known password."""
    user = User(
        username="testuser",
        password_hash=hash_password("correct-password"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session):
    """Create and persist an inactive user."""
    user = User(
        username="inactive",
        password_hash=hash_password("some-password"),
        role=UserRole.VIEWER,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------

class TestVerifyPassword:

    def test_correct_password_returns_true(self):
        hashed = hash_password("my-secret")
        assert verify_password("my-secret", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("my-secret")
        assert verify_password("wrong-password", hashed) is False

    def test_invalid_hash_returns_false(self):
        # Should catch InvalidHash and return False, not raise
        assert verify_password("any-password", "not-a-valid-hash") is False


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------

class TestAuthenticateUser:

    def test_valid_credentials_returns_user(self, db_session, active_user):
        result = authenticate_user(db_session, "testuser", "correct-password")
        assert result is not None
        assert result.username == "testuser"

    def test_wrong_username_returns_none(self, db_session, active_user):
        result = authenticate_user(db_session, "nonexistent", "correct-password")
        assert result is None

    def test_wrong_password_returns_none(self, db_session, active_user):
        result = authenticate_user(db_session, "testuser", "wrong-password")
        assert result is None

    def test_inactive_user_returns_none(self, db_session, inactive_user):
        result = authenticate_user(db_session, "inactive", "some-password")
        assert result is None


# ---------------------------------------------------------------------------
# generate_session_token
# ---------------------------------------------------------------------------

class TestGenerateSessionToken:

    def test_returns_non_empty_string(self):
        token = generate_session_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_tokens_are_unique(self):
        token1 = generate_session_token()
        token2 = generate_session_token()
        assert token1 != token2


# ---------------------------------------------------------------------------
# create_session_cookie
# ---------------------------------------------------------------------------

class TestCreateSessionCookie:

    def test_no_remember_me_expires_in_24_hours(self):
        before = datetime.utcnow()
        cookie = create_session_cookie(user_id=1, remember_me=False)
        after = datetime.utcnow()

        assert cookie["user_id"] == 1
        expires = datetime.fromisoformat(cookie["expires_at"])
        # Should be approximately 24h from now
        assert expires > before + timedelta(hours=23, minutes=59)
        assert expires < after + timedelta(hours=24, minutes=1)

    def test_remember_me_expires_in_30_days(self):
        before = datetime.utcnow()
        cookie = create_session_cookie(user_id=42, remember_me=True)
        after = datetime.utcnow()

        assert cookie["user_id"] == 42
        expires = datetime.fromisoformat(cookie["expires_at"])
        # Should be approximately 30 days from now
        assert expires > before + timedelta(days=29, hours=23)
        assert expires < after + timedelta(days=30, minutes=1)


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:

    def test_valid_user_id_returns_user(self, db_session, active_user):
        result = get_current_user(db_session, active_user.id)
        assert result.id == active_user.id
        assert result.username == "testuser"

    def test_nonexistent_user_raises_401(self, db_session):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db_session, 99999)
        assert exc_info.value.status_code == 401
        assert "not found" in exc_info.value.detail.lower()

    def test_inactive_user_raises_401(self, db_session, inactive_user):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db_session, inactive_user.id)
        assert exc_info.value.status_code == 401
        assert "inactive" in exc_info.value.detail.lower()
