"""
Tests for settings API endpoints.

Tests cover auto-renewal configuration and SMS template management.

WHO-43 (Task 0.5, TDD red phase) extends this file with 10 tests for the
new Twilio configuration endpoints — see TestTwilioConfigEndpoints and
TestSmsStatusEndpoint at the bottom of this module. Twilio HTTP calls are
stubbed via @patch on src.api.routes.settings.Client (the SDK class the
implementer is expected to use per design.md §Component 4).
"""

import os
from unittest.mock import patch, Mock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from twilio.base.exceptions import TwilioRestException


class TestAutoRenewEndpoints:
    """Tests for auto-renewal configuration endpoints."""

    def test_get_auto_renew_config(self, client: TestClient):
        """Test retrieving auto-renewal configuration."""
        response = client.get("/api/v1/settings/auto-renew")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "threshold_weeks" in data
        assert "renew_weeks" in data
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["threshold_weeks"], int)
        assert isinstance(data["renew_weeks"], int)

    def test_update_auto_renew_config(self, client: TestClient):
        """Test updating auto-renewal configuration."""
        update_data = {
            "enabled": False,
            "threshold_weeks": 6,
            "renew_weeks": 26
        }

        response = client.put("/api/v1/settings/auto-renew", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["threshold_weeks"] == 6
        assert data["renew_weeks"] == 26

    def test_update_auto_renew_partial(self, client: TestClient):
        """Test partial update of auto-renewal configuration."""
        # Only update enabled flag
        update_data = {"enabled": True}

        response = client.put("/api/v1/settings/auto-renew", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True


class TestSMSTemplateEndpoints:
    """Tests for SMS template management endpoints."""

    def test_get_sms_template_default(self, client: TestClient):
        """Test retrieving default SMS template on first access."""
        response = client.get("/api/v1/settings/sms-template")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "template" in data
        assert "last_updated" in data
        assert "character_count" in data
        assert "sms_count" in data
        assert "variables" in data

        # Verify template content
        template = data["template"]
        assert len(template) > 0
        assert "{name}" in template
        assert "{start_time}" in template
        assert "{end_time}" in template
        assert "{duration}" in template

        # Verify metadata
        assert data["character_count"] == len(template)
        assert data["sms_count"] >= 1
        assert isinstance(data["variables"], list)
        assert "name" in data["variables"]
        assert "start_time" in data["variables"]
        assert "end_time" in data["variables"]
        assert "duration" in data["variables"]

    def test_update_sms_template_valid(self, client: TestClient):
        """Test updating SMS template with valid content."""
        new_template = "Hi {name}, on-call from {start_time} to {end_time} ({duration})."

        response = client.put("/api/v1/settings/sms-template", json={
            "template": new_template
        })

        assert response.status_code == 200
        data = response.json()
        assert data["template"] == new_template
        assert data["character_count"] == len(new_template)
        assert data["sms_count"] == 1  # Should fit in 1 SMS
        assert sorted(data["variables"]) == ["duration", "end_time", "name", "start_time"]

    def test_update_sms_template_empty(self, client: TestClient):
        """Test that empty template is rejected."""
        response = client.put("/api/v1/settings/sms-template", json={
            "template": ""
        })

        # Pydantic validation catches this before endpoint logic (422 vs 400)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert isinstance(detail, list) or "String should have at least 1 character" in str(detail)

    def test_update_sms_template_whitespace_only(self, client: TestClient):
        """Test that whitespace-only template is rejected."""
        response = client.put("/api/v1/settings/sms-template", json={
            "template": "   \n   "
        })

        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_update_sms_template_no_variables(self, client: TestClient):
        """Test that template without variables is rejected."""
        response = client.put("/api/v1/settings/sms-template", json={
            "template": "This is a static message with no variables."
        })

        assert response.status_code == 400
        assert "must contain at least one variable" in response.json()["detail"]

    def test_update_sms_template_invalid_variables(self, client: TestClient):
        """Test that template with invalid variables is rejected."""
        response = client.put("/api/v1/settings/sms-template", json={
            "template": "Hi {name}, your shift is {invalid_var}."
        })

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Invalid template variables" in detail
        assert "invalid_var" in detail

    def test_update_sms_template_too_long(self, client: TestClient):
        """Test that template exceeding character limit is rejected."""
        # Create a template > 320 characters
        long_template = "Hi {name}, " + "x" * 350

        response = client.put("/api/v1/settings/sms-template", json={
            "template": long_template
        })

        # Pydantic validation catches this before endpoint logic (422 vs 400)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert isinstance(detail, list) or "320" in str(detail)

    def test_update_sms_template_max_length(self, client: TestClient):
        """Test template at exactly 320 characters (2 SMS segments)."""
        # Create a template at exactly 320 chars
        template = "Hi {name}, " + "x" * 298 + " {duration}"
        assert len(template) == 320

        response = client.put("/api/v1/settings/sms-template", json={
            "template": template
        })

        assert response.status_code == 200
        data = response.json()
        assert data["character_count"] == 320
        assert data["sms_count"] == 2

    def test_sms_count_calculation(self, client: TestClient):
        """Test SMS segment count calculation for various lengths."""
        test_cases = [
            ("Hi {name}!", 1),  # 10 chars = 1 SMS
            ("Hi {name}, " + "x" * 148, 1),  # 159 chars = 1 SMS
            ("Hi {name}, " + "x" * 149, 1),  # 160 chars = 1 SMS (exactly fills one segment)
            ("Hi {name}, " + "x" * 150, 2),  # 161 chars = 2 SMS (spills to second segment)
            ("Hi {name}, " + "x" * 309, 2),  # 320 chars = 2 SMS (max allowed)
        ]

        for template, expected_sms_count in test_cases:
            response = client.put("/api/v1/settings/sms-template", json={
                "template": template
            })

            assert response.status_code == 200, f"Template length {len(template)} failed: {response.json()}"
            data = response.json()
            assert data["sms_count"] == expected_sms_count, \
                f"Template of {len(template)} chars should be {expected_sms_count} SMS, got {data['sms_count']}"

    def test_template_persistence(self, client: TestClient):
        """Test that template changes persist across requests."""
        # Update template
        new_template = "Test {name} {duration}"
        response = client.put("/api/v1/settings/sms-template", json={
            "template": new_template
        })
        assert response.status_code == 200

        # Retrieve template
        response = client.get("/api/v1/settings/sms-template")
        assert response.status_code == 200
        data = response.json()
        assert data["template"] == new_template

    def test_template_with_all_variables(self, client: TestClient):
        """Test template containing all supported variables."""
        template = "Alert: {name} on-call {start_time}-{end_time} ({duration})"

        response = client.put("/api/v1/settings/sms-template", json={
            "template": template
        })

        assert response.status_code == 200
        data = response.json()
        assert set(data["variables"]) == {"name", "start_time", "end_time", "duration"}

    def test_template_with_subset_variables(self, client: TestClient):
        """Test template with only some variables (valid)."""
        template = "Hi {name}, shift starts {start_time}"

        response = client.put("/api/v1/settings/sms-template", json={
            "template": template
        })

        assert response.status_code == 200
        data = response.json()
        assert set(data["variables"]) == {"name", "start_time"}

    def test_template_with_multiline(self, client: TestClient):
        """Test template with line breaks."""
        template = """WhoseOnFirst Alert

Hi {name}, you are on-call from {start_time} to {end_time}.

Duration: {duration}"""

        response = client.put("/api/v1/settings/sms-template", json={
            "template": template
        })

        assert response.status_code == 200
        data = response.json()
        assert data["template"] == template
        assert "\n" in data["template"]

    def test_variable_extraction_regex(self, client: TestClient):
        """Test that variable extraction correctly identifies all placeholders."""
        template = "{name} {name} {start_time} {end_time} {duration} {name}"

        response = client.put("/api/v1/settings/sms-template", json={
            "template": template
        })

        assert response.status_code == 200
        data = response.json()
        # Variables list may include duplicates from regex findall
        assert "name" in data["variables"]
        assert "start_time" in data["variables"]
        assert "end_time" in data["variables"]
        assert "duration" in data["variables"]


# ===========================================================================
# WHO-43 — Twilio config + SMS status endpoints (TDD red phase)
# ===========================================================================
#
# These tests pin the contract for design.md §Component 4:
#   GET  /api/v1/settings/twilio       (auth, returns masked token)
#   PUT  /api/v1/settings/twilio       (admin, validates via Twilio API,
#                                        encrypts on persist)
#   GET  /api/v1/settings/sms-status   (auth, returns {configured, source})
#
# All Twilio SDK calls are mocked via @patch('src.api.routes.settings.Client').
# These tests will fail until Tasks 5–7 add the schemas, endpoints, and
# admin/auth wiring.

class TestTwilioConfigEndpoints:
    """GET/PUT /api/v1/settings/twilio."""

    @pytest.fixture(autouse=True)
    def ensure_secret_key(self, monkeypatch):
        """Provide SECRET_KEY for encrypted-token writes without leaking to
        other test classes or tests that must see the key absent."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-api-twilio-endpoints")  # gitleaks:allow (test-only fake key)

    # --- GET /twilio -----------------------------------------------------

    def test_get_twilio_returns_masked_token_when_configured(self, client: TestClient):
        """Covers REQ-2 AC 3, AC 4 (masked token in response)."""
        # Seed the DB via the existing PUT path's logical equivalent —
        # use SettingsService directly so this test doesn't depend on the
        # PUT endpoint also being implemented.
        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        # Pull the test session out of the dependency override. Close the
        # generator after extracting the session so override_get_db's
        # finally block runs (CodeRabbit N7).
        db_gen = app.dependency_overrides[get_db]()
        try:
            db = next(db_gen)
        finally:
            db_gen.close()
        svc = SettingsService(db)
        svc.set_setting(
            "twilio_account_sid", "xx1234567890abcdef1234567890abcdef",
            value_type="str"
        )
        svc.set_setting(
            "twilio_auth_token", "supersecret-token-1234",
            value_type="encrypted"
        )
        svc.set_setting(
            "twilio_phone_number", "+15551239876",
            value_type="str"
        )

        response = client.get("/api/v1/settings/twilio")

        assert response.status_code == 200
        data = response.json()
        assert data["account_sid"] == "xx1234567890abcdef1234567890abcdef"
        assert data["phone_number"] == "+15551239876"
        # Mask: 8 bullets + last 4 chars of plaintext token "1234".
        assert data["auth_token_masked"] == "••••••••" + "1234"

    def test_get_twilio_returns_null_token_when_not_configured(self, client: TestClient):
        """Covers REQ-2 AC 3 (null masked when no token stored)."""
        response = client.get("/api/v1/settings/twilio")

        assert response.status_code == 200
        data = response.json()
        assert data.get("auth_token_masked") is None
        assert data.get("account_sid") is None
        assert data.get("phone_number") is None

    # --- PUT /twilio -----------------------------------------------------

    @patch("src.api.routes.settings.Client")
    def test_put_twilio_validates_via_twilio_api_before_persisting(
        self, mock_client_class, client: TestClient
    ):
        """Covers REQ-1 AC 4, AC 6; NFR Security (validation-before-persist).

        Asserts (a) Twilio API was called BEFORE DB write, (b) DB now has
        the encrypted creds.
        """
        # Mock Twilio Client.api.accounts(sid).fetch() to succeed (200 OK).
        mock_client = Mock()
        mock_client.api.accounts.return_value.fetch.return_value = Mock(sid="ACvalid")
        mock_client_class.return_value = mock_client

        payload = {
            "account_sid": "xx1234567890abcdef1234567890abcdef",
            "auth_token": "valid-twilio-auth-token-32chars-XX",
            "phone_number": "+15558675309",
        }

        response = client.put("/api/v1/settings/twilio", json=payload)

        assert response.status_code == 200, response.text
        # Twilio API must have been called for validation.
        mock_client_class.assert_called_once()
        mock_client.api.accounts.assert_called()

        # DB now has the new rows.
        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        db = next(app.dependency_overrides[get_db]())
        svc = SettingsService(db)
        sid_row = svc.repository.get_by_key("twilio_account_sid")
        token_row = svc.repository.get_by_key("twilio_auth_token")
        phone_row = svc.repository.get_by_key("twilio_phone_number")

        assert sid_row is not None and sid_row.value == "xx1234567890abcdef1234567890abcdef"
        assert token_row is not None and token_row.value_type == "encrypted"
        assert token_row.value != "valid-twilio-auth-token-32chars-XX", (
            "Token must be persisted as ciphertext, not plaintext"
        )
        assert phone_row is not None and phone_row.value == "+15558675309"

    @patch("src.api.routes.settings.Client")
    def test_put_twilio_rejects_with_400_when_twilio_returns_401(
        self, mock_client_class, client: TestClient
    ):
        """Covers REQ-1 AC 5 (Twilio 401 → no persistence + clear error)."""
        # Mock Twilio Client to raise a 401 TwilioRestException on fetch.
        mock_client = Mock()
        mock_client.api.accounts.return_value.fetch.side_effect = TwilioRestException(
            status=401,
            uri="https://api.twilio.com/2010-04-01/Accounts/AC.../",
            msg="Authenticate",
            code=20003,
        )
        mock_client_class.return_value = mock_client

        payload = {
            "account_sid": "ACbadcredsbadcredsbadcredsbadcred1",
            "auth_token": "wrong-token-but-well-formed-XXXXXX",
            "phone_number": "+15550000001",
        }

        response = client.put("/api/v1/settings/twilio", json=payload)

        assert response.status_code == 400, response.text
        body = response.json()
        # Detail mentions credential rejection (exact wording TBD by impl).
        detail = str(body.get("detail", "")).lower()
        assert any(w in detail for w in ("reject", "credential", "twilio")), (
            f"Expected credential-rejection message, got: {body}"
        )

        # CRITICAL: validation gate — no DB rows were written.
        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        db = next(app.dependency_overrides[get_db]())
        svc = SettingsService(db)
        assert svc.repository.get_by_key("twilio_account_sid") is None
        assert svc.repository.get_by_key("twilio_auth_token") is None
        assert svc.repository.get_by_key("twilio_phone_number") is None

    @patch("src.api.routes.settings.Client")
    def test_put_twilio_returns_502_on_twilio_network_error(
        self, mock_client_class, client: TestClient
    ):
        """Covers design.md §Error Handling scenario 2 (network failure)."""
        import httpx

        mock_client = Mock()
        mock_client.api.accounts.return_value.fetch.side_effect = httpx.TimeoutException(
            "Request timed out"
        )
        mock_client_class.return_value = mock_client

        payload = {
            "account_sid": "xx1234567890abcdef1234567890abcdef",
            "auth_token": "valid-format-token-but-net-failure00",
            "phone_number": "+15550000002",
        }

        response = client.put("/api/v1/settings/twilio", json=payload)

        assert response.status_code == 502, response.text

        # No persistence on network failure.
        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        db = next(app.dependency_overrides[get_db]())
        svc = SettingsService(db)
        assert svc.repository.get_by_key("twilio_account_sid") is None
        assert svc.repository.get_by_key("twilio_auth_token") is None
        assert svc.repository.get_by_key("twilio_phone_number") is None

    @patch("src.api.routes.settings.Client")
    def test_put_twilio_persists_after_successful_validation(
        self, mock_client_class, client: TestClient
    ):
        """Covers REQ-1 AC 6, REQ-2 AC 1 (correct value_types per row)."""
        mock_client = Mock()
        mock_client.api.accounts.return_value.fetch.return_value = Mock(sid="ACok")
        mock_client_class.return_value = mock_client

        payload = {
            "account_sid": "xxabcdef1234567890abcdef1234567890",
            "auth_token": "another-good-token-1234567890XX",
            "phone_number": "+15551112222",
        }

        response = client.put("/api/v1/settings/twilio", json=payload)
        assert response.status_code == 200, response.text

        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        db = next(app.dependency_overrides[get_db]())
        svc = SettingsService(db)

        sid_row = svc.repository.get_by_key("twilio_account_sid")
        token_row = svc.repository.get_by_key("twilio_auth_token")
        phone_row = svc.repository.get_by_key("twilio_phone_number")

        assert sid_row is not None
        assert sid_row.value_type == "str"
        assert sid_row.value == "xxabcdef1234567890abcdef1234567890"

        assert token_row is not None
        assert token_row.value_type == "encrypted"
        # Stored value is ciphertext, not plaintext.
        assert token_row.value != "another-good-token-1234567890XX"

        assert phone_row is not None
        assert phone_row.value_type == "str"
        assert phone_row.value == "+15551112222"

    def test_put_twilio_requires_admin_role(
        self, db_session, mock_admin_user
    ):
        """Covers REQ-1 AC 7, NFR Security (admin-only PUT).

        A viewer-role user must be rejected with HTTP 403 by require_admin.
        We construct a dedicated TestClient that overrides require_admin to
        raise 403 (simulating a viewer hitting the dependency), since the
        shared `client` fixture overrides require_admin to allow admin.
        """
        from src.main import app
        from src.api.dependencies import get_db
        from src.api.routes.auth import require_auth, require_admin
        from src.models.user import User, UserRole

        # Build a viewer user override.
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        def override_require_auth():
            # Authenticated, but as a viewer (not admin).
            viewer = User(
                id=999,
                username="test_viewer",
                password_hash="x",
                role=UserRole.VIEWER,
                is_active=True,
            )
            return viewer

        def override_require_admin():
            # Real require_admin would raise 403 for non-admin — emulate that.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[require_auth] = override_require_auth
        app.dependency_overrides[require_admin] = override_require_admin

        try:
            with TestClient(app) as viewer_client:
                response = viewer_client.put(
                    "/api/v1/settings/twilio",
                    json={
                        "account_sid": "xx1234567890abcdef1234567890abcdef",
                        "auth_token": "viewer-attempt-token-1234567890",
                        "phone_number": "+15554443333",
                    },
                )
            assert response.status_code == 403, response.text
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routes.settings.Client")
    def test_put_twilio_rejects_masked_placeholder_as_token(
        self, mock_client_class, client: TestClient
    ):
        """Covers REQ-2 AC 4, design.md §Error Handling scenario 6.

        If the frontend re-submits the masked placeholder (8 bullets +
        4 chars), the server MUST reject with 400 — never call Twilio,
        never write to the DB.
        """
        masked_placeholder = "•" * 8 + "1234"

        payload = {
            "account_sid": "xx1234567890abcdef1234567890abcdef",
            "auth_token": masked_placeholder,
            "phone_number": "+15550006666",
        }

        response = client.put("/api/v1/settings/twilio", json=payload)

        assert response.status_code == 400, response.text
        # Detail should mention masked/placeholder rejection.
        detail = str(response.json().get("detail", "")).lower()
        assert any(w in detail for w in ("mask", "placeholder", "re-enter")), (
            f"Expected masked-placeholder rejection message, got: {response.json()}"
        )

        # Twilio was not called.
        mock_client_class.assert_not_called()

        # DB unchanged.
        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        db = next(app.dependency_overrides[get_db]())
        svc = SettingsService(db)
        assert svc.repository.get_by_key("twilio_auth_token") is None


class TestSmsStatusEndpoint:
    """GET /api/v1/settings/sms-status."""

    def test_get_sms_status_returns_db_when_configured_in_db(
        self, client: TestClient
    ):
        """Covers REQ-4 AC 6, REQ-3 AC 1 (DB source reported as 'db')."""
        from src.services.settings_service import SettingsService
        from src.api.dependencies import get_db
        from src.main import app

        db = next(app.dependency_overrides[get_db]())
        svc = SettingsService(db)
        svc.set_setting(
            "twilio_account_sid", "xxdb000000000000000000000000000abc",
            value_type="str"
        )
        svc.set_setting(
            "twilio_auth_token", "db-token-status-test",
            value_type="encrypted"
        )
        svc.set_setting(
            "twilio_phone_number", "+15558881234",
            value_type="str"
        )

        with patch.dict(os.environ, {}, clear=True):
            os.environ["SECRET_KEY"] = "test-secret-key-status-db"  # gitleaks:allow (test-only fake key)
            response = client.get("/api/v1/settings/sms-status")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["configured"] is True
        assert data["source"] == "db"

    @patch.dict(os.environ, {}, clear=True)
    def test_get_sms_status_returns_none_when_neither_configured(
        self, client: TestClient
    ):
        """Covers REQ-4 AC 1, AC 6 (none source when no creds anywhere)."""
        response = client.get("/api/v1/settings/sms-status")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["configured"] is False
        assert data["source"] == "none"

    @patch.dict(
        os.environ,
        {"SMS_MOCK_MODE": "true", "SECRET_KEY": "test-key-mock"},  # gitleaks:allow (test-only fake key)
        clear=True,
    )
    def test_get_sms_status_returns_mock_when_forced_via_env(
        self, client: TestClient
    ):
        """Covers REQ-3 AC 4, REQ-4 AC 5, AC 6 (mock source when forced).

        When SMS_MOCK_MODE is truthy, the status endpoint must report
        source='mock' (informational), distinct from 'none' (warning).
        """
        response = client.get("/api/v1/settings/sms-status")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["source"] == "mock"
        # 'configured' is False because mock mode is not "configured" per
        # the design — only db|env count as configured.
        assert data["configured"] is False
