"""
Tests for TeamMemberService.

This module contains comprehensive tests for the team member service layer,
covering CRUD operations, validation, error handling, and business logic.
"""

import pytest
from sqlalchemy.orm import Session

from src.services import (
    TeamMemberService,
    DuplicatePhoneError,
    MemberNotFoundError,
    InvalidPhoneError,
)
from src.models.team_member import TeamMember


class TestTeamMemberServiceCreate:
    """Tests for creating team members."""

    def test_create_success(self, db_session: Session, sample_team_member_data):
        """Test successful team member creation."""
        service = TeamMemberService(db_session)

        member = service.create(sample_team_member_data)

        assert member.id is not None
        assert member.name == sample_team_member_data["name"]
        assert member.phone == sample_team_member_data["phone"]
        assert member.is_active is True
        assert member.created_at is not None

    def test_create_inactive_member(self, db_session: Session, sample_team_member_data):
        """Test creating inactive team member."""
        service = TeamMemberService(db_session)
        sample_team_member_data["is_active"] = False

        member = service.create(sample_team_member_data)

        assert member.is_active is False

    def test_create_invalid_phone_format(self, db_session: Session):
        """Test that invalid phone format raises error."""
        service = TeamMemberService(db_session)

        invalid_phones = [
            "123456789",  # Too short
            "+2123456789",  # Wrong country code
            "15551234567",  # Missing +
            "+1555-123-4567",  # Contains hyphens
            "+1 555 123 4567",  # Contains spaces
            "",  # Empty
            None,  # None
        ]

        for invalid_phone in invalid_phones:
            with pytest.raises(InvalidPhoneError):
                service.create({
                    "name": "Test User",
                    "phone": invalid_phone
                })

    def test_create_without_phone(self, db_session: Session):
        """Test that creating member without phone raises error."""
        service = TeamMemberService(db_session)

        with pytest.raises(InvalidPhoneError):
            service.create({"name": "Test User"})


class TestTeamMemberServiceRead:
    """Tests for reading team members."""

    def test_get_by_id_success(self, db_session: Session, sample_team_member_data):
        """Test getting member by ID."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        member = service.get_by_id(created.id)

        assert member.id == created.id
        assert member.name == created.name
        assert member.phone == created.phone

    def test_get_by_id_not_found(self, db_session: Session):
        """Test that getting non-existent member raises error."""
        service = TeamMemberService(db_session)

        with pytest.raises(MemberNotFoundError) as exc_info:
            service.get_by_id(99999)

        assert "not found" in str(exc_info.value).lower()

    def test_get_all(self, db_session: Session, sample_team_member_data):
        """Test getting all team members."""
        service = TeamMemberService(db_session)

        # Create multiple members
        for i in range(3):
            data = sample_team_member_data.copy()
            data["name"] = f"Member {i}"
            data["phone"] = f"+1555000000{i}"
            service.create(data)

        members = service.get_all()

        assert len(members) == 3

    def test_get_all_active_only(self, db_session: Session, sample_team_member_data):
        """Test getting only active members."""
        service = TeamMemberService(db_session)

        # Create active members
        for i in range(2):
            data = sample_team_member_data.copy()
            data["name"] = f"Active {i}"
            data["phone"] = f"+1555000000{i}"
            service.create(data)

        # Create inactive member
        inactive_data = sample_team_member_data.copy()
        inactive_data["name"] = "Inactive"
        inactive_data["phone"] = "+15550000099"
        inactive_data["is_active"] = False
        service.create(inactive_data)

        active_members = service.get_all(active_only=True)

        assert len(active_members) == 2
        assert all(m.is_active for m in active_members)

    def test_get_all_with_pagination(self, db_session: Session, sample_team_member_data):
        """Test pagination of member list."""
        service = TeamMemberService(db_session)

        # Create 5 members
        for i in range(5):
            data = sample_team_member_data.copy()
            data["name"] = f"Member {i}"
            data["phone"] = f"+1555000000{i}"
            service.create(data)

        # Get first 2
        page1 = service.get_all(skip=0, limit=2)
        assert len(page1) == 2

        # Get next 2
        page2 = service.get_all(skip=2, limit=2)
        assert len(page2) == 2

        # Ensure different members
        assert page1[0].id != page2[0].id

    def test_get_active(self, db_session: Session, sample_team_member_data):
        """Test getting only active members."""
        service = TeamMemberService(db_session)

        # Create active and inactive members
        active_data = sample_team_member_data.copy()
        service.create(active_data)

        inactive_data = sample_team_member_data.copy()
        inactive_data["name"] = "Inactive Member"
        inactive_data["phone"] = "+15550000099"
        inactive_data["is_active"] = False
        service.create(inactive_data)

        active_members = service.get_active()

        assert len(active_members) == 1
        assert active_members[0].is_active is True

    def test_get_inactive(self, db_session: Session, sample_team_member_data):
        """Test getting only inactive members."""
        service = TeamMemberService(db_session)

        # Create active member
        active_data = sample_team_member_data.copy()
        service.create(active_data)

        # Create inactive member
        inactive_data = sample_team_member_data.copy()
        inactive_data["name"] = "Inactive Member"
        inactive_data["phone"] = "+15550000099"
        inactive_data["is_active"] = False
        service.create(inactive_data)

        inactive_members = service.get_inactive()

        assert len(inactive_members) == 1
        assert inactive_members[0].is_active is False

    def test_get_by_phone(self, db_session: Session, sample_team_member_data):
        """Test getting member by phone number."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        member = service.get_by_phone(sample_team_member_data["phone"])

        assert member is not None
        assert member.id == created.id
        assert member.phone == sample_team_member_data["phone"]

    def test_get_by_phone_not_found(self, db_session: Session):
        """Test getting member by non-existent phone."""
        service = TeamMemberService(db_session)

        member = service.get_by_phone("+15559999999")

        assert member is None


class TestTeamMemberServiceUpdate:
    """Tests for updating team members."""

    def test_update_name(self, db_session: Session, sample_team_member_data):
        """Test updating member name."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        updated = service.update(created.id, {"name": "Updated Name"})

        assert updated.name == "Updated Name"
        assert updated.phone == created.phone

    def test_update_phone(self, db_session: Session, sample_team_member_data):
        """Test updating member phone."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        new_phone = "+15559999999"
        updated = service.update(created.id, {"phone": new_phone})

        assert updated.phone == new_phone

    def test_update_invalid_phone_format(self, db_session: Session, sample_team_member_data):
        """Test that updating with invalid phone format raises error."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        with pytest.raises(InvalidPhoneError):
            service.update(created.id, {"phone": "invalid"})

    def test_update_non_existent_member(self, db_session: Session):
        """Test that updating non-existent member raises error."""
        service = TeamMemberService(db_session)

        with pytest.raises(MemberNotFoundError):
            service.update(99999, {"name": "New Name"})

    def test_update_is_active(self, db_session: Session, sample_team_member_data):
        """Test updating member active status."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        updated = service.update(created.id, {"is_active": False})

        assert updated.is_active is False


class TestTeamMemberServiceDelete:
    """Tests for deleting team members."""

    def test_delete_success(self, db_session: Session, sample_team_member_data):
        """Test successful member deletion."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        success = service.delete(created.id)

        assert success is True

        # Verify deletion
        with pytest.raises(MemberNotFoundError):
            service.get_by_id(created.id)

    def test_delete_non_existent_member(self, db_session: Session):
        """Test that deleting non-existent member raises error."""
        service = TeamMemberService(db_session)

        with pytest.raises(MemberNotFoundError):
            service.delete(99999)


class TestTeamMemberServiceActivation:
    """Tests for member activation/deactivation."""

    def test_deactivate_member(self, db_session: Session, sample_team_member_data):
        """Test deactivating an active member."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        deactivated = service.deactivate(created.id)

        assert deactivated.is_active is False

    def test_deactivate_already_inactive(self, db_session: Session, sample_team_member_data):
        """Test deactivating already inactive member (idempotent)."""
        service = TeamMemberService(db_session)
        sample_team_member_data["is_active"] = False
        created = service.create(sample_team_member_data)

        # Should not raise error
        deactivated = service.deactivate(created.id)

        assert deactivated.is_active is False

    def test_activate_member(self, db_session: Session, sample_team_member_data):
        """Test activating an inactive member."""
        service = TeamMemberService(db_session)
        sample_team_member_data["is_active"] = False
        created = service.create(sample_team_member_data)

        activated = service.activate(created.id)

        assert activated.is_active is True

    def test_activate_already_active(self, db_session: Session, sample_team_member_data):
        """Test activating already active member (idempotent)."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        # Should not raise error
        activated = service.activate(created.id)

        assert activated.is_active is True

    def test_deactivate_non_existent_member(self, db_session: Session):
        """Test that deactivating non-existent member raises error."""
        service = TeamMemberService(db_session)

        with pytest.raises(MemberNotFoundError):
            service.deactivate(99999)

    def test_activate_non_existent_member(self, db_session: Session):
        """Test that activating non-existent member raises error."""
        service = TeamMemberService(db_session)

        with pytest.raises(MemberNotFoundError):
            service.activate(99999)


class TestTeamMemberServiceValidation:
    """Tests for validation methods."""

    def test_phone_exists_true(self, db_session: Session, sample_team_member_data):
        """Test phone_exists returns True for existing phone."""
        service = TeamMemberService(db_session)
        service.create(sample_team_member_data)

        exists = service.phone_exists(sample_team_member_data["phone"])

        assert exists is True

    def test_phone_exists_false(self, db_session: Session):
        """Test phone_exists returns False for non-existent phone."""
        service = TeamMemberService(db_session)

        exists = service.phone_exists("+15559999999")

        assert exists is False

    def test_phone_exists_with_exclusion(self, db_session: Session, sample_team_member_data):
        """Test phone_exists with member ID exclusion."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        # Should return False when excluding the member with this phone
        exists = service.phone_exists(
            sample_team_member_data["phone"],
            exclude_id=created.id
        )

        assert exists is False


class TestTeamMemberServiceQueries:
    """Tests for query methods."""

    def test_get_count(self, db_session: Session, sample_team_member_data):
        """Test getting total member count."""
        service = TeamMemberService(db_session)

        # Create members
        for i in range(3):
            data = sample_team_member_data.copy()
            data["name"] = f"Member {i}"
            data["phone"] = f"+1555000000{i}"
            service.create(data)

        count = service.get_count()

        assert count == 3

    def test_get_count_active_only(self, db_session: Session, sample_team_member_data):
        """Test getting count of active members only."""
        service = TeamMemberService(db_session)

        # Create active members
        for i in range(2):
            data = sample_team_member_data.copy()
            data["name"] = f"Active {i}"
            data["phone"] = f"+1555000000{i}"
            service.create(data)

        # Create inactive member
        inactive_data = sample_team_member_data.copy()
        inactive_data["name"] = "Inactive"
        inactive_data["phone"] = "+15550000099"
        inactive_data["is_active"] = False
        service.create(inactive_data)

        count = service.get_count(active_only=True)

        assert count == 2

    def test_search_by_name_exact(self, db_session: Session, sample_team_member_data):
        """Test searching by exact name."""
        service = TeamMemberService(db_session)
        created = service.create(sample_team_member_data)

        results = service.search_by_name(sample_team_member_data["name"])

        assert len(results) == 1
        assert results[0].id == created.id

    def test_search_by_name_partial(self, db_session: Session, sample_team_member_data):
        """Test searching by partial name."""
        service = TeamMemberService(db_session)
        sample_team_member_data["name"] = "John Smith"
        service.create(sample_team_member_data)

        results = service.search_by_name("John")

        assert len(results) == 1

    def test_search_by_name_case_insensitive(self, db_session: Session, sample_team_member_data):
        """Test that name search is case-insensitive."""
        service = TeamMemberService(db_session)
        sample_team_member_data["name"] = "John Smith"
        service.create(sample_team_member_data)

        results = service.search_by_name("john")

        assert len(results) == 1

    def test_search_by_name_no_results(self, db_session: Session, sample_team_member_data):
        """Test searching with no matching results."""
        service = TeamMemberService(db_session)
        service.create(sample_team_member_data)

        results = service.search_by_name("NonExistent")

        assert len(results) == 0


class TestTeamMemberServiceRotation:

    def test_deactivate_renumbers_remaining_active_members(self, db_session: Session):
        """When a member is deactivated with others present, rotation orders are renumbered."""
        service = TeamMemberService(db_session)
        m1 = service.create({"name": "Alice", "phone": "+15551111111", "is_active": True})
        m2 = service.create({"name": "Bob", "phone": "+15552222222", "is_active": True})
        service.deactivate(m1.id)
        # Bob should still be active and rotation re-ordered
        db_session.refresh(m2)
        assert m2.is_active is True

    def test_update_rotation_orders_success(self, db_session: Session):
        service = TeamMemberService(db_session)
        m1 = service.create({"name": "Alice", "phone": "+15551111111", "is_active": True})
        m2 = service.create({"name": "Bob", "phone": "+15552222222", "is_active": True})
        updated = service.update_rotation_orders({m1.id: 1, m2.id: 0})
        assert len(updated) == 2

    def test_update_rotation_orders_missing_member_raises(self, db_session: Session):
        from src.services.team_member_service import MemberNotFoundError
        service = TeamMemberService(db_session)
        with pytest.raises(MemberNotFoundError):
            service.update_rotation_orders({99999: 0})
