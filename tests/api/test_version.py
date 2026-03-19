"""
Tests for the version API endpoint.
"""

from pathlib import Path

from fastapi.testclient import TestClient


class TestVersionEndpoint:
    """Tests for GET /api/v1/version."""

    def test_get_version_returns_200(self, client: TestClient):
        """Test that the version endpoint returns 200 with the correct version."""
        response = client.get("/api/v1/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.6.0"

    def test_get_version_missing_file(self, client: TestClient, monkeypatch):
        """Test that a missing VERSION file returns {"version": "unknown"}."""
        import src.api.routes.version as version_module

        monkeypatch.setattr(
            version_module, "_VERSION_FILE", Path("/nonexistent/VERSION")
        )

        response = client.get("/api/v1/version")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "unknown"
