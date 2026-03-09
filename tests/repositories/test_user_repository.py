"""
Tests for UserRepository.

Covers: get_active_users, get_by_role, activate, deactivate, update_password
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.user import User, UserRole
from src.repositories.user_repository import UserRepository
from src.auth.utils import hash_password


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
def repo(db_session):
    return UserRepository(db_session)


@pytest.fixture
def admin_user(db_session):
    user = User(
        username="admin",
        password_hash=hash_password("admin-pass"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session):
    user = User(
        username="viewer",
        password_hash=hash_password("viewer-pass"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session):
    user = User(
        username="olduser",
        password_hash=hash_password("old-pass"),
        role=UserRole.VIEWER,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestGetActiveUsers:

    def test_returns_only_active_users(self, repo, admin_user, viewer_user, inactive_user):
        active = repo.get_active_users()
        usernames = [u.username for u in active]
        assert "admin" in usernames
        assert "viewer" in usernames
        assert "olduser" not in usernames

    def test_empty_db_returns_empty_list(self, repo):
        assert repo.get_active_users() == []


class TestGetByRole:

    def test_returns_admin_users(self, repo, admin_user, viewer_user):
        admins = repo.get_by_role(UserRole.ADMIN)
        assert len(admins) == 1
        assert admins[0].username == "admin"

    def test_returns_viewer_users(self, repo, admin_user, viewer_user):
        viewers = repo.get_by_role(UserRole.VIEWER)
        assert len(viewers) == 1
        assert viewers[0].username == "viewer"

    def test_no_matching_role_returns_empty(self, repo, viewer_user):
        admins = repo.get_by_role(UserRole.ADMIN)
        assert admins == []


class TestActivate:

    def test_activate_inactive_user(self, repo, inactive_user):
        result = repo.activate(inactive_user.id)
        assert result.is_active is True

    def test_activate_nonexistent_returns_none(self, repo):
        result = repo.activate(99999)
        assert result is None


class TestDeactivate:

    def test_deactivate_active_user(self, repo, admin_user):
        result = repo.deactivate(admin_user.id)
        assert result.is_active is False

    def test_deactivate_nonexistent_returns_none(self, repo):
        result = repo.deactivate(99999)
        assert result is None


class TestUpdatePassword:

    def test_updates_password_hash(self, repo, admin_user):
        new_hash = hash_password("new-password")
        result = repo.update_password(admin_user.id, new_hash)
        assert result.password_hash == new_hash

    def test_nonexistent_user_returns_none(self, repo):
        result = repo.update_password(99999, "some-hash")
        assert result is None
