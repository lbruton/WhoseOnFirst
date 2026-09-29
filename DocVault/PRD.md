---
tags: []
doc_type: prd
project: whoseonfirst
source: migrated
aliases: ["WhoseOnFirst PRD"]
created: "2025-11-21"
updated: "2026-06-09"
migrated_from: "repo:docs/planning/PRD.md"
---

# Product Requirements Document (PRD)
## WhoseOnFirst - On-Call Team SMS Notifier

**Version:** 2.0 (Living Document)  
**Last Updated:** November 10, 2025  
**Current Phase:** Phase 2 - Deployment & Authentication  
**Status:** ✅ Phase 1 Complete (v1.0.0)  
**Author:** Development Team

---

## 📋 Living Document Guide

This PRD is a **living document** that evolves with the product. It serves as the authoritative source for all requirements.

### Status Indicators
- ✅ **Complete** - Implemented and released (includes version number)
- 🔄 **In Progress** - Currently being implemented (includes Linear issue)
- 📋 **Planned** - Approved for future implementation
- 🔮 **Vision** - Long-term ideas, not yet approved

### Linking to Linear
New requirements (REQ-026+) are tracked in Linear with cross-references:
- **In PRD:** `REQ-026: Manual Shift Override UI (WHO-5)`
- **In Linear:** `WHO-5: REQ-026 - Manual Shift Override UI`

### Adding New Requirements
1. Pick next sequential REQ-XXX number
2. Create Linear issue: `REQ-XXX - [Feature Name]`
3. Add to PRD with Linear reference
4. Update when completed with version number

**Template:** See [New Requirement Template](#new-requirement-template) section below.

---

## Executive Summary

WhoseOnFirst is an automated on-call rotation and SMS notification system designed to manage fair scheduling for technical teams. The system ensures equitable shift distribution using a simple circular rotation algorithm, schedules the double-shift during the workweek (Tue-Wed) to minimize weekend impact, and automatically notifies on-call personnel at shift start times.

**Current Status:** Phase 1 MVP complete (v1.0.0) - Backend, frontend, testing, and Docker deployment all operational. Awaiting Twilio 10DLC approval (~1 week). Phase 2 (offline installer + authentication) in planning.

---

## Problem Statement

### Current Pain Points
- Manual on-call rotation management is error-prone and time-consuming
- No automated notification system for shift changes
- Difficulty ensuring fair rotation across team members
- Challenge in preventing individuals from being on-call multiple weekend days consecutively
- Need for flexible shift patterns (24-hour and 48-hour shifts)
- Team size fluctuations require dynamic schedule adjustments

### Target Users
- **Primary:** IT/DevOps teams of 5-10 members requiring on-call coverage
- **Secondary:** Team leads and managers who manage on-call schedules
- **Future:** Organizations with multiple teams requiring coordinated coverage

---

## Goals and Objectives

### Primary Goals
1. ✅ Automate daily SMS notifications to on-call personnel at 8:00 AM CST *(v1.0.0)*
2. ✅ Implement fair rotation algorithm ensuring no weekend-day clustering *(v1.0.0)*
3. ✅ Provide simple administrative interface for schedule management *(v1.0.0)*
4. ✅ Support flexible shift patterns (24-hour and 48-hour durations) *(v1.0.0)*
5. ✅ Enable easy addition/removal of team members *(v1.0.0)*

### Success Metrics
- ✅ 100% on-time notification delivery (8:00 AM CST ±1 minute) - *Pending Twilio approval*
- ✅ Zero instances of unfair weekend distribution - *Achieved via 48h Tue-Wed shift*
- ✅ <5 minutes required for administrative tasks - *Achieved via intuitive UI*
- 📋 99.9% system uptime during business hours - *Production validation pending*
- ✅ Successful deployment within 90 days - *Achieved: 5 days ahead of schedule*

---

## User Stories

### As an On-Call Team Member
- ✅ I want to receive an SMS at 8:00 AM CST when my shift starts *(v1.0.0)*
- ✅ I want to know exactly when my shift ends *(v1.0.0)*
- ✅ I want fair weekend distribution so I'm not on-call multiple weekend days *(v1.0.0)*
- ✅ I want visibility into the upcoming schedule *(v1.0.0 - Dashboard calendar)*

### As a Team Administrator
- ✅ I want to easily add/remove team members from rotation *(v1.0.0)*
- ✅ I want to customize shift patterns (days and durations) *(v1.0.0)*
- 📋 I want to manually override the schedule when needed *(REQ-037)*
- ✅ I want to see a history of notifications sent *(v1.0.0)*
- ✅ I want to ensure fair rotation across all team members *(v1.0.0)*

### As a Manager
- ✅ I want confidence that coverage is maintained 24/7 *(v1.0.0)*
- ✅ I want audit logs of all schedule changes *(v1.0.0 - notification_log table)*
- ✅ I want to see notification delivery status *(v1.0.0)*
- ✅ I want minimal maintenance overhead *(v1.0.0 - Docker deployment)*

---

## Functional Requirements

### Core Features (Phase 1 - MVP)

**Status:** ✅ Complete (v1.0.0)  
**Last Updated:** November 9, 2025

#### 1. Team Member Management

**REQ-001: Store Team Member Information**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall store team member information including name, phone number (E.164 format), active status, and rotation order.

**REQ-002: Add New Team Members**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall support adding new team members via web UI with phone validation and automatic rotation order assignment.

**REQ-003: Remove/Deactivate Team Members**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall support soft delete (deactivation) and hard delete (Shift+Click with name confirmation) of team members with automatic rotation order renumbering.

**REQ-004: Phone Number Validation**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall validate phone numbers for E.164 format (+1XXXXXXXXXX) on both frontend and backend.

**REQ-005: Prevent Duplicate Phone Numbers**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall enforce unique constraint on phone numbers and display user-friendly error messages.

#### 2. Shift Configuration

**REQ-006: Configurable Shift Patterns**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall support configurable shift patterns with shift number, day of week, duration, and start time.

**REQ-007: 24-Hour Shift Support**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall support 24-hour shift durations.

**REQ-008: 48-Hour Shift Support**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall support 48-hour shift durations spanning two consecutive days (e.g., Tuesday-Wednesday).

**REQ-009: Assign Shifts to Days**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall assign shifts to specific days of the week with validation for consecutive days on 48h shifts.

**REQ-010: Sequential Shift Numbering**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** Medium  
System shall number shifts sequentially (1-7) with automatic next-available number suggestion.

#### 3. Schedule Generation

**REQ-011: Fair Circular Rotation Algorithm**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** Critical  
System shall implement fair circular rotation using formula: `member_index = shifts_elapsed % team_size` where `shifts_elapsed = (week * shift_count) + shift_index`. This ensures all team members cycle through all shifts continuously.

**REQ-012: Workweek Double-Shift Distribution**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall schedule the 48-hour double shift during workweek (Tuesday-Wednesday) to minimize weekend impact and distribute burden fairly.

**REQ-013: Weekly Rotation**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall rotate shift assignments weekly where each team member moves through all shifts continuously.

**REQ-014: Advance Schedule Generation**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall generate schedules from 1 to 104 weeks in advance (default 4 weeks).

**REQ-015: Recalculate on Team Changes**  
**Status:** ✅ Complete (v1.0.0) - Manual regeneration  
**Priority:** Medium  
**Note:** Manual regeneration via Schedule Generation page. Auto-regeneration planned in REQ-039.  
System shall allow administrators to regenerate schedules when team composition changes.

#### 4. SMS Notifications

**REQ-016: Daily SMS at 8:00 AM CST**  
**Status:** ✅ Complete (v1.0.0) - Pending Twilio approval  
**Priority:** Critical  
System shall send SMS notifications at 8:00 AM CST daily via APScheduler with America/Chicago timezone.

**REQ-017: SMS Message Content**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
SMS message shall include shift start time, duration, end time, and editable template (stored in LocalStorage for MVP).

**REQ-018: Twilio API Integration**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** Critical  
System shall use Twilio API for SMS delivery with verified working integration.

**REQ-019: Log SMS Attempts**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall log all SMS attempts including status, Twilio SID, timestamp, and error messages to notification_log table.

**REQ-020: Retry Failed SMS**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall retry failed SMS notifications up to 3 times with exponential backoff (0s, 60s, 120s).

#### 5. Administrative Interface

**REQ-021: Web-Based Admin Dashboard**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
System shall provide web-based admin dashboard with 8 pages: Dashboard, Team Members, Shifts, Schedule Generation, Notifications, Help & Setup, Change Password, Login.

**REQ-022: Current Week Schedule Display**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
Dashboard shall display current month's schedule with dynamic calendar, on-call escalation chain, and color-coded team legend.

**REQ-023: Upcoming Schedule View**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
Dashboard shall show upcoming schedules with 14-day preview in Schedule Generation page.

**REQ-024: Manual Schedule Overrides**  
**Status:** 📋 Planned (REQ-037)  
**Priority:** Medium  
Dashboard shall allow manual schedule overrides for one-time exceptions (vacation, swaps). *Deferred to Phase 3.*

**REQ-025: Notification History**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** High  
Dashboard shall display notification history with delivery stats, recent 50 SMS, and status indicators.

---

### Enhanced Features (Phase 2 - Deployment & Auth)

**Status:** 🔄 In Progress  
**Last Updated:** November 10, 2025

**REQ-026: Docker Containerization**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** Critical  
System shall be fully containerized with Docker/Podman support, multi-stage Dockerfile, and docker-compose configurations for development (port 8900) and production (port 8000).

**REQ-027: Authentication System**  
**Status:** ✅ Complete (v1.0.0)  
**Priority:** Critical  
System shall implement session-based authentication with Argon2id password hashing, two-tier roles (Admin/Viewer), and HTTPOnly cookies with SameSite protection.

**REQ-028: Offline Installer (WHO-5)**  
**Status:** 📋 Planned  
**Priority:** High  
**Linear:** [WHO-5](https://linear.app/hextrackr/issue/WHO-5)  
System shall provide offline installer bundle for air-gapped RHEL 10 deployment with pre-downloaded container images and vendored dependencies.

**REQ-029: HTTPS Support (WHO-6)**  
**Status:** 📋 Planned  
**Priority:** High  
**Linear:** [WHO-6](https://linear.app/hextrackr/issue/WHO-6)  
System shall support HTTPS in production via nginx reverse proxy configuration.

**REQ-030: Production Deployment Validation (WHO-7)**  
**Status:** 📋 Planned  
**Priority:** High  
**Linear:** [WHO-7](https://linear.app/hextrackr/issue/WHO-7)  
System shall be validated in production RHEL 10 VM with 1-week trial period monitoring SMS delivery and system stability.

---

### Advanced Features (Phase 3 - Enhancements)

**Status:** 📋 Planned  
**Last Updated:** November 10, 2025

**REQ-031: Email Notification Backup (WHO-8)**  
**Status:** 📋 Planned  
**Priority:** Medium  
**Linear:** [WHO-8](https://linear.app/hextrackr/issue/WHO-8)  
System shall support email notifications as backup to SMS via SendGrid, AWS SES, or SMTP.

**REQ-032: Enhanced Reporting (WHO-9)**  
**Status:** 📋 Planned  
**Priority:** Low  
**Linear:** [WHO-9](https://linear.app/hextrackr/issue/WHO-9)  
System shall provide analytics dashboard with fairness metrics, notification delivery rates, and historical trends.

**REQ-033: Settings UI for Twilio (WHO-10)**  
**Status:** 📋 Planned  
**Priority:** Medium  
**Linear:** [WHO-10](https://linear.app/hextrackr/issue/WHO-10)  
System shall provide UI for managing Twilio credentials instead of .env file configuration.

**REQ-034: Global SMS Template Management (WHO-11)**  
**Status:** 📋 Planned  
**Priority:** Low  
**Linear:** [WHO-11](https://linear.app/hextrackr/issue/WHO-11)  
System shall store SMS templates in database with backend API instead of browser LocalStorage.

**REQ-035: PTO/Vacation Management (WHO-12)**  
**Status:** 📋 Planned  
**Priority:** Low  
**Linear:** [WHO-12](https://linear.app/hextrackr/issue/WHO-12)  
System shall provide PTO calendar with conflict warnings and automatic schedule adjustment.

**REQ-036: Team Member Self-Service Portal (WHO-13)**  
**Status:** 📋 Planned  
**Priority:** Low  
**Linear:** [WHO-13](https://linear.app/hextrackr/issue/WHO-13)  
System shall allow team members to view their own schedules and request shift swaps (requires authentication expansion).

**REQ-037: Manual Shift Override UI (WHO-14)**  
**Status:** 📋 Planned  
**Priority:** Medium  
**Linear:** [WHO-14](https://linear.app/hextrackr/issue/WHO-14)

System shall provide UI for manual shift overrides:
- Select future date and shift
- Manually assign different team member
- Override applies to single occurrence only (doesn't affect rotation)
- Visual indicator in calendar for overridden shifts
- Audit log of all manual overrides

**Acceptance Criteria:**
- [ ] UI to select date + shift for override
- [ ] Dropdown to select replacement team member
- [ ] Save override without affecting rotation algorithm
- [ ] Calendar displays override indicator (different color/icon)
- [ ] Notification sent to overridden member (not original)
- [ ] Admin can remove/edit overrides before effective date

**REQ-038: Multi-Level SMS Notifications (WHO-15)**  
**Status:** 📋 Planned  
**Priority:** Medium  
**Linear:** [WHO-15](https://linear.app/hextrackr/issue/WHO-15)

System shall send escalation chain SMS notifications:
- Send 3 SMS messages per shift start (Primary, Secondary, Tertiary)
- Primary: "You are PRIMARY on-call. Backup: [Name]. Escalation: [Name]"
- Secondary: "You are BACKUP on-call. Primary: [Name]. Escalation: [Name]"
- Tertiary: "You are ESCALATION on-call. Primary: [Name]. Backup: [Name]"
- Uses rotation_order-based backup calculation (already implemented in frontend Dashboard)

**Acceptance Criteria:**
- [ ] Calculate escalation chain based on rotation_order
- [ ] Compose 3 different message templates
- [ ] Send 3 SMS concurrently at 8:00 AM CST
- [ ] Log all 3 notifications separately
- [ ] Frontend toggle to enable/disable multi-level notifications
- [ ] Update notification history to show escalation level

**REQ-039: Auto-Regeneration on Config Changes (WHO-16)**  
**Status:** 📋 Planned  
**Priority:** Medium  
**Linear:** [WHO-16](https://linear.app/hextrackr/issue/WHO-16)

System shall automatically regenerate schedules when configuration changes:
- Auto-regenerate when team members added/removed/reordered
- Auto-regenerate when shifts added/modified/deleted
- Warning banner if changes detected but schedule not regenerated
- Admin setting to toggle auto-regeneration vs. manual trigger

**Acceptance Criteria:**
- [ ] Detect team member CRUD operations
- [ ] Detect shift configuration changes
- [ ] Show warning banner on Dashboard when changes detected
- [ ] Backend API to check if regeneration needed
- [ ] Setting to enable/disable auto-regeneration
- [ ] Preserve notification history when regenerating

**REQ-049: Optional Second Phone Number for Dual-Device Paging (WHO-17)**
**Status:** ✅ Complete (v1.2.0)
**Priority:** Medium
**Linear:** [WHO-17](https://linear.app/hextrackr/issue/WHO-17)

System shall support optional second phone number per team member for redundant notification delivery:
- Add optional "secondary_phone" field to team_members table
- Validate secondary phone in E.164 format (same as primary)
- Send SMS to both phone numbers when secondary is configured
- Display both phone numbers in Team Members page
- Log notifications for both numbers separately
- Allow independent retry logic for each number

**Acceptance Criteria:**
- [ ] Database migration adds nullable secondary_phone column
- [ ] Team Members page shows secondary phone input field
- [ ] Frontend validates secondary phone format (E.164)
- [ ] Backend sends concurrent SMS to both numbers at shift start
- [ ] Notification log shows separate entries for primary/secondary
- [ ] Retry logic handles primary/secondary failures independently
- [ ] Dashboard escalation chain displays both numbers when configured

**Implementation Notes:**
- Use async/concurrent Twilio API calls for both numbers
- Secondary phone is completely optional (nullable)
- No impact to existing single-phone workflows
- Consider Twilio rate limits when sending 2x SMS per shift

**Dependencies:**
- None - independent feature

**Testing:**
- Test single phone (backward compatibility)
- Test dual phone (concurrent delivery)
- Test secondary phone validation
- Test notification log with dual entries
- Test retry logic for mixed success/failure scenarios

**REQ-050: Global Team Member Color Consistency System (WHO-22)**
**Status:** 📋 Planned
**Priority:** Medium
**Linear:** [WHO-22](https://linear.app/hextrackr/issue/WHO-22)

System shall provide consistent avatar color assignment for team members across all pages and sessions:
- Add `color` field to team_members table (VARCHAR(20), stores CSS class like "team-color-1")
- Assign color from 16-color WCAG AA palette on member creation
- Return color in all API responses (GET /api/v1/team-members)
- Replace page-specific color algorithms with database-driven colors
- Support manual color override via Team Members edit page (future)

**Acceptance Criteria:**
- [ ] Database migration adds `color` column to team_members table
- [ ] Assign colors to existing members (sorted by ID for consistency)
- [ ] Update Pydantic schemas to include `color` field
- [ ] Replace `getTeamColor()` functions on all 4 pages with `member.color`
- [ ] Gary K shows same color on Dashboard, Team Members, Schedule, and Notifications
- [ ] New members automatically get next available color from palette
- [ ] Color persists across sessions and page refreshes

**Implementation Notes:**
- Current issue: 3 different pages use 3 different color assignment algorithms
  - Dashboard/Notifications: Sort by ID → find position → modulo
  - Schedule page: Loop index → modulo (no sorting!)
  - Team Members page: forEach index → modulo (different sort!)
- Result: Same member appears in different colors depending on page
- Database approach provides single source of truth
- Consider "color pool" tracking to prevent collisions when all 16 colors in use
- Color field optional on creation (auto-assigned by backend)

**Dependencies:**
- None - independent feature

**Testing:**
- Verify Gary K shows same color on all 4 pages
- Test new member creation (gets next available color)
- Test color persistence across sessions
- Test manual color override (future enhancement)
- Verify existing members get consistent colors after migration

---

**REQ-051: Weekly Escalation Contact Schedule Summary (WHO-23)**
**Status:** 📋 Planned
**Priority:** High (Supervisor Request)
**Linear:** [WHO-23](https://linear.app/hextrackr/issue/WHO-23)

System shall send automated weekly SMS summary to escalation contacts every Monday at 8:00 AM CST with upcoming 7-day on-call schedule:
- New APScheduler job runs Monday 8am CST
- Query schedules for next 7 days (Mon-Sun)
- Compose message with day, team member name, and primary phone
- Send to both escalation contacts (primary + secondary phones)
- Log sends with category `escalation_weekly`
- Settings modal toggle to enable/disable weekly summary
- Manual "Send Test Weekly Summary" button for testing

**SMS Format Example:**
```
WhoseOnFirst Weekly Schedule (Nov 18-24)

Mon 11/18: Lance B +19187019714
Tue 11/19: Gary K +19187019714 (48h)
Wed 11/20: Gary K (continues)
Thu 11/21: Troy M +19187019714
...

Questions? Reply to this message.
```

**Acceptance Criteria:**
- [ ] Scheduler job runs every Monday 8:00 AM CST
- [ ] SMS sent to escalation primary and secondary phones
- [ ] Message lists 7 days with name + primary phone only
- [ ] 48h shifts marked with "(48h)" and "(continues)"
- [ ] Settings: `escalation_weekly_enabled` (boolean)
- [ ] Settings: `escalation_weekly_template` (text)
- [ ] Notification log entries with category `escalation_weekly`
- [ ] Settings modal: Toggle and "Send Test" button
- [ ] Manual trigger endpoint for testing

**Implementation Notes:**
- Builds on existing scheduler and SMS service infrastructure
- Query pattern: Next Monday 00:00:00 + 7 days
- Character count: ~320 chars (2 SMS segments, ~$0.016/recipient)
- Weekly cost: ~$0.032/week (~$0.13/month) for 2 recipients
- No new tables needed (uses existing settings table)
- Template stored in settings, customizable by admin

**Dependencies:**
- WHO-17 (Dual-Device SMS) - Complete v1.2.0

**Testing:**
- Verify Monday 8am job execution
- Test 7-day query returns correct schedules
- Validate 48h shift display logic
- Test toggle enable/disable persistence
- Verify SMS delivery to both escalation phones
- Test manual trigger endpoint

---

**REQ-052: Calendar Card Phone Display Enhancement (WHO-24)**
**Status:** 📋 Planned
**Priority:** Medium (UX Polish)
**Linear:** [WHO-24](https://linear.app/hextrackr/issue/WHO-24)

System shall enhance calendar card phone display to match header escalation chain pattern:
- Add mobile icon (`ti ti-device-mobile`) before phone numbers
- Show primary phone always visible in card
- Show secondary phone in Bootstrap tooltip on hover (if configured)
- Tooltip format: "Secondary: +1918XXXXXXX"
- No tooltip if team member has no secondary phone
- Maintain current card colors and layout

**Acceptance Criteria:**
- [ ] Calendar cards display mobile icon before phone number
- [ ] Icon matches header pattern (icon before number)
- [ ] Primary phone always visible
- [ ] Secondary phone in tooltip on hover (if exists)
- [ ] No tooltip for single-phone members
- [ ] Tooltips work on desktop (hover) and mobile (tap)
- [ ] Cards grow naturally to accommodate content
- [ ] No layout breakage across screen sizes

**Implementation Notes:**
- Frontend-only change (no API modifications)
- Use Bootstrap tooltip component (`data-bs-toggle="tooltip"`)
- Tooltip pattern prepares for WHO-14 (manual overrides) gray line display
- Secondary phone discoverable without cluttering cards
- Tabler Icons font already loaded (no additional requests)
- Dispose tooltips before re-rendering calendar

**Dependencies:**
- WHO-17 (Dual-Device SMS) - Complete v1.2.0 (provides `secondary_phone` field)

**Testing:**
- Visual: Icon displays on all calendar cards
- Tooltip: Hover shows secondary phone (when exists)
- Mobile: Tap shows tooltip on touch devices
- Data: Test with/without secondary phone
- Browser: Chrome, Firefox, Safari, Mobile Safari, Mobile Chrome

---

### Future Vision (Phase 4 - Advanced Features)

**Status:** 🔮 Vision (Not Yet Approved)  
**Last Updated:** November 10, 2025

**REQ-040: Multi-Team Support**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall support multiple independent teams with separate rotations and schedules.

**REQ-041: PostgreSQL Migration**  
**Status:** 🔮 Vision  
**Priority:** Medium  
System shall migrate from SQLite to PostgreSQL for production scalability with data migration utilities.

**REQ-042: Microsoft Teams Integration**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall integrate with Microsoft Teams for notifications and schedule visibility.

**REQ-043: Slack Integration**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall integrate with Slack for notifications and bot commands.

**REQ-044: REST API for External Integrations**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall provide RESTful API with API key authentication for external system integrations.

**REQ-045: Mobile Application**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall provide mobile applications (iOS/Android) for on-call personnel with push notifications and schedule visibility.

**REQ-046: Calendar Export**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall support iCal format export for calendar integration (Google Calendar, Outlook, etc.).

**REQ-047: Webhook Support**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall support webhooks for schedule changes and notification events.

**REQ-048: Advanced Analytics Dashboard**  
**Status:** 🔮 Vision  
**Priority:** Low  
System shall provide advanced analytics with fairness metrics, historical trends, and custom reports.

---

## Non-Functional Requirements

### Performance

**NFR-001: SMS Delivery Timing**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** SMS notifications within 60 seconds of scheduled time  
**Achieved:** APScheduler precision with 5-minute misfire grace time

**NFR-002: Web Dashboard Load Time**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** <2 seconds load time  
**Achieved:** Minimal API calls, optimized queries with indexes

**NFR-003: API Response Time**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** <500ms (95th percentile)  
**Achieved:** Simple queries, SQLAlchemy ORM optimization

**NFR-004: Team Size Support**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Up to 20 team members without degradation  
**Tested:** 8 members, algorithm works for 1-16+ members

### Reliability

**NFR-005: System Uptime**  
**Status:** 📋 Planned  
**Target:** 99.9% uptime during business hours (8 AM - 8 PM CST)  
**Note:** Production validation pending

**NFR-006: Data Persistence**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Reliable data persistence  
**Achieved:** SQLite WAL journal mode, Docker named volumes

**NFR-007: Transient Failure Recovery**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Automatic recovery from transient failures  
**Achieved:** SMS retry logic (3 attempts), exponential backoff

**NFR-008: Scheduler Resume**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Scheduler resumes after restart without missing notifications  
**Achieved:** SQLAlchemy job store, misfire grace time

### Security

**NFR-009: Credential Storage**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Store credentials in environment variables  
**Achieved:** .env file with .gitignore exclusion

**NFR-010: HTTPS Enforcement**  
**Status:** 📋 Planned  
**Target:** HTTPS for all web traffic  
**Note:** Production nginx reverse proxy pending

**NFR-011: Input Sanitization**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Prevent injection attacks  
**Achieved:** Pydantic validation, SQLAlchemy ORM (no raw SQL)

**NFR-012: Phone Number Privacy**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Secure phone storage, sanitized logs  
**Achieved:** Database encryption, masked last 4 digits in logs

### Scalability

**NFR-013: PostgreSQL Migration Path**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Architecture supports PostgreSQL migration  
**Achieved:** SQLAlchemy abstraction, no SQLite-specific queries

**NFR-014: Horizontal Scaling Support**  
**Status:** 🔮 Vision  
**Target:** Architecture supports horizontal scaling  
**Note:** Phase 4 consideration

**NFR-015: Multi-Tenant Schema**  
**Status:** 🔮 Vision  
**Target:** Database schema supports multi-tenant  
**Note:** Phase 4 consideration

### Maintainability

**NFR-016: Test Coverage**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** >80% test coverage  
**Achieved:** 85% overall (288 tests), 100% rotation algorithm

**NFR-017: Comprehensive Logging**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Log all important events  
**Achieved:** APScheduler logs, SMS logs, API logs

**NFR-018: Externalized Configuration**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** No hard-coded values  
**Achieved:** Environment variables for all config

**NFR-019: Modern Python Best Practices**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** Type hints, async/await where appropriate  
**Achieved:** Full type hints, FastAPI async support

### Usability

**NFR-020: Intuitive Admin Interface**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** No training required  
**Achieved:** Tabler.io UI, clear navigation, help page

**NFR-021: Concise SMS Messages**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** <160 characters (single SMS)  
**Achieved:** Editable template with character counter

**NFR-022: Actionable Error Messages**  
**Status:** ✅ Complete (v1.0.0)  
**Target:** User-friendly errors  
**Achieved:** Pydantic validation messages, HTTP status codes

---

## Technical Constraints

### Infrastructure
- **CONSTRAINT-001:** Must run on RHEL 10 ✅
- **CONSTRAINT-002:** Must support Docker containerization ✅ (v1.0.0)
- **CONSTRAINT-003:** Must operate in air-gapped environment (offline installer pending)
- **CONSTRAINT-004:** Must use approved SMS provider (Twilio) ✅

### Technology Stack
- **CONSTRAINT-005:** Backend must use Python 3.11+ ✅
- **CONSTRAINT-006:** Must use FastAPI framework ✅
- **CONSTRAINT-007:** Must support SQLite for initial deployment ✅
- **CONSTRAINT-008:** Must support PostgreSQL migration path ✅

### Development
- **CONSTRAINT-009:** Development environment: macOS with Docker Desktop ✅
- **CONSTRAINT-010:** Testing environment: Proxmox home lab ✅
- **CONSTRAINT-011:** Version control: Git/GitHub ✅
- **CONSTRAINT-012:** Primary development tool: Claude Code CLI ✅

---

## Use Case: Typical Weekly Rotation

### Example Team Configuration
**Team Members:** Bob, Dave, Steve, John, Paul, Matt, Sam, Lance (8 members)

**Shift Pattern:**
- Shift 1: Monday (24 hours, 8am-8am)
- Shift 2: Tuesday-Wednesday (48 hours, 8am-8am)
- Shift 3: Thursday (24 hours, 8am-8am)
- Shift 4: Friday (24 hours, 8am-8am)
- Shift 5: Saturday (24 hours, 8am-8am)
- Shift 6: Sunday (24 hours, 8am-8am)

### Week 1 Assignments
| Shift | Day(s) | Duration | Assigned To |
|-------|--------|----------|-------------|
| 1 | Monday | 24h | Bob |
| 2 | Tue-Wed | 48h | Dave |
| 3 | Thursday | 24h | Steve |
| 4 | Friday | 24h | John |
| 5 | Saturday | 24h | Paul |
| 6 | Sunday | 24h | Matt |

*Note: Sam and Lance rotate in during Week 2*

### Week 2 Assignments (Continuous Rotation)
| Shift | Day(s) | Duration | Assigned To |
|-------|--------|----------|-------------|
| 1 | Monday | 24h | Sam |
| 2 | Tue-Wed | 48h | Lance |
| 3 | Thursday | 24h | Bob |
| 4 | Friday | 24h | Dave |
| 5 | Saturday | 24h | Steve |
| 6 | Sunday | 24h | John |

### Fairness Algorithm (Circular Rotation)
- Formula: `shifts_elapsed = (week * shift_count) + shift_index`
- Member assignment: `member_index = shifts_elapsed % team_size`
- **All team members cycle through all shifts continuously**
- No special weekend logic needed - 48h Tue-Wed shift distributes burden fairly
- With 8 members and 6 shifts, two people are "off" each week, rotating through team
- Over 8 weeks, every member gets equal distribution of all shifts including the double shift

**Implementation:** 100% test coverage in `tests/test_rotation_algorithm.py`

---

## Sample SMS Messages

### Standard Shift Start Notification (Editable Template)
```
WhoseOnFirst: Your on-call shift has started.
Duration: 24 hours (until 8:00 AM CST tomorrow)
Questions? Contact admin.
```

### Multi-Day Shift Notification (Editable Template)
```
WhoseOnFirst: Your 48h shift has started.
Until 8:00 AM CST Thursday. Questions? Contact admin.
```

**Note:** SMS template editable in Notifications page (stored in LocalStorage for MVP, backend API planned in REQ-034).

---

## Out of Scope

The following features are explicitly out of scope for initial releases:
- Voice call notifications (SMS only for MVP)
- Integration with ticketing systems (Phase 4+)
- Automated incident escalation (not scheduling focus)
- On-call payment/compensation tracking (HR/payroll system responsibility)
- Advanced PTO conflict detection (REQ-035 provides basic support)
- Self-service shift swapping without admin approval (requires auth expansion)

---

## Dependencies

### External Services
- ✅ Twilio API (SMS provider) - Integration complete, pending 10DLC approval
- 📋 RHEL 10 VM (production environment) - Available, deployment pending

### Internal Dependencies
- None - self-contained application

---

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation | Status |
|------|--------|-------------|------------|--------|
| Twilio API outage | High | Low | Retry logic, notification logs, admin alerts | ✅ Mitigated |
| Schedule algorithm bug | High | Medium | 100% test coverage, manual override capability | ✅ Mitigated |
| SMS delivery failures | Medium | Medium | 3x retry with exponential backoff | ✅ Mitigated |
| Database corruption | High | Low | WAL journal mode, Docker named volumes, backup strategy | ✅ Mitigated |
| Timezone handling errors | Medium | Medium | America/Chicago via pytz, extensive testing | ✅ Mitigated |
| Team member churn | Low | High | Simple UI for add/remove, auto rotation reordering | ✅ Mitigated |
| Twilio 10DLC approval delay | Medium | Medium | Working integration ready, awaiting approval | 🔄 Monitoring |

---

## Timeline and Phases

### Phase 1: MVP Development ✅ COMPLETE
**Duration:** November 4-9, 2025 (5 days - ahead of 6-week estimate!)
- ✅ Core backend (database, models, API)
- ✅ Scheduler and SMS integration
- ✅ Admin frontend interface (8 pages)
- ✅ Testing (288 tests, 85% coverage)
- ✅ Docker deployment
- ✅ Authentication system (Argon2id)

**Deliverables:**
- v1.0.0 Production Release (November 9, 2025)
- Complete documentation
- Docker containerization
- Linear integration established

### Phase 2: Deployment & Authentication 🔄 IN PROGRESS
**Duration:** November 10-30, 2025 (3 weeks estimated)
- 📋 Offline installer for air-gapped deployment
- 📋 RHEL 10 production validation
- 📋 HTTPS support via nginx
- 📋 Twilio 10DLC approval completion
- 📋 REQ-051: Weekly escalation contact schedule summary (WHO-23)
- 📋 REQ-052: Calendar card phone display enhancement (WHO-24)
- 📋 1-week production trial

**Deliverables:**
- v1.1.0 Production-Ready Deployment
- Offline installer bundle
- Production deployment guide
- Performance validation report
- Enhanced supervisor workflow tools

### Phase 3: Enhancements 📋 PLANNED
**Duration:** December 2025 - January 2026 (6-8 weeks estimated)
- REQ-037: Manual shift override UI (WHO-14)
- REQ-038: Multi-level SMS notifications (WHO-15)
- REQ-039: Auto-regeneration on config changes (WHO-16)
- REQ-050: Global color consistency system (WHO-22)
- REQ-031: Email notification backup
- REQ-035: PTO/vacation management

**Deliverables:**
- v1.2.0 Enhanced Features Release
- Advanced admin capabilities
- Multi-channel notifications

### Phase 4: Scale & Integrations 🔮 VISION
**Duration:** Q1 2026+ (12+ weeks estimated)
- REQ-040: Multi-team support
- REQ-041: PostgreSQL migration
- REQ-042/043: Teams/Slack integration
- REQ-045: Mobile application
- REQ-048: Advanced analytics

**Deliverables:**
- v2.0.0 Enterprise Release
- Multi-tenant architecture
- Mobile apps (iOS/Android)
- External integrations

---

## New Requirement Template

Use this template when adding new requirements:

```markdown
**REQ-XXX: [Feature Name] (WHO-XX)**
**Status:** 📋 Planned / 🔄 In Progress / ✅ Complete (vX.X.X)
**Phase:** X - [Phase Name]
**Priority:** High / Medium / Low
**Linear:** [WHO-XX](https://linear.app/hextrackr/issue/WHO-XX)

[Brief description of the requirement]

**Acceptance Criteria:**
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

**Implementation Notes:**
[Technical approach or constraints]

**Dependencies:**
[Other REQ-XXX that must be completed first]

**Testing:**
[Key test scenarios]
```

---

## Approval and Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Product Owner | Lonnie B. | ✅ | 2025-11-09 |
| Tech Lead | Claude Code | ✅ | 2025-11-09 |
| Stakeholder | Development Team | ✅ | 2025-11-09 |

---

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-04 | Development Team | Initial PRD creation |
| 2.0 | 2025-11-10 | Development Team | Converted to living document format with status tracking, Linear integration, and Phase 1 completion markers |

---

## Appendix

### Glossary
- **On-Call:** State of being available to respond to incidents during designated time period
- **Shift:** Defined time period for on-call coverage
- **Rotation:** Pattern of shift assignments across team members
- **Fair Distribution:** Algorithm ensuring equitable assignment of shifts, especially weekends
- **Circular Rotation:** Continuous cycling through all shifts where `member_index = shifts_elapsed % team_size`
- **Escalation Chain:** Backup contacts (Primary/Secondary/Tertiary) calculated from rotation_order

### References
- [Twilio SMS API Documentation](https://www.twilio.com/docs/sms)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [WhoseOnFirst GitHub Repository](https://github.com/Lonnie-Bruton/WhoseOnFirst)
- [WhoseOnFirst Linear Board](https://linear.app/hextrackr/team/WhoseOnFirst)
- [CLAUDE.md](/CLAUDE.md) - AI Context File
- [Documentation Guide](/docs/DOCUMENTATION_GUIDE.md) - Documentation System

---

**Last Reviewed:** November 10, 2025  
**Next Review:** December 2025 (Quarterly)
