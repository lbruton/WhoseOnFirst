# Product Overview

## Product Purpose

WhoseOnFirst is an automated on-call rotation and SMS notification system designed for small-to-medium technical teams (5-10 members). It eliminates the error-prone manual management of on-call schedules by providing fair, algorithmic rotation with automatic SMS notifications at shift boundaries.

The core problem: manual on-call rotation is time-consuming, unfair, and prone to human error. Team members get clustered on weekends, schedules fall out of date, and nobody gets notified reliably. WhoseOnFirst solves this with a deterministic circular rotation algorithm and Twilio-powered SMS delivery.

## Target Users

**Primary: On-Call Team Members (7-person IT/DevOps team)**
- Need to know when their shift starts and ends
- Want fair distribution of weekend and double shifts
- Expect reliable 8:00 AM CST notifications via SMS
- Want visibility into the upcoming schedule from any device

**Secondary: Team Administrator (single admin managing the rotation)**
- Manages team member roster (add/remove/reorder)
- Configures shift patterns (24h and 48h durations)
- Generates and monitors schedules weeks in advance
- Reviews notification delivery history and troubleshoots failures

**Tertiary: Manager / Supervisor**
- Needs confidence that 24/7 coverage is maintained
- Wants audit trail of schedule changes and notifications
- Receives weekly escalation summary SMS (planned)

## Key Features

1. **Circular Rotation Algorithm**: Deterministic `member_index = shifts_elapsed % team_size` formula ensures every team member cycles through every shift position. No special-case weekend logic — the 48h Tuesday-Wednesday shift distributes burden naturally.

2. **Automated SMS Notifications**: Daily 8:00 AM CST notifications via Twilio with retry logic (3 attempts, exponential backoff). Supports primary and secondary phone numbers per team member for redundant delivery.

3. **Web-Based Admin Dashboard**: 8-page Tabler.io interface — Dashboard (calendar + escalation chain), Team Members (drag-drop reorder), Shifts (pattern config), Schedule Generation (1-104 weeks), Notifications (delivery history), Help & Setup, Login, Change Password.

4. **Flexible Shift Patterns**: Configurable shifts supporting 24h and 48h durations. Default: 6 shifts per week (Mon 24h, Tue-Wed 48h, Thu 24h, Fri 24h, Sat 24h, Sun 24h).

5. **Session-Based Authentication**: Argon2id password hashing, Admin/Viewer role tiers, HTTPOnly cookies with SameSite protection.

6. **Docker Containerized Deployment**: Single-container deployment via Docker/Podman. Production runs on Portainer with GitOps from the `main` branch. Named volume preserves SQLite database across redeploys.

## Business Objectives

- **Eliminate manual scheduling overhead**: Admin spends fewer than 5 minutes/week on rotation management (vs. hours previously)
- **Ensure fair rotation**: Zero instances of unfair weekend clustering — mathematically guaranteed by the algorithm
- **Achieve reliable notifications**: 100% on-time SMS delivery at 8:00 AM CST (within 60-second window)
- **Enable corporate deployment**: Package for air-gapped RHEL Kubernetes environments with offline installer (Phase 2)
- **Minimize operational cost**: Single SQLite database, single container, Twilio SMS at ~$0.0079/message

## Success Metrics

- **Notification reliability**: 100% on-time delivery (8:00 AM CST +/- 1 minute)
- **Fairness guarantee**: Over N weeks (where N = team_size), every member gets equal distribution of all shift positions
- **Admin efficiency**: Less than 5 minutes required for any administrative task
- **System uptime**: 99.9% during business hours (8 AM - 8 PM CST)
- **Test coverage**: Maintain >80% overall, 100% on rotation algorithm

## Product Principles

1. **Fairness is non-negotiable**: The rotation algorithm is the heart of the product. It must be deterministic, mathematically provable, and have 100% test coverage. No manual overrides should break the fairness guarantee for future rotations.

2. **Simplicity over features**: This serves a 7-person team, not an enterprise. Every feature must justify its complexity. A single SQLite database, a single container, and vanilla JavaScript are deliberate choices — not limitations.

3. **Notifications must be reliable**: If an on-call person doesn't get their SMS, the system has failed its primary job. Retry logic, delivery logging, and dual-phone support all serve this principle.

4. **Admin self-service**: The admin should never need to touch the database, edit config files, or SSH into the server for routine operations. Everything is managed through the web UI.

5. **Offline-capable deployment**: The corporate target environment is air-gapped RHEL with Kubernetes. The architecture must support offline installation and operation without internet dependencies (except Twilio for SMS).

## Monitoring & Visibility

- **Dashboard Type**: Web-based (Tabler.io/Bootstrap 5), responsive for mobile and tablet
- **Real-time Updates**: Page refresh (no WebSocket) — appropriate for a schedule that changes weekly, not per-second
- **Key Metrics Displayed**: Current month calendar with color-coded team members, escalation chain (primary/backup/tertiary), notification delivery stats (sent/failed/pending), 14-day schedule preview
- **Sharing Capabilities**: Read-only Viewer role for team members; Cloudflare Zero Trust access for remote viewing

## Future Vision

### Near-Term (Phase 2-3)
- **Offline installer**: Container bundle for air-gapped RHEL Kubernetes corporate deployment
- **Manual shift overrides**: One-time swap/override without breaking rotation continuity
- **Weekly escalation summary**: Monday 8 AM SMS to supervisors with the week's schedule
- **Multi-level notifications**: Primary/Backup/Escalation SMS at each shift start
- **Auto-regeneration**: Schedule rebuilds automatically when team or shift config changes

### Long-Term (Phase 4)
- **PostgreSQL migration**: For multi-instance and horizontal scaling
- **Multi-team support**: Independent rotations for multiple teams
- **Calendar export**: iCal format for Google Calendar / Outlook integration
- **Teams/Slack integration**: Notification delivery via corporate messaging platforms
- **Mobile application**: Native iOS/Android with push notifications
