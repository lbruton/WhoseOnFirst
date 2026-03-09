"""
Tests for TeamMemberRepository.

Tests all team member-specific operations including phone validation,
active/inactive queries, and soft delete functionality.
"""

import pytest
from src.repositories import TeamMemberRepository


class TestTeamMemberRepositoryCreate:
    """Tests for creating team members."""

    def test_create_team_member_success(self, team_member_repo, sample_team_member_data):
        """Test successful team member creation."""
        member = team_member_repo.create(sample_team_member_data)

        assert member.id is not None
        assert member.name == sample_team_member_data["name"]
        assert member.phone == sample_team_member_data["phone"]
        assert member.is_active is True
        assert member.created_at is not None
        assert member.updated_at is not None

    def test_create_duplicate_phone_fails(self, team_member_repo, sample_team_member_data):
        """Test that creating member with duplicate phone number fails."""
        team_member_repo.create(sample_team_member_data)

        with pytest.raises(Exception):
            team_member_repo.create(sample_team_member_data)

    def test_create_inactive_member(self, team_member_repo, sample_team_member_data):
        """Test creating an inactive team member."""
        sample_team_member_data["is_active"] = False
        member = team_member_repo.create(sample_team_member_data)

        assert member.is_active is False


class TestTeamMemberRepositoryRead:
    """Tests for reading/querying team members."""

    def test_get_by_id(self, team_member_repo, sample_team_member_data):
        """Test retrieving team member by ID."""
        created = team_member_repo.create(sample_team_member_data)
        retrieved = team_member_repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, team_member_repo):
        """Test retrieving non-existent team member returns None."""
        result = team_member_repo.get_by_id(99999)
        assert result is None

    def test_get_all(self, team_member_repo, populated_team_members):
        """Test retrieving all team members."""
        members = team_member_repo.get_all()

        assert len(members) == len(populated_team_members)

    def test_get_all_with_pagination(self, team_member_repo, populated_team_members):
        """Test pagination in get_all."""
        page1 = team_member_repo.get_all(skip=0, limit=2)
        page2 = team_member_repo.get_all(skip=2, limit=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    def test_get_active(self, team_member_repo, populated_team_members):
        """Test retrieving only active team members."""
        active_members = team_member_repo.get_active()

        assert len(active_members) == 4  # 4 out of 5 are active in fixture
        assert all(m.is_active for m in active_members)

    def test_get_inactive(self, team_member_repo, populated_team_members):
        """Test retrieving only inactive team members."""
        inactive_members = team_member_repo.get_inactive()

        assert len(inactive_members) == 1
        assert all(not m.is_active for m in inactive_members)

    def test_get_by_phone(self, team_member_repo, sample_team_member_data):
        """Test retrieving team member by phone number."""
        created = team_member_repo.create(sample_team_member_data)
        retrieved = team_member_repo.get_by_phone(sample_team_member_data["phone"])

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.phone == created.phone

    def test_get_by_phone_not_found(self, team_member_repo):
        """Test retrieving by non-existent phone returns None."""
        result = team_member_repo.get_by_phone("+15559999999")
        assert result is None


class TestTeamMemberRepositoryUpdate:
    """Tests for updating team members."""

    def test_update_name(self, team_member_repo, sample_team_member_data):
        """Test updating team member name."""
        member = team_member_repo.create(sample_team_member_data)
        updated = team_member_repo.update(member.id, {"name": "Jane Doe"})

        assert updated.name == "Jane Doe"
        assert updated.phone == member.phone  # Unchanged

    def test_update_phone(self, team_member_repo, sample_team_member_data):
        """Test updating team member phone number."""
        member = team_member_repo.create(sample_team_member_data)
        new_phone = "+15559876543"
        updated = team_member_repo.update(member.id, {"phone": new_phone})

        assert updated.phone == new_phone

    def test_update_non_existent(self, team_member_repo):
        """Test updating non-existent member returns None."""
        result = team_member_repo.update(99999, {"name": "Ghost"})
        assert result is None


class TestTeamMemberRepositoryDelete:
    """Tests for deleting team members."""

    def test_delete_success(self, team_member_repo, sample_team_member_data):
        """Test successful team member deletion."""
        member = team_member_repo.create(sample_team_member_data)
        result = team_member_repo.delete(member.id)

        assert result is True
        assert team_member_repo.get_by_id(member.id) is None

    def test_delete_non_existent(self, team_member_repo):
        """Test deleting non-existent member returns False."""
        result = team_member_repo.delete(99999)
        assert result is False


class TestTeamMemberRepositorySoftDelete:
    """Tests for soft delete (deactivate/activate) functionality."""

    def test_deactivate_member(self, team_member_repo, sample_team_member_data):
        """Test deactivating a team member."""
        member = team_member_repo.create(sample_team_member_data)
        deactivated = team_member_repo.deactivate(member.id)

        assert deactivated.is_active is False
        assert deactivated.id == member.id

    def test_activate_member(self, team_member_repo, sample_team_member_data):
        """Test activating a team member."""
        sample_team_member_data["is_active"] = False
        member = team_member_repo.create(sample_team_member_data)

        activated = team_member_repo.activate(member.id)

        assert activated.is_active is True
        assert activated.id == member.id

    def test_deactivate_non_existent(self, team_member_repo):
        """Test deactivating non-existent member returns None."""
        result = team_member_repo.deactivate(99999)
        assert result is None

    def test_activate_non_existent(self, team_member_repo):
        """Test activating non-existent member returns None."""
        result = team_member_repo.activate(99999)
        assert result is None


class TestTeamMemberRepositoryValidation:
    """Tests for phone validation and existence checks."""

    def test_phone_exists_true(self, team_member_repo, sample_team_member_data):
        """Test phone_exists returns True for existing phone."""
        team_member_repo.create(sample_team_member_data)
        exists = team_member_repo.phone_exists(sample_team_member_data["phone"])

        assert exists is True

    def test_phone_exists_false(self, team_member_repo):
        """Test phone_exists returns False for non-existent phone."""
        exists = team_member_repo.phone_exists("+15559999999")
        assert exists is False

    def test_phone_exists_with_exclusion(self, team_member_repo, sample_team_member_data):
        """Test phone_exists with ID exclusion for updates."""
        member = team_member_repo.create(sample_team_member_data)

        # Should return False when excluding the member's own ID
        exists = team_member_repo.phone_exists(
            sample_team_member_data["phone"],
            exclude_id=member.id
        )
        assert exists is False

        # Create another member
        other_data = sample_team_member_data.copy()
        other_data["phone"] = "+15559876543"
        other_member = team_member_repo.create(other_data)

        # Should return True for other member's phone
        exists = team_member_repo.phone_exists(
            other_data["phone"],
            exclude_id=member.id
        )
        assert exists is True


class TestTeamMemberRepositoryQueries:
    """Tests for specialized query methods."""

    def test_get_count_active(self, team_member_repo, populated_team_members):
        """Test counting active team members."""
        count = team_member_repo.get_count_active()
        assert count == 4  # 4 active members in fixture

    def test_search_by_name_exact(self, team_member_repo, populated_team_members):
        """Test searching by exact name match."""
        results = team_member_repo.search_by_name("Alice Smith")

        assert len(results) == 1
        assert results[0].name == "Alice Smith"

    def test_search_by_name_partial(self, team_member_repo, populated_team_members):
        """Test searching by partial name match."""
        results = team_member_repo.search_by_name("Smith")

        assert len(results) == 1
        assert "Smith" in results[0].name

    def test_search_by_name_case_insensitive(self, team_member_repo, populated_team_members):
        """Test searching is case-insensitive."""
        results = team_member_repo.search_by_name("alice")

        assert len(results) == 1
        assert results[0].name == "Alice Smith"

    def test_search_by_name_no_results(self, team_member_repo, populated_team_members):
        """Test searching returns empty list when no matches."""
        results = team_member_repo.search_by_name("Nonexistent")
        assert len(results) == 0


class TestTeamMemberRepositoryCount:
    """Tests for count and exists methods."""

    def test_count(self, team_member_repo, populated_team_members):
        """Test counting total team members."""
        count = team_member_repo.count()
        assert count == len(populated_team_members)

    def test_exists_true(self, team_member_repo, sample_team_member_data):
        """Test exists returns True for existing member."""
        member = team_member_repo.create(sample_team_member_data)
        exists = team_member_repo.exists(member.id)
        assert exists is True

    def test_exists_false(self, team_member_repo):
        """Test exists returns False for non-existent member."""
        exists = team_member_repo.exists(99999)
        assert exists is False


class TestTeamMemberRepositoryRotation:
    """Tests for rotation order methods."""

    def test_get_max_rotation_order_empty(self, team_member_repo):
        result = team_member_repo.get_max_rotation_order()
        assert result == 0

    def test_get_max_rotation_order_with_members(self, team_member_repo, populated_team_members):
        result = team_member_repo.get_max_rotation_order()
        assert isinstance(result, int)

    def test_update_rotation_orders(self, team_member_repo, populated_team_members):
        order_map = {m.id: i for i, m in enumerate(populated_team_members)}
        updated = team_member_repo.update_rotation_orders(order_map)
        assert len(updated) == len(populated_team_members)
        for i, m in enumerate(updated):
            assert m.rotation_order is not None

    def test_update_rotation_orders_ignores_missing_id(self, team_member_repo, populated_team_members):
        order_map = {99999: 5}
        updated = team_member_repo.update_rotation_orders(order_map)
        assert updated == []

    def test_get_ordered_for_rotation_active_only(self, team_member_repo, populated_team_members):
        results = team_member_repo.get_ordered_for_rotation(active_only=True)
        assert all(m.is_active for m in results)

    def test_get_ordered_for_rotation_all_members(self, team_member_repo, populated_team_members):
        results = team_member_repo.get_ordered_for_rotation(active_only=False)
        assert len(results) >= len(populated_team_members)
