"""
Pydantic schemas for settings API.

Defines request/response models for settings endpoints.
"""

import re

from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal, Optional
from datetime import datetime

# Masked placeholder rendered by the admin UI when a token is already
# stored: 8 bullets + last 4 chars of the token. The route handler
# rejects this with a friendly 400 — the schema must allow it through.
_MASKED_AUTH_TOKEN_PLACEHOLDER = re.compile(r"^•{8}[A-Za-z0-9]{4}$")


class SettingResponse(BaseModel):
    """Response model for a single setting."""

    id: int
    key: str
    value: str
    value_type: str
    description: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingUpdateRequest(BaseModel):
    """Request model for updating a setting."""

    value: Any = Field(..., description="Setting value (will be converted to appropriate type)")


class TwilioConfigRequest(BaseModel):
    """Request body for PUT /api/v1/settings/twilio.

    Validation strategy:

    - ``account_sid`` is sanity-checked with a permissive shape regex
      (two letters + 30–40 alphanumerics) so obvious garbage like
      ``"notvalid"`` fails fast at the schema layer with a field-specific
      Pydantic 422 — instead of being passed to Twilio and surfacing as
      a generic "Twilio rejected these credentials" message that doesn't
      tell the user which field is wrong (dogfood Bug #2). The pattern
      is intentionally broader than ``^AC[a-f0-9]{32}$`` because the
      test suite uses ``xx``-prefixed fixtures to avoid GitHub's Twilio
      secret scanner; a real malformed SID still gets caught by Twilio's
      401 in the route handler.
    - ``auth_token`` enforces a minimum length of 20 in a custom
      validator that explicitly allows the masked-placeholder shape
      through. The route handler then rejects the placeholder with a
      friendly 400 ("re-enter the real token to update").
    - ``phone_number`` is strict E.164 US format.
    """
    account_sid: str = Field(..., pattern=r"^[A-Za-z]{2}[A-Za-z0-9]{30,40}$")
    auth_token: str = Field(..., max_length=200)
    phone_number: str = Field(..., pattern=r"^\+1\d{10}$")

    @field_validator("auth_token")
    @classmethod
    def _auth_token_min_length_or_placeholder(cls, v: str) -> str:
        # The masked placeholder (12 chars) is allowed through so the
        # route handler can return its friendly 400. Anything else must
        # meet the real-token minimum length.
        if _MASKED_AUTH_TOKEN_PLACEHOLDER.fullmatch(v):
            return v
        if len(v) < 20:
            raise ValueError(
                "Auth Token must be at least 20 characters "
                "(paste the full token from Twilio Console)"
            )
        return v


class TwilioConfigResponse(BaseModel):
    """Response body for GET /api/v1/settings/twilio. Auth token is masked."""
    account_sid: Optional[str] = None
    phone_number: Optional[str] = None
    auth_token_masked: Optional[str] = None


class SMSStatusResponse(BaseModel):
    """Response body for GET /api/v1/settings/sms-status."""
    configured: bool
    source: Literal["db", "env", "none", "mock"]


class AutoRenewConfigResponse(BaseModel):
    """Response model for auto-renewal configuration."""

    enabled: bool = Field(..., description="Whether auto-renewal is enabled")
    threshold_weeks: int = Field(..., description="Weeks remaining to trigger renewal", ge=1, le=52)
    renew_weeks: int = Field(..., description="Number of weeks to generate during renewal", ge=1, le=104)


class AutoRenewConfigRequest(BaseModel):
    """Request model for updating auto-renewal configuration."""

    enabled: Optional[bool] = Field(None, description="Enable or disable auto-renewal")
    threshold_weeks: Optional[int] = Field(None, description="Weeks remaining to trigger renewal", ge=1, le=52)
    renew_weeks: Optional[int] = Field(None, description="Number of weeks to generate", ge=1, le=104)


class SMSTemplateResponse(BaseModel):
    """Response model for SMS template."""

    template: str = Field(..., description="SMS notification template with variables")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")
    character_count: int = Field(..., description="Template character count")
    sms_count: int = Field(..., description="Estimated SMS segments (160 chars per SMS)")
    variables: list[str] = Field(..., description="List of template variables found")


class SMSTemplateRequest(BaseModel):
    """Request model for updating SMS template."""

    template: str = Field(
        ...,
        description="SMS template with variables: {name}, {start_time}, {end_time}, {duration}",
        min_length=1,
        max_length=320,
        examples=["WhoseOnFirst Alert\n\nHi {name}, you are on-call from {start_time} to {end_time}."]
    )


class EscalationConfigResponse(BaseModel):
    """Response model for escalation contact configuration."""

    enabled: bool = Field(..., description="Whether escalation contacts are displayed on dashboard")
    primary_name: Optional[str] = Field(None, description="Primary escalation contact name")
    primary_phone: Optional[str] = Field(None, description="Primary escalation contact phone (E.164 format)")
    secondary_name: Optional[str] = Field(None, description="Secondary escalation contact name")
    secondary_phone: Optional[str] = Field(None, description="Secondary escalation contact phone (E.164 format)")


class EscalationConfigRequest(BaseModel):
    """Request model for updating escalation contact configuration."""

    enabled: bool = Field(..., description="Enable or disable escalation contact display")
    primary_name: Optional[str] = Field(None, description="Primary escalation contact name", max_length=100)
    primary_phone: Optional[str] = Field(
        None,
        description="Primary escalation contact phone (E.164 format: +1XXXXXXXXXX)",
        pattern=r"^\+1\d{10}$",
        examples=["+19187019714"]
    )
    secondary_name: Optional[str] = Field(None, description="Secondary escalation contact name", max_length=100)
    secondary_phone: Optional[str] = Field(
        None,
        description="Secondary escalation contact phone (E.164 format: +1XXXXXXXXXX)",
        pattern=r"^\+1\d{10}$",
        examples=["+19187019714"]
    )
