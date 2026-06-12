"""
TeamMember model for WhoseOnFirst.

Represents a team member who can be assigned to on-call shifts.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class TeamMember(Base):
    """
    Team member model.

    Attributes:
        id: Primary key
        name: Full name of team member
        phone: Phone number in E.164 format (+1XXXXXXXXXX)
        secondary_phone: Optional secondary phone for dual-device paging
        is_active: Whether member is currently active in rotation
        rotation_order: Position in rotation sequence (lower numbers go first)
        weekly_digest_optin: Whether member receives the Monday weekly digest
            SMS (independent of escalation-contact status, WOF-10)
        created_at: Timestamp when member was added
        updated_at: Timestamp when member was last modified

    Relationships:
        schedules: List of schedule assignments for this member
    """

    __tablename__ = "team_members"

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Member information
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    # NOTE: No unique constraint - multiple members can share same personal phone or omit it
    # Also compatible with testing mode where primary phone is non-unique (see migration 200f01c20965)
    secondary_phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    rotation_order = Column(Integer, nullable=True, index=True)  # Order in rotation (nullable for flexibility)
    # Monday weekly-digest opt-in, decoupled from escalation contacts (WOF-10)
    weekly_digest_optin = Column(Boolean, default=False, nullable=False, server_default="0")

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    schedules = relationship(
        "Schedule",
        back_populates="team_member",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        """String representation of TeamMember."""
        return f"<TeamMember(id={self.id}, name='{self.name}', phone='{self.phone}', active={self.is_active})>"

    def __str__(self):
        """Human-readable string representation."""
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({self.phone}) - {status}"

    def to_dict(self):
        """
        Convert model to dictionary for API responses.

        Returns:
            Dictionary representation of the team member
        """
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "secondary_phone": self.secondary_phone,
            "is_active": self.is_active,
            "rotation_order": self.rotation_order,
            "weekly_digest_optin": self.weekly_digest_optin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        Validate phone number is in E.164 format.

        Args:
            phone: Phone number to validate

        Returns:
            True if valid, False otherwise
        """
        import re
        # E.164 format: +1 followed by 10 digits
        pattern = r'^\+1\d{10}$'
        return bool(re.match(pattern, phone))

    def sanitize_phone_for_log(self) -> str:
        """
        Return sanitized phone number for logging (mask last 4 digits).

        Returns:
            Sanitized phone number like +1555***1234
        """
        if len(self.phone) >= 4:
            return f"{self.phone[:-4]}***{self.phone[-4:]}"
        return "***"
