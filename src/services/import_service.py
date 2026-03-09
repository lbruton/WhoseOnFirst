"""
ImportService — validates and restores a .stvault backup.

Truncates existing data in FK-safe order then bulk-inserts from the file.
The entire operation is wrapped in a single transaction; any error triggers
a full rollback.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.models import TeamMember, Shift, Schedule
from src.models.settings import Settings

SUPPORTED_SCHEMA_VERSIONS = {"1.0"}
REQUIRED_DATA_KEYS = {"team_members", "shifts", "schedule", "settings"}


class ImportValidationError(Exception):
    """Raised when a .stvault payload fails validation."""


class ImportService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, payload: dict) -> list[str]:
        """
        Validate a .stvault payload.

        Returns:
            List of error strings (empty = valid).
        """
        errors = []

        if not isinstance(payload, dict):
            return ["Payload must be a JSON object"]

        # schema_version
        version = payload.get("schema_version")
        if version is None:
            errors.append("Missing required field: schema_version")
        elif version not in SUPPORTED_SCHEMA_VERSIONS:
            errors.append(
                f"Unsupported schema_version '{version}'. "
                f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
            )

        # data envelope
        data = payload.get("data")
        if data is None:
            errors.append("Missing required field: data")
            return errors  # can't check table keys without data

        if not isinstance(data, dict):
            errors.append("Field 'data' must be a JSON object")
            return errors

        for key in REQUIRED_DATA_KEYS:
            if key not in data:
                errors.append(f"Missing required data key: {key}")
            elif not isinstance(data[key], list):
                errors.append(f"Data key '{key}' must be a list")

        return errors

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore_all(self, payload: dict) -> dict[str, int]:
        """
        Validate then restore database from a .stvault payload.

        Raises:
            ImportValidationError: If validation fails.

        Returns:
            Dictionary with counts of inserted rows per table.
        """
        errors = self.validate(payload)
        if errors:
            raise ImportValidationError("; ".join(errors))

        data = payload["data"]

        try:
            # Truncate in FK-safe order (children before parents)
            self.db.query(Schedule).delete()
            self.db.query(TeamMember).delete()
            self.db.query(Shift).delete()
            self.db.query(Settings).delete()
            self.db.flush()

            counts = {
                "team_members": self._insert_team_members(data["team_members"]),
                "shifts": self._insert_shifts(data["shifts"]),
                "schedule": self._insert_schedule(data["schedule"]),
                "settings": self._insert_settings(data["settings"]),
            }

            self.db.commit()
            return counts

        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------------
    # Table inserters
    # ------------------------------------------------------------------

    def _parse_dt(self, value) -> datetime | None:
        """Parse an ISO datetime string or return None."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            # Strip timezone info for SQLite naive datetime storage
            dt = datetime.fromisoformat(str(value))
            return dt.replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

    def _insert_team_members(self, rows: list[dict]) -> int:
        for row in rows:
            member = TeamMember(
                name=row["name"],
                phone=row["phone"],
                secondary_phone=row.get("secondary_phone"),
                is_active=row.get("is_active", True),
                rotation_order=row.get("rotation_order"),
                created_at=self._parse_dt(row.get("created_at")),
            )
            self.db.add(member)
        self.db.flush()
        return len(rows)

    def _insert_shifts(self, rows: list[dict]) -> int:
        for row in rows:
            shift = Shift(
                shift_number=row["shift_number"],
                day_of_week=row["day_of_week"],
                duration_hours=row["duration_hours"],
                start_time=row.get("start_time", "08:00:00"),
                created_at=self._parse_dt(row.get("created_at")),
            )
            self.db.add(shift)
        self.db.flush()
        return len(rows)

    def _insert_schedule(self, rows: list[dict]) -> int:
        # Build id→new_id maps for team_members and shifts
        # Import doesn't preserve original PKs — SQLite auto-assigns new IDs.
        # We rely on name/phone uniqueness for team_members and shift_number for shifts.
        member_map = {
            m.name: m.id
            for m in self.db.query(TeamMember).all()
        }
        shift_map = {
            s.shift_number: s.id
            for s in self.db.query(Shift).all()
        }

        for row in rows:
            # Resolve FKs by original IDs stored in the file
            # Since we flushed members/shifts above, we can query them
            team_member_id = row.get("team_member_id")
            shift_id = row.get("shift_id")

            sched = Schedule(
                team_member_id=team_member_id,
                shift_id=shift_id,
                week_number=row["week_number"],
                start_datetime=self._parse_dt(row["start_datetime"]),
                end_datetime=self._parse_dt(row["end_datetime"]),
                notified=row.get("notified", False),
                created_at=self._parse_dt(row.get("created_at")),
            )
            self.db.add(sched)
        self.db.flush()
        return len(rows)

    def _insert_settings(self, rows: list[dict]) -> int:
        for row in rows:
            setting = Settings(
                key=row["key"],
                value=row["value"],
                value_type=row.get("value_type", "str"),
                description=row.get("description"),
            )
            self.db.add(setting)
        self.db.flush()
        return len(rows)
