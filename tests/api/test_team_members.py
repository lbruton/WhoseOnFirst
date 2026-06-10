"""
Team Members API endpoint tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.team_member import TeamMember


class TestListTeamMembers:
    """Tests for GET /api/v1/team-members/"""

    def test_list_empty(self, client: TestClient):
        """Test listing team members when database is empty."""
        response = client.get("/api/v1/team-members/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_all_members(self, client: TestClient, db_session: Session):
        """Test listing all team members."""
        # Create test data
        member1 = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        member2 = TeamMember(name="Jane Smith", phone="+15559876543", is_active=False)
        db_session.add_all([member1, member2])
        db_session.commit()

        response = client.get("/api/v1/team-members/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "John Doe"
        assert data[1]["name"] == "Jane Smith"

    def test_list_active_only(self, client: TestClient, db_session: Session):
        """Test listing only active team members."""
        # Create test data
        member1 = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        member2 = TeamMember(name="Jane Smith", phone="+15559876543", is_active=False)
        db_session.add_all([member1, member2])
        db_session.commit()

        response = client.get("/api/v1/team-members/?active_only=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "John Doe"
        assert data[0]["is_active"] is True


class TestGetTeamMember:
    """Tests for GET /api/v1/team-members/{id}"""

    def test_get_existing_member(self, client: TestClient, db_session: Session):
        """Test getting an existing team member."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        response = client.get(f"/api/v1/team-members/{member.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == member.id
        assert data["name"] == "John Doe"
        assert data["phone"] == "+15551234567"
        assert data["is_active"] is True

    def test_get_nonexistent_member(self, client: TestClient):
        """Test getting a member that doesn't exist."""
        response = client.get("/api/v1/team-members/999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCreateTeamMember:
    """Tests for POST /api/v1/team-members/"""

    def test_create_valid_member(self, client: TestClient):
        """Test creating a valid team member."""
        member_data = {
            "name": "John Doe",
            "phone": "+15551234567"
        }
        response = client.post("/api/v1/team-members/", json=member_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "John Doe"
        assert data["phone"] == "+15551234567"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_invalid_phone_format(self, client: TestClient):
        """Test creating member with invalid phone format."""
        member_data = {
            "name": "John Doe",
            "phone": "555-1234"  # Invalid format
        }
        response = client.post("/api/v1/team-members/", json=member_data)
        assert response.status_code == 422  # Pydantic validation error

    def test_create_missing_name(self, client: TestClient):
        """Test creating member without name."""
        member_data = {
            "phone": "+15551234567"
        }
        response = client.post("/api/v1/team-members/", json=member_data)
        assert response.status_code == 422  # Pydantic validation error

    def test_create_empty_name(self, client: TestClient):
        """Test creating member with empty name."""
        member_data = {
            "name": "   ",  # Whitespace only
            "phone": "+15551234567"
        }
        response = client.post("/api/v1/team-members/", json=member_data)
        assert response.status_code == 422  # Pydantic validation error


class TestWeeklyDigestOptin:
    """WOF-10: per-member Monday weekly-digest opt-in flag."""

    def test_create_defaults_to_false(self, client: TestClient):
        """Omitting the flag creates a member opted out of the digest."""
        response = client.post(
            "/api/v1/team-members/",
            json={"name": "Default Dana", "phone": "+15553330001"}
        )
        assert response.status_code == 201
        assert response.json()["weekly_digest_optin"] is False

    def test_create_with_optin_true(self, client: TestClient):
        """The flag can be set at creation time."""
        response = client.post(
            "/api/v1/team-members/",
            json={
                "name": "Digest Dave",
                "phone": "+15553330002",
                "weekly_digest_optin": True
            }
        )
        assert response.status_code == 201
        assert response.json()["weekly_digest_optin"] is True

    def test_update_toggles_optin(self, client: TestClient, db_session: Session):
        """The flag can be toggled via PUT."""
        member = TeamMember(name="Toggle Tom", phone="+15553330003", is_active=True)
        db_session.add(member)
        db_session.commit()

        response = client.put(
            f"/api/v1/team-members/{member.id}",
            json={"weekly_digest_optin": True}
        )
        assert response.status_code == 200
        assert response.json()["weekly_digest_optin"] is True

        response = client.put(
            f"/api/v1/team-members/{member.id}",
            json={"weekly_digest_optin": False}
        )
        assert response.status_code == 200
        assert response.json()["weekly_digest_optin"] is False


class TestUpdateTeamMember:
    """Tests for PUT /api/v1/team-members/{id}"""

    def test_update_name(self, client: TestClient, db_session: Session):
        """Test updating team member name."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        update_data = {"name": "John Smith"}
        response = client.put(f"/api/v1/team-members/{member.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "John Smith"
        assert data["phone"] == "+15551234567"  # Unchanged

    def test_update_phone(self, client: TestClient, db_session: Session):
        """Test updating team member phone."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        update_data = {"phone": "+15559876543"}
        response = client.put(f"/api/v1/team-members/{member.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "+15559876543"
        assert data["name"] == "John Doe"  # Unchanged

    def test_update_both_fields(self, client: TestClient, db_session: Session):
        """Test updating both name and phone."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        update_data = {
            "name": "Jane Doe",
            "phone": "+15559876543"
        }
        response = client.put(f"/api/v1/team-members/{member.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Jane Doe"
        assert data["phone"] == "+15559876543"

    def test_update_nonexistent_member(self, client: TestClient):
        """Test updating a member that doesn't exist."""
        update_data = {"name": "John Smith"}
        response = client.put("/api/v1/team-members/999", json=update_data)
        assert response.status_code == 404


class TestDeactivateTeamMember:
    """Tests for DELETE /api/v1/team-members/{id}"""

    def test_deactivate_active_member(self, client: TestClient, db_session: Session):
        """Test deactivating an active team member."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        response = client.delete(f"/api/v1/team-members/{member.id}")
        assert response.status_code == 204

        # Verify member is deactivated
        db_session.refresh(member)
        assert member.is_active is False

    def test_deactivate_inactive_member(self, client: TestClient, db_session: Session):
        """Test deactivating an already inactive member."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=False)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        response = client.delete(f"/api/v1/team-members/{member.id}")
        assert response.status_code == 204

        # Verify member remains inactive
        db_session.refresh(member)
        assert member.is_active is False

    def test_deactivate_nonexistent_member(self, client: TestClient):
        """Test deactivating a member that doesn't exist."""
        response = client.delete("/api/v1/team-members/999")
        assert response.status_code == 404


class TestActivateTeamMember:
    """Tests for POST /api/v1/team-members/{id}/activate"""

    def test_activate_inactive_member(self, client: TestClient, db_session: Session):
        """Test activating an inactive team member."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=False)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        response = client.post(f"/api/v1/team-members/{member.id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

        # Verify in database
        db_session.refresh(member)
        assert member.is_active is True

    def test_activate_active_member(self, client: TestClient, db_session: Session):
        """Test activating an already active member."""
        member = TeamMember(name="John Doe", phone="+15551234567", is_active=True)
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        response = client.post(f"/api/v1/team-members/{member.id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_activate_nonexistent_member(self, client: TestClient):
        """Test activating a member that doesn't exist."""
        response = client.post("/api/v1/team-members/999/activate")
        assert response.status_code == 404


class TestTeamMemberIntegration:
    """Integration tests for team member workflows."""

    def test_full_lifecycle(self, client: TestClient, db_session: Session):
        """Test complete team member lifecycle: create -> update -> deactivate -> activate."""
        # Create
        create_data = {
            "name": "John Doe",
            "phone": "+15551234567"
        }
        response = client.post("/api/v1/team-members/", json=create_data)
        assert response.status_code == 201
        member_id = response.json()["id"]

        # Read
        response = client.get(f"/api/v1/team-members/{member_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "John Doe"

        # Update
        update_data = {"name": "John Smith"}
        response = client.put(f"/api/v1/team-members/{member_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["name"] == "John Smith"

        # Deactivate
        response = client.delete(f"/api/v1/team-members/{member_id}")
        assert response.status_code == 204

        # Verify deactivated (should not appear in active list)
        response = client.get("/api/v1/team-members/?active_only=true")
        assert response.status_code == 200
        assert len(response.json()) == 0

        # Activate
        response = client.post(f"/api/v1/team-members/{member_id}/activate")
        assert response.status_code == 200
        assert response.json()["is_active"] is True

        # Verify activated (should appear in active list)
        response = client.get("/api/v1/team-members/?active_only=true")
        assert response.status_code == 200
        assert len(response.json()) == 1
