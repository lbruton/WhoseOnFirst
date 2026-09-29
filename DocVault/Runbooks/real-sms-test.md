---
tags:
  - runbook
  - whoseonfirst
doc_type: runbook
project: whoseonfirst
created: "2026-04-22"
updated: "2026-04-22"
---

# Real SMS Test Runbook

**Purpose:** For rare cases when you need to send a real SMS to verify Twilio delivery. Used maybe once per quarter.

## Prerequisites

- Dev container running — verify with `docker ps --filter name=whoseonfirst-dev`
- Production container still running on Portainer (this test does not affect it)
- Access to [[Infisical]] WhoseOnFirst/prod secrets (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`)
- Your personal phone number ready in E.164 format (`+1XXXXXXXXXX`)

## Pre-Test Safety Checklist

Complete before starting:

- [ ] Confirmed dev container is currently in mock mode (check logs for `[MOCK]`)
- [ ] Have Twilio creds from Infisical ready (do NOT paste them into chat)
- [ ] Know your personal phone number in E.164 format (`+1XXXXXXXXXX`)
- [ ] Production container on Portainer is UNTOUCHED

## Steps

### 1. Create `.env.dev` in project root with real Twilio creds

```env
SMS_MOCK_MODE=false
TWILIO_ACCOUNT_SID=<from Infisical>
TWILIO_AUTH_TOKEN=<from Infisical>
TWILIO_PHONE_NUMBER=<from Infisical>
```

### 2. Uncomment `env_file:` stanza in `docker-compose.dev.yml`

Uncomment the `env_file:` block (lines 99-100) so the dev container picks up `.env.dev`.

### 3. Restart the dev container

```bash
docker-compose -f docker-compose.dev.yml restart
```

### 4. Log into admin UI

Open `localhost:8900` and log in with admin credentials.

### 5. Change ONE test team member's phone number

Set a single test team member's phone to **your personal number** only.

### 6. Send Manual Notification

Go to Notifications page and click **Send Manual Notification** to that member.

### 7. Verify SMS received

Confirm the SMS arrived on your phone.

### 8. Check notification logs

In the admin UI, confirm the notification logs show successful delivery.

## Post-Test Revert Checklist (MANDATORY)

> [!warning] Every item below is required. Do not skip any step.

- [ ] Delete `.env.dev` file: `rm .env.dev`
- [ ] Re-comment `env_file:` stanza in `docker-compose.dev.yml` (if you uncommented it)
- [ ] Restart container: `docker-compose -f docker-compose.dev.yml restart`
- [ ] Verify mock mode active: check logs for `SMS service initialized in mock mode`
- [ ] Restore test member's phone number if changed in DB (or just restart — first-boot seeds fresh data)

> [!danger] NEVER send test SMS to real team members
> Only use your own phone number. The production container handles real team notifications.
> If you forget to revert, the dev scheduler will attempt to send real SMS at 8 AM CST.
