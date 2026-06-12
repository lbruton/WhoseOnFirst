"""
Schedule overrides API endpoint tests.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


class TestCompletePastOverridesErrorSanitization:
    """Tests that the manual completion trigger never exposes raw exception text (WOF-19)."""

    def test_complete_past_error_hides_exception_detail(self, client: TestClient):
        """A failing override completion job must return a generic 500 detail, not str(e)."""
        with patch(
            "src.scheduler.schedule_manager.complete_past_overrides"
        ) as mock_complete:
            mock_complete.side_effect = Exception("SECRET-INTERNAL-DETAIL")
            response = client.post("/api/v1/schedule-overrides/complete-past")

        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Override completion job failed - see server logs"
        assert "SECRET-INTERNAL-DETAIL" not in response.text
