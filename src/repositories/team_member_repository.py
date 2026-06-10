"""
Team member repository for database operations.

Handles all database operations related to team members,
including phone validation and active member queries.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_repository import BaseRepository
from ..models.team_member import TeamMember


class TeamMemberRepository(BaseRepository[TeamMember]):
    """
    Repository for team member database operations.

    Extends BaseRepository with team member-specific queries:
    - Get active members
    - Get by phone number
    - Check phone uniqueness
    - Deactivate/activate members

    Attributes:
        db: SQLAlchemy database session
    """

    def __init__(self, db: Session):
        """
        Initialize TeamMemberRepository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(db, TeamMember)

    def get_active(self) -> List[TeamMember]:
        """
        Get all active team members.

        Returns:
            List of active TeamMember instances, ordered by name

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.is_active.is_(True))
                .order_by(self.model.name)
                .all()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting active team members: {str(e)}")

    def get_digest_recipients(self) -> List[TeamMember]:
        """
        Get active team members opted into the Monday weekly digest (WOF-10).

        Returns:
            List of active TeamMember instances with weekly_digest_optin set,
            ordered by name

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(
                    self.model.is_active.is_(True),
                    self.model.weekly_digest_optin.is_(True)
                )
                .order_by(self.model.name)
                .all()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting digest recipients: {str(e)}")

    def get_inactive(self) -> List[TeamMember]:
        """
        Get all inactive team members.

        Returns:
            List of inactive TeamMember instances, ordered by name

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.is_active.is_(False))
                .order_by(self.model.name)
                .all()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting inactive team members: {str(e)}")

    def get_by_phone(self, phone: str) -> Optional[TeamMember]:
        """
        Get team member by phone number.

        Args:
            phone: Phone number in E.164 format (+1XXXXXXXXXX)

        Returns:
            TeamMember instance if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.phone == phone)
                .first()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting team member by phone: {str(e)}")

    def phone_exists(self, phone: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if phone number already exists in database.

        Useful for validation before creating/updating team members.

        Args:
            phone: Phone number to check
            exclude_id: Optional ID to exclude from check (for updates)

        Returns:
            True if phone exists (and isn't the excluded ID), False otherwise

        Raises:
            Exception: If database operation fails
        """
        try:
            query = self.db.query(self.model).filter(self.model.phone == phone)

            if exclude_id is not None:
                query = query.filter(self.model.id != exclude_id)

            return query.count() > 0
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error checking phone existence: {str(e)}")

    def deactivate(self, member_id: int) -> Optional[TeamMember]:
        """
        Deactivate a team member (soft delete).

        Sets is_active to False instead of deleting the record.
        Preserves historical schedule data.

        Args:
            member_id: Team member ID to deactivate

        Returns:
            Updated TeamMember instance if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        try:
            member = self.get_by_id(member_id)
            if member:
                member.is_active = False
                self.db.commit()
                self.db.refresh(member)
            return member
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error deactivating team member: {str(e)}")

    def activate(self, member_id: int) -> Optional[TeamMember]:
        """
        Activate a team member.

        Sets is_active to True to add them back to rotation.

        Args:
            member_id: Team member ID to activate

        Returns:
            Updated TeamMember instance if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        try:
            member = self.get_by_id(member_id)
            if member:
                member.is_active = True
                self.db.commit()
                self.db.refresh(member)
            return member
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error activating team member: {str(e)}")

    def get_count_active(self) -> int:
        """
        Get count of active team members.

        Useful for rotation algorithm and validation.

        Returns:
            Number of active team members

        Raises:
            Exception: If database operation fails
        """
        try:
            return (
                self.db.query(self.model)
                .filter(self.model.is_active.is_(True))
                .count()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error counting active team members: {str(e)}")

    def search_by_name(self, name_query: str) -> List[TeamMember]:
        """
        Search team members by name (case-insensitive partial match).

        Args:
            name_query: Name or partial name to search for

        Returns:
            List of matching TeamMember instances

        Raises:
            Exception: If database operation fails
        """
        try:
            search_term = f"%{name_query}%"
            return (
                self.db.query(self.model)
                .filter(self.model.name.ilike(search_term))
                .order_by(self.model.name)
                .all()
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error searching team members by name: {str(e)}")

    def get_max_rotation_order(self) -> int:
        """
        Get the maximum rotation_order value.

        Useful for assigning new members to the end of the rotation.

        Returns:
            Maximum rotation_order value, or 0 if no members exist

        Raises:
            Exception: If database operation fails
        """
        try:
            max_order = (
                self.db.query(self.model.rotation_order)
                .filter(self.model.rotation_order.isnot(None))
                .order_by(self.model.rotation_order.desc())
                .first()
            )
            return max_order[0] if max_order and max_order[0] is not None else 0
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting max rotation order: {str(e)}")

    def update_rotation_orders(self, order_mapping: dict) -> List[TeamMember]:
        """
        Update rotation_order for multiple team members.

        Args:
            order_mapping: Dictionary mapping team member ID to new rotation_order value
                          Example: {1: 0, 2: 1, 3: 2}

        Returns:
            List of updated TeamMember instances

        Raises:
            Exception: If database operation fails
        """
        try:
            updated_members = []
            for member_id, new_order in order_mapping.items():
                member = self.get_by_id(member_id)
                if member:
                    member.rotation_order = new_order
                    updated_members.append(member)

            self.db.commit()

            # Refresh all updated members
            for member in updated_members:
                self.db.refresh(member)

            return updated_members
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error updating rotation orders: {str(e)}")

    def get_ordered_for_rotation(self, active_only: bool = True) -> List[TeamMember]:
        """
        Get team members ordered for rotation.

        Orders by rotation_order first (if set), then by ID as fallback.
        This ensures consistent rotation even if rotation_order is not set for all members.

        Args:
            active_only: If True, only return active members

        Returns:
            List of TeamMember instances sorted by rotation_order, then ID

        Raises:
            Exception: If database operation fails
        """
        try:
            query = self.db.query(self.model)

            if active_only:
                query = query.filter(self.model.is_active.is_(True))

            # Order by rotation_order (nulls last), then by ID as fallback
            return query.order_by(
                self.model.rotation_order.nullslast(),
                self.model.id
            ).all()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise Exception(f"Database error getting ordered team members: {str(e)}")
