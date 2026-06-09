---
name: block-live-twilio-creds
enabled: true
event: file
pattern: TWILIO_ACCOUNT_SID\s*=\s*AC[a-f0-9]|TWILIO_AUTH_TOKEN\s*=\s*[a-f0-9]{20,}
action: block
---

BLOCKED: Live Twilio credentials detected in file write.

Production Twilio creds must ONLY exist in Infisical/Portainer stack env vars — never on disk.
Local .env must use empty values or dummy placeholders. docker-compose.dev.yml sets SMS_MOCK_MODE=true
and uses fake creds (ACdev_mock_account_sid_not_real).

If both dev and production containers run with real creds, DUPLICATE SMS fires to real coworkers at 8 AM CST.
