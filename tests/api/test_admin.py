"""
Admin API endpoint tests — export/import (backup & restore).

The import endpoint is the only consumer of python-multipart (FastAPI
UploadFile), so the round-trip test here doubles as functional validation
of the multipart parser whenever that dependency is bumped.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.team_member import TeamMember


class TestExportImportRoundTrip:
    """Tests for GET /api/v1/admin/export and POST /api/v1/admin/import."""

    def test_import_restores_exported_backup(
        self, client: TestClient, db_session: Session
    ):
        """A real multipart upload of an exported backup restores cleanly.

        Exercises the python-multipart parser end-to-end (UploadFile).
        """
        member = TeamMember(name="Backup Bob", phone="+15557770001", is_active=True)
        db_session.add(member)
        db_session.commit()

        export_response = client.get("/api/v1/admin/export")
        assert export_response.status_code == 200
        backup_bytes = export_response.content

        import_response = client.post(
            "/api/v1/admin/import",
            files={"file": ("backup.stvault", backup_bytes, "application/json")},
        )

        assert import_response.status_code == 200
        body = import_response.json()
        assert body["status"] == "success"
        assert body["imported"]["team_members"] >= 1

    def test_import_rejects_invalid_json(self, client: TestClient):
        """A multipart upload that isn't JSON returns 400, not a parser crash."""
        response = client.post(
            "/api/v1/admin/import",
            files={"file": ("backup.stvault", b"not-json{{{", "application/json")},
        )

        assert response.status_code == 400
        assert "invalid json" in response.json()["detail"].lower()
