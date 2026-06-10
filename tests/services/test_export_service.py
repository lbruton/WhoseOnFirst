"""
Tests for ExportService and ImportService (WHO-36).

Covers: export envelope structure, per-table serialization,
        import validation, full restore round-trip, rollback on error.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models import TeamMember, Shift, Schedule
from src.models.settings import Settings
from src.services.export_service import ExportService
from src.services.import_service import ImportService, ImportValidationError


SCHEMA_VERSION = "1.0"


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
def export_service(db_session):
    return ExportService(db_session)


@pytest.fixture
def import_service(db_session):
    return ImportService(db_session)


@pytest.fixture
def populated_db(db_session):
    """Seed one row in each table so export has real data."""
    member = TeamMember(name="Alice", phone="+15551111111", is_active=True, rotation_order=0)
    db_session.add(member)
    db_session.flush()

    shift = Shift(shift_number=1, day_of_week="Monday", duration_hours=24, start_time="08:00:00")
    db_session.add(shift)
    db_session.flush()

    now = datetime.now()
    sched = Schedule(
        team_member_id=member.id,
        shift_id=shift.id,
        week_number=1,
        start_datetime=now,
        end_datetime=now + timedelta(hours=24),
        notified=False,
    )
    db_session.add(sched)

    setting = Settings(key="auto_renew_enabled", value="true", value_type="bool")
    db_session.add(setting)
    db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# ExportService
# ---------------------------------------------------------------------------

class TestExportEnvelope:

    def test_has_required_top_level_keys(self, export_service):
        result = export_service.export_all()
        assert "schema_version" in result
        assert "exported_at" in result
        assert "app_version" in result
        assert "data" in result

    def test_schema_version_is_1_0(self, export_service):
        result = export_service.export_all()
        assert result["schema_version"] == SCHEMA_VERSION

    def test_app_version_is_canonical(self, export_service):
        """Export provenance must track the VERSION file, not a stale literal (WOF-14)."""
        from src.version import get_app_version

        result = export_service.export_all()
        assert result["app_version"] == get_app_version()

    def test_exported_at_is_iso_string(self, export_service):
        result = export_service.export_all()
        # Should parse without error
        datetime.fromisoformat(result["exported_at"])

    def test_data_has_four_keys(self, export_service):
        result = export_service.export_all()
        assert set(result["data"].keys()) == {"team_members", "shifts", "schedule", "settings"}

    def test_empty_db_exports_empty_lists(self, export_service):
        result = export_service.export_all()
        assert result["data"]["team_members"] == []
        assert result["data"]["shifts"] == []
        assert result["data"]["schedule"] == []
        assert result["data"]["settings"] == []


class TestExportTeamMembers:

    def test_exports_member_fields(self, export_service, populated_db):
        result = export_service.export_all()
        members = result["data"]["team_members"]
        assert len(members) == 1
        m = members[0]
        assert m["name"] == "Alice"
        assert m["phone"] == "+15551111111"
        assert m["is_active"] is True
        assert m["rotation_order"] == 0
        assert "id" in m

    def test_datetime_fields_are_strings(self, export_service, populated_db):
        result = export_service.export_all()
        m = result["data"]["team_members"][0]
        assert isinstance(m["created_at"], str)


class TestExportShifts:

    def test_exports_shift_fields(self, export_service, populated_db):
        result = export_service.export_all()
        shifts = result["data"]["shifts"]
        assert len(shifts) == 1
        s = shifts[0]
        assert s["shift_number"] == 1
        assert s["day_of_week"] == "Monday"
        assert s["duration_hours"] == 24
        assert s["start_time"] == "08:00:00"


class TestExportSchedule:

    def test_exports_schedule_fields(self, export_service, populated_db):
        result = export_service.export_all()
        schedules = result["data"]["schedule"]
        assert len(schedules) == 1
        s = schedules[0]
        assert "team_member_id" in s
        assert "shift_id" in s
        assert "week_number" in s
        assert isinstance(s["start_datetime"], str)
        assert isinstance(s["end_datetime"], str)
        assert s["notified"] is False


class TestExportSettings:

    def test_exports_settings_fields(self, export_service, populated_db):
        result = export_service.export_all()
        settings = result["data"]["settings"]
        assert len(settings) == 1
        s = settings[0]
        assert s["key"] == "auto_renew_enabled"
        assert s["value"] == "true"
        assert s["value_type"] == "bool"


# ---------------------------------------------------------------------------
# ImportService — validation
# ---------------------------------------------------------------------------

class TestImportValidation:

    def test_valid_payload_passes(self, import_service):
        payload = {
            "schema_version": "1.0",
            "exported_at": "2026-03-09T22:00:00",
            "app_version": "1.5.0",
            "data": {
                "team_members": [],
                "shifts": [],
                "schedule": [],
                "settings": [],
            }
        }
        errors = import_service.validate(payload)
        assert errors == []

    def test_wrong_schema_version_fails(self, import_service):
        payload = {
            "schema_version": "99.0",
            "data": {"team_members": [], "shifts": [], "schedule": [], "settings": []}
        }
        errors = import_service.validate(payload)
        assert any("schema_version" in e for e in errors)

    def test_missing_schema_version_fails(self, import_service):
        payload = {
            "data": {"team_members": [], "shifts": [], "schedule": [], "settings": []}
        }
        errors = import_service.validate(payload)
        assert any("schema_version" in e for e in errors)

    def test_missing_data_key_fails(self, import_service):
        payload = {"schema_version": "1.0"}
        errors = import_service.validate(payload)
        assert any("data" in e for e in errors)

    def test_missing_table_key_fails(self, import_service):
        payload = {
            "schema_version": "1.0",
            "data": {"team_members": [], "shifts": []}  # missing schedule and settings
        }
        errors = import_service.validate(payload)
        assert len(errors) >= 1

    def test_non_list_table_fails(self, import_service):
        payload = {
            "schema_version": "1.0",
            "data": {"team_members": "bad", "shifts": [], "schedule": [], "settings": []}
        }
        errors = import_service.validate(payload)
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# ImportService — restore
# ---------------------------------------------------------------------------

class TestImportRestore:

    def test_restore_inserts_team_members(self, import_service, db_session):
        payload = {
            "schema_version": "1.0",
            "data": {
                "team_members": [
                    {"id": 1, "name": "Bob", "phone": "+15552222222",
                     "secondary_phone": None, "is_active": True,
                     "rotation_order": 0, "created_at": "2026-01-01T00:00:00",
                     "updated_at": "2026-01-01T00:00:00"}
                ],
                "shifts": [],
                "schedule": [],
                "settings": [],
            }
        }
        result = import_service.restore_all(payload)
        assert result["team_members"] == 1
        members = db_session.query(TeamMember).all()
        assert len(members) == 1
        assert members[0].name == "Bob"

    def test_restore_clears_existing_data(self, import_service, populated_db):
        # populated_db has 1 member, 1 shift, 1 schedule, 1 setting
        payload = {
            "schema_version": "1.0",
            "data": {
                "team_members": [],
                "shifts": [],
                "schedule": [],
                "settings": [],
            }
        }
        import_service.restore_all(payload)
        assert populated_db.query(TeamMember).count() == 0
        assert populated_db.query(Shift).count() == 0
        assert populated_db.query(Schedule).count() == 0
        assert populated_db.query(Settings).count() == 0

    def test_restore_returns_counts(self, import_service, db_session):
        payload = {
            "schema_version": "1.0",
            "data": {
                "team_members": [],
                "shifts": [
                    {"id": 1, "shift_number": 1, "day_of_week": "Monday",
                     "duration_hours": 24, "start_time": "08:00:00",
                     "created_at": "2026-01-01T00:00:00"}
                ],
                "schedule": [],
                "settings": [],
            }
        }
        result = import_service.restore_all(payload)
        assert result["shifts"] == 1
        assert isinstance(result["team_members"], int)

    def test_full_round_trip(self, export_service, import_service, populated_db, db_session):
        """Export then re-import should restore identical data."""
        exported = export_service.export_all()

        # Wipe and re-import
        import_service.restore_all(exported)

        assert db_session.query(TeamMember).count() == 1
        assert db_session.query(Shift).count() == 1
        assert db_session.query(Schedule).count() == 1
        assert db_session.query(Settings).count() == 1
        member = db_session.query(TeamMember).first()
        assert member.name == "Alice"
        assert member.phone == "+15551111111"

    def test_invalid_payload_raises(self, import_service):
        payload = {"schema_version": "99.0", "data": {}}
        with pytest.raises(ImportValidationError):
            import_service.restore_all(payload)
