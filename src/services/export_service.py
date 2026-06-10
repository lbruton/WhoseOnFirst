"""
ExportService — serializes the database to a .stvault JSON envelope.

Exports team_members, shifts, schedule, and settings.
Users and notification_log are intentionally excluded.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models import TeamMember, Shift, Schedule
from src.models.settings import Settings
from src.version import get_app_version

# Version of the .stvault envelope format — independent of the app version
SCHEMA_VERSION = "1.0"


def _dt(value) -> str | None:
    """Convert a datetime (or None) to ISO 8601 string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class ExportService:
    def __init__(self, db: Session):
        self.db = db

    def export_all(self) -> dict[str, Any]:
        """
        Build and return the complete .stvault export envelope.

        Returns:
            Dictionary ready for json.dumps() serialization.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "app_version": get_app_version(),
            "data": {
                "team_members": self._export_team_members(),
                "shifts": self._export_shifts(),
                "schedule": self._export_schedule(),
                "settings": self._export_settings(),
            },
        }

    def _export_team_members(self) -> list[dict]:
        rows = self.db.query(TeamMember).order_by(TeamMember.rotation_order, TeamMember.id).all()
        return [
            {
                "id": m.id,
                "name": m.name,
                "phone": m.phone,
                "secondary_phone": m.secondary_phone,
                "is_active": m.is_active,
                "rotation_order": m.rotation_order,
                "created_at": _dt(m.created_at),
                "updated_at": _dt(m.updated_at),
            }
            for m in rows
        ]

    def _export_shifts(self) -> list[dict]:
        rows = self.db.query(Shift).order_by(Shift.shift_number).all()
        return [
            {
                "id": s.id,
                "shift_number": s.shift_number,
                "day_of_week": s.day_of_week,
                "duration_hours": s.duration_hours,
                "start_time": s.start_time,
                "created_at": _dt(s.created_at),
            }
            for s in rows
        ]

    def _export_schedule(self) -> list[dict]:
        rows = self.db.query(Schedule).order_by(Schedule.start_datetime).all()
        return [
            {
                "id": s.id,
                "team_member_id": s.team_member_id,
                "shift_id": s.shift_id,
                "week_number": s.week_number,
                "start_datetime": _dt(s.start_datetime),
                "end_datetime": _dt(s.end_datetime),
                "notified": s.notified,
                "created_at": _dt(s.created_at),
            }
            for s in rows
        ]

    def _export_settings(self) -> list[dict]:
        rows = self.db.query(Settings).order_by(Settings.key).all()
        return [
            {
                "id": s.id,
                "key": s.key,
                "value": s.value,
                "value_type": s.value_type,
                "description": s.description,
                "updated_at": _dt(s.updated_at),
            }
            for s in rows
        ]
