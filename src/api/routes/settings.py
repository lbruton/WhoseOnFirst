"""
Settings API Routes

FastAPI router for application settings management.
"""

import logging
import re
from typing import Optional

import httpx
import requests.exceptions
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

from src.api.dependencies import get_db
from src.api.schemas.settings import (
    AutoRenewConfigResponse,
    AutoRenewConfigRequest,
    SMSTemplateResponse,
    SMSTemplateRequest,
    EscalationConfigResponse,
    EscalationConfigRequest,
    TwilioConfigRequest,
    TwilioConfigResponse,
    SMSStatusResponse,
)
from src.services import SettingsService
from src.services.secrets_service import SecretsConfigurationError
from src.services.sms_service import SMSService
from src.api.routes.auth import require_auth, require_admin


logger = logging.getLogger(__name__)

router = APIRouter()


# Matches the masked placeholder format the GET endpoint returns:
# 8 BULLET (U+2022) characters followed by 4 alphanumeric chars.
_MASKED_PLACEHOLDER_PATTERN = re.compile(r"^•{8}[A-Za-z0-9]{4}$")


def _mask_token(plaintext: Optional[str]) -> Optional[str]:
    """Return masked representation of a secret: 8 bullets + last 4 chars.

    Returns ``None`` when the input is ``None`` or shorter than 4 characters
    (treated as effectively absent rather than risking a partial reveal).
    """
    if not plaintext or len(plaintext) < 4:
        return None
    return ("•" * 8) + plaintext[-4:]


@router.get("/auto-renew", response_model=AutoRenewConfigResponse)
def get_auto_renew_config(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get auto-renewal configuration.

    Returns current settings for automatic schedule renewal.

    Args:
        db: Database session (injected)

    Returns:
        Auto-renewal configuration

    Example:
        GET /api/v1/settings/auto-renew
    """
    service = SettingsService(db)
    config = service.get_auto_renew_config()
    return config


@router.put("/auto-renew", response_model=AutoRenewConfigResponse)
def update_auto_renew_config(
    request: AutoRenewConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Update auto-renewal configuration.

    Updates settings for automatic schedule renewal.
    Only administrators can update these settings.

    Args:
        request: Auto-renewal configuration update
        db: Database session (injected)

    Returns:
        Updated auto-renewal configuration

    Example:
        PUT /api/v1/settings/auto-renew
        {
            "enabled": true,
            "threshold_weeks": 4,
            "renew_weeks": 52
        }
    """
    service = SettingsService(db)

    # Build update dict from request (only include non-None values)
    update_dict = {}
    if request.enabled is not None:
        update_dict["enabled"] = request.enabled
    if request.threshold_weeks is not None:
        update_dict["threshold_weeks"] = request.threshold_weeks
    if request.renew_weeks is not None:
        update_dict["renew_weeks"] = request.renew_weeks

    # Update settings
    service.update_auto_renew_config(update_dict)

    # Return updated config
    config = service.get_auto_renew_config()
    return config


@router.get("/sms-template", response_model=SMSTemplateResponse)
def get_sms_template(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get the SMS notification template.

    Returns the current SMS template used for on-call notifications.
    Template includes variables: {name}, {start_time}, {end_time}, {duration}

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        SMS template with metadata

    Example:
        GET /api/v1/settings/sms-template
    """
    service = SettingsService(db)
    template = service.get_sms_template()

    # Extract variables from template
    variables = re.findall(r'\{(\w+)\}', template)

    # Get last updated timestamp
    setting = service.get_setting("sms_template")
    last_updated = setting.updated_at if setting else None

    # Calculate character count and SMS segments
    char_count = len(template)
    sms_count = max(1, (char_count + 159) // 160)  # Ceiling division

    return SMSTemplateResponse(
        template=template,
        last_updated=last_updated,
        character_count=char_count,
        sms_count=sms_count,
        variables=variables
    )


@router.put("/sms-template", response_model=SMSTemplateResponse)
def update_sms_template(
    request: SMSTemplateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Update the SMS notification template.

    Updates the template used for on-call notifications.
    Only administrators can update the template.

    **Template Variables:**
    - {name}: Team member name
    - {start_time}: Shift start time (e.g., "Mon 08:00 AM")
    - {end_time}: Shift end time (e.g., "Tue 08:00 AM")
    - {duration}: Shift duration (e.g., "24h")

    **Validation Rules:**
    - Must contain at least one variable
    - Maximum 320 characters (2 SMS segments)
    - Cannot be empty or whitespace only

    Args:
        request: SMS template update request
        db: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        Updated SMS template with metadata

    Raises:
        HTTPException 400: If template is invalid

    Example:
        PUT /api/v1/settings/sms-template
        {
            "template": "Hi {name}, you're on-call from {start_time} to {end_time}."
        }
    """
    template = request.template.strip()

    # Validation 1: Check for empty template
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMS template cannot be empty"
        )

    # Validation 2: Check for at least one variable
    variables = re.findall(r'\{(\w+)\}', template)
    if not variables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template must contain at least one variable: {name}, {start_time}, {end_time}, or {duration}"
        )

    # Validation 3: Check for valid variables only
    valid_variables = {"name", "start_time", "end_time", "duration"}
    invalid_variables = set(variables) - valid_variables
    if invalid_variables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template variables: {', '.join(invalid_variables)}. Valid variables: {', '.join(valid_variables)}"
        )

    # Validation 4: Check character limit (320 = 2 SMS segments)
    if len(template) > 320:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template too long: {len(template)} characters (max 320)"
        )

    # Save template
    service = SettingsService(db)
    try:
        service.set_sms_template(template)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Return updated template with metadata
    setting = service.get_setting("sms_template")
    char_count = len(template)
    sms_count = max(1, (char_count + 159) // 160)

    return SMSTemplateResponse(
        template=template,
        last_updated=setting.updated_at if setting else None,
        character_count=char_count,
        sms_count=sms_count,
        variables=variables
    )


@router.get("/escalation", response_model=EscalationConfigResponse)
def get_escalation_config(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get escalation contact configuration.

    Returns the current escalation contact settings for dashboard display.
    Escalation contacts are fixed (non-rotating) and displayed on the dashboard
    alongside rotating Primary/Backup on-call assignments.

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Escalation contact configuration

    Example:
        GET /api/v1/settings/escalation
    """
    service = SettingsService(db)
    config = service.get_escalation_config()
    return config


@router.put("/escalation", response_model=EscalationConfigResponse)
def update_escalation_config(
    request: EscalationConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Update escalation contact configuration.

    Updates the fixed escalation contacts displayed on the dashboard.
    Only administrators can update these settings.

    **Escalation Contacts:**
    - Primary Escalation (1st): First level of escalation
    - Secondary Escalation (2nd): Second level of escalation

    **Phone Format:**
    - Must be E.164 format: +1XXXXXXXXXX
    - Example: +19187019714

    **Note:** Escalation contacts are display-only and do NOT receive
    automated notifications. They are not part of the rotation schedule.

    Args:
        request: Escalation configuration update
        db: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        Updated escalation configuration

    Raises:
        HTTPException 400: If phone format is invalid

    Example:
        PUT /api/v1/settings/escalation
        {
            "enabled": true,
            "primary_name": "Ken U",
            "primary_phone": "+19187019714",
            "secondary_name": "Steve N",
            "secondary_phone": "+19185551234"
        }
    """
    service = SettingsService(db)

    # Update escalation configuration
    # Pydantic schema already validates phone format (E.164)
    try:
        service.set_escalation_config(
            enabled=request.enabled,
            primary_name=request.primary_name,
            primary_phone=request.primary_phone,
            secondary_name=request.secondary_name,
            secondary_phone=request.secondary_phone
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Return updated config
    config = service.get_escalation_config()
    return config


@router.get("/escalation-weekly")
def get_escalation_weekly(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """
    Get weekly escalation summary setting.

    Returns whether the weekly schedule summary SMS is enabled.

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        Dictionary with 'enabled' boolean status

    Example:
        GET /api/v1/settings/escalation-weekly
    """
    service = SettingsService(db)
    return {
        "enabled": service.is_escalation_weekly_enabled()
    }


@router.put("/escalation-weekly")
def update_escalation_weekly(
    request: dict,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Update weekly escalation summary setting.

    Enables or disables the weekly schedule summary SMS sent to
    escalation contacts every Monday at 8:00 AM CST.

    Only administrators can update this setting.

    Args:
        request: Dictionary with 'enabled' boolean field
        db: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        Dictionary with updated 'enabled' status

    Example:
        PUT /api/v1/settings/escalation-weekly
        {
            "enabled": true
        }
    """
    service = SettingsService(db)

    # Extract enabled flag from request
    enabled = request.get('enabled', False)

    # Update the setting
    service.set_escalation_weekly_enabled(enabled)

    # Return updated status
    return {
        "enabled": service.is_escalation_weekly_enabled()
    }


@router.get("/twilio", response_model=TwilioConfigResponse)
def get_twilio_config(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth),
) -> TwilioConfigResponse:
    """
    Get current Twilio configuration.

    Returns Account SID and sender phone number in plaintext, with the
    Auth Token returned as a masked placeholder ("••••••••XXXX" — 8 bullets
    followed by the last 4 characters of the plaintext token). If a value
    is unset (or the encrypted token cannot be decrypted), the corresponding
    response field is ``null``.

    Args:
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        TwilioConfigResponse with masked auth token

    Example:
        GET /api/v1/settings/twilio
    """
    service = SettingsService(db)
    sid_setting = service.get_setting("twilio_account_sid")
    token_setting = service.get_setting("twilio_auth_token")
    phone_setting = service.get_setting("twilio_phone_number")

    sid_value = sid_setting.value if sid_setting else None
    token_value = token_setting.value if token_setting else None
    phone_value = phone_setting.value if phone_setting else None

    return TwilioConfigResponse(
        account_sid=sid_value,
        phone_number=phone_value,
        auth_token_masked=_mask_token(token_value),
    )


@router.put("/twilio", response_model=TwilioConfigResponse)
def put_twilio_config(
    request: TwilioConfigRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin),
) -> TwilioConfigResponse:
    """
    Update Twilio configuration with validation.

    The handler validates the credentials by calling the Twilio API
    (``client.api.accounts(sid).fetch()``) BEFORE persisting any setting.
    On success, the SID and phone number are stored as plaintext settings
    and the auth token is stored encrypted-at-rest via Fernet
    (``value_type="encrypted"``).

    **Error mapping:**

    - ``400`` — Twilio rejected the credentials (auth failure / SDK 401),
      OR the auth token field is the masked placeholder
      ("••••••••XXXX") rather than a real token.
    - ``502`` — Could not reach Twilio (network timeout, DNS failure,
      or any non-401 transport error).

    Only administrators can update Twilio configuration.

    Args:
        request: TwilioConfigRequest with account_sid, auth_token, phone_number
        db: Database session (injected)
        current_user: Authenticated admin user (injected)

    Returns:
        TwilioConfigResponse with masked auth token

    Raises:
        HTTPException 400: Masked placeholder submitted, or Twilio rejected
            the credentials (SDK status 401).
        HTTPException 502: Twilio API was unreachable.

    Example:
        PUT /api/v1/settings/twilio
        {
            "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "auth_token": "your-twilio-auth-token",
            "phone_number": "+15551234567"
        }
    """
    # 1. Defense-in-depth: the masked placeholder must never round-trip
    # through Twilio validation or hit the DB. Frontend should swap it for
    # a real token before submit; this guard catches programming errors.
    if _MASKED_PLACEHOLDER_PATTERN.match(request.auth_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Auth Token is the masked placeholder — re-enter the real "
                "token to update."
            ),
        )

    # 2. Validate via Twilio API call BEFORE persisting anything.
    try:
        # TwilioHttpClient is the SDK's expected http_client interface;
        # passing a raw httpx.Client silently dropped the timeout (CodeRabbit M4).
        client = Client(
            request.account_sid,
            request.auth_token,
            http_client=TwilioHttpClient(timeout=5.0),
        )
        client.api.accounts(request.account_sid).fetch()
    except TwilioRestException as exc:
        if exc.status == 401:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Twilio rejected these credentials — check the Account "
                    "SID and Auth Token."
                ),
            ) from exc
        if exc.status is not None and exc.status < 500:
            # Client-side Twilio error (e.g. 400 bad SID format, 429 rate
            # limited) — the server was reachable; surface the Twilio detail.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Twilio error ({exc.status}): {exc.msg}",
            ) from exc
        # 5xx or unknown status — genuine server-side / transport problem.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not reach Twilio for validation. Try again, or "
                "check network connectivity."
            ),
        ) from exc
    except (
        requests.exceptions.RequestException,
        httpx.TransportError,
        httpx.TimeoutException,
    ) as exc:
        # Network/transport failure (DNS, TCP timeout, TLS error, etc.).
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not reach Twilio for validation. Try again, or "
                "check network connectivity."
            ),
        ) from exc

    # 3. Persist (only after validation passed). Token is encrypted via
    # SettingsService when value_type="encrypted".
    service = SettingsService(db)
    try:
        service.set_setting(
            "twilio_account_sid",
            request.account_sid,
            value_type="str",
            description="Twilio Account SID",
        )
        service.set_setting(
            "twilio_auth_token",
            request.auth_token,
            value_type="encrypted",
            description="Twilio Auth Token (encrypted at rest via Fernet)",
        )
        service.set_setting(
            "twilio_phone_number",
            request.phone_number,
            value_type="str",
            description="Twilio sender phone number (E.164)",
        )
    except SecretsConfigurationError as exc:
        logger.error(
            "Twilio config persist failed: SECRET_KEY missing — cannot encrypt auth token"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Server is missing the SECRET_KEY environment variable "
                "required to encrypt secrets. Contact your administrator."
            ),
        ) from exc

    # 4. Audit log line — never include the token itself.
    logger.info(
        "Twilio config updated by user_id=%s",
        getattr(current_user, "id", "unknown"),
    )

    # 5. Return masked response.
    return TwilioConfigResponse(
        account_sid=request.account_sid,
        phone_number=request.phone_number,
        auth_token_masked=_mask_token(request.auth_token),
    )


@router.get("/sms-status", response_model=SMSStatusResponse)
def get_sms_status(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth),
) -> SMSStatusResponse:
    """Return current SMS configuration status.

    Used by the sidebar pill and the admin banner to surface whether
    real SMS will be sent. ``configured`` is True only when the resolved
    source is ``"db"`` or ``"env"``; ``"mock"`` and ``"none"`` both report
    ``configured=False`` (mock is informational, none is a warning).

    No DB writes or Twilio calls are performed by this endpoint. Service
    initialization may emit diagnostic logs while resolving configuration.
    """
    sms_service = SMSService(db)
    return SMSStatusResponse(
        configured=sms_service.config_source in ("db", "env"),
        source=sms_service.config_source,
    )
