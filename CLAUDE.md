# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> See `~/.claude/CLAUDE.md` for global workflow rules (push safety, version checkout gate, PR lifecycle, MCP tools, code search tiers, UI design workflow, plugins).

## Push Policy (overrides global)

Direct push to `main` is allowed for small fixes (CSS, copy, config tweaks). PRs are optional — use them for features or anything that warrants a review trail. No version lock, no Codacy gate on pushes.

## Quick Start

**Project:** WhoseOnFirst - Automated on-call rotation and SMS notification system for 7-person technical team

**Current Status:** Phase 1 MVP + Auth Complete

- Backend: 100% (FastAPI/APScheduler/Twilio)
- Frontend: 100% (11 pages — dashboard, login, admin, team members, shifts, schedule, schedule overrides, notifications, help, change password, style guide)
- Auth: Shipped (Argon2 password hashing, login/logout, role-based access, first-boot admin seeding)
- Testing: 288 tests, 85% coverage
- Deployment: Docker on Portainer (production), Cloudflare tunnel + Zero Trust

**Next Phase:** Versioning process, Docker offline installer, PostgreSQL migration

**Work From:**

- **Issues:** DocVault vault, prefix `WHO` (see `issue` skill)
- **Requirements:** `/docs/planning/PRD.md` (living document)
- **Code Patterns:** `/docs/reference/code-patterns.md`

---

## DocVault — Project Documentation

Technical documentation lives in **DocVault** at `/Volumes/DATA/GitHub/DocVault/Projects/WhoseOnFirst/`. Read relevant pages before discussing architecture or planning changes.

Key pages: `Overview.md`, Issues directory.

```
Read /Volumes/DATA/GitHub/DocVault/Projects/WhoseOnFirst/Overview.md
```

When making changes that affect documented behavior, run `/vault-update` before pushing.

## Documentation Hierarchy

```text
DocVault (Primary Docs) + mem0 (Session Context)
  ↓ references
/docs/planning/PRD.md (Living Requirements)
  ↓ informs
CLAUDE.md (This File - AI Context)
  ↓ generates
CHANGELOG.md (Version History)
  ↓ summarizes
README.md (User-Facing)
```

**Full Documentation Guide:** `/docs/DOCUMENTATION_GUIDE.md`

---

## Project Architecture

### Core Principles

**Layered Architecture:**

```text
API Layer (FastAPI routes)
  ↓
Service Layer (Business logic)
  ↓
Repository Layer (Data access)
  ↓
Database (SQLite → PostgreSQL path)
```

**Background Jobs:**

- APScheduler with America/Chicago timezone
- Daily SMS at 8:00 AM CST
- Auto-renewal check at 2:00 AM CST

**Circular Rotation Algorithm:**

- Simple modulo-based rotation: `member_index = shifts_elapsed % team_size`
- Works with any team size (1 to 15+ members)
- 100% test coverage (30 tests in `tests/test_rotation_algorithm.py`)

**Full Architecture:** `/docs/planning/architecture.md`

---

## Technology Stack

**Backend:** FastAPI 0.115+, SQLAlchemy 2.0+, APScheduler 3.10+, Twilio SDK 9.2+, Uvicorn 0.30+

**Database:** Phase 1: SQLite (`./data/whoseonfirst.db`), Phase 2+: PostgreSQL migration path

**Frontend:** Tabler.io 1.0.0-beta20 (Bootstrap 5), Vanilla JavaScript, 16-color WCAG AA team member system

**Deployment:** Docker/Podman containers, RHEL 10 target (production)

---

## Development Workflow

### Docker-First Development (PRIMARY)

```bash
# Start dev container (port 8900)
docker-compose -f docker-compose.dev.yml up -d

# Rebuild after code changes (REQUIRED)
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d
```

### Testing (Local Environment)

```bash
source venv/bin/activate
pytest --cov=src --cov-report=html
```

---

## Critical Implementation Details

### Database Schema

**Core Tables:** `team_members`, `shifts`, `schedule`, `notification_log`, `settings`, `users`

**Important Indexes:** `schedule(start_datetime)`, `schedule(notified, start_datetime)`, `team_members(is_active)`

### API Endpoint Structure

All APIs under `/api/v1/` prefix:

- `/auth/` - Login, logout, token refresh, password change
- `/admin/` - User management (create, list, delete users, reset passwords)
- `/team-members/` - CRUD, `/reorder` (drag-drop), `/{id}/permanent` (hard delete)
- `/shifts/` - Shift configuration management
- `/schedules/` - Generation, queries, notifications
- `/schedule-overrides/` - Manual schedule swap/override management
- `/notifications/` - Notification history and configuration
- `/settings/` - Auto-renewal configuration

Also: `/api` (info), `/health` (health check), `/api/v1/version` (build version)

### Security Requirements

- Service credentials (Twilio, SECRET_KEY) in `.env` / Portainer stack env vars (never commit)
- **First-boot admin seeding:** `src/main.py` lifespan hook creates `admin/Admin123!` when `users` table is empty (idempotent). This is a code-resident credential — change it after first login.
- Auth uses Argon2-cffi (OWASP 2025 recommended) for password hashing
- Pydantic validates all inputs (phone: `^\+1\d{10}$`)
- SQLAlchemy ORM exclusively (no raw SQL)
- Mask phone numbers in logs (last 4 digits)

---

## Testing Requirements

**Current Coverage:** 85% (288 tests), Rotation algorithm: 100%, Critical paths: 100%
**Target:** Maintain 80%+ coverage

---

## Common Patterns

### Repository Pattern

```python
class TeamMemberRepository(BaseRepository[TeamMember]):
    def get_active(self) -> List[TeamMember]:
        return self.db.query(self.model).filter(
            self.model.is_active == True
        ).all()
```

---

## Important Constraints

1. **Timezone:** Always use America/Chicago (CST/CDT) via `pytz`
2. **Phone Format:** E.164 only (+1XXXXXXXXXX)
3. **Shift Config:** Default 6 shifts, Shift 2 is 48h double (Tue-Wed)
4. **Schedule Gen:** Minimum 4 weeks advance
5. **Transactions:** Explicit transactions with rollback on errors

---

## Common Pitfalls (Avoid These)

- Using system cron → Use APScheduler
- Hardcoding timezones → Use `timezone('America/Chicago')`
- Skipping phone validation → Validate E.164 format
- Missing indexes → Index frequently queried fields
- Regenerating entire schedule → Regenerate from change date forward
- Storing secrets in code → Use environment variables

---

## RPI Workflow (Research → Plan → Implement)

**WhoseOnFirst uses RPI** — a lightweight 3-phase process adapted from HexTrackr. This is a project-specific override to the global spec-workflow.

**Phase 1: RESEARCH** (30-90 min) — Document current state with file:line references
**Phase 2: PLAN** (30-60 min) — Break into 3-10 tasks, write before/after snippets
**Phase 3: IMPLEMENT** (1-3 hours) — Execute with Docker rebuild checkpoints

**Full Process:** `/docs/RPI_PROCESS.md`

---

## Issue Tracking

Issues tracked in DocVault vault. Prefix: `WHO` (see `issue` skill).

---

## Project Phases

**Phase 1: MVP** — COMPLETE
**Phase 2: Deployment & Auth** — COMPLETE (Portainer GitOps, Cloudflare tunnel, Argon2 auth, admin seeding, role-based access)
**Phase 3: Enhancements** — IN PLANNING (versioning, Docker offline installer, PostgreSQL migration)
**Phase 4: Advanced Features** — FUTURE

---

## When Creating New Code

1. Follow layered architecture (API → Service → Repository)
2. Use type hints everywhere (MyPy validation)
3. Write tests first (especially critical paths)
4. Handle timezones explicitly (America/Chicago)
5. Log important events with context
6. Validate all inputs (Pydantic models)
7. Use dependency injection (FastAPI `Depends()`)



## Code Search

> See global `~/.claude/CLAUDE.md` for the full code search tier order (HARD GATE).

**Project search path**: `/Volumes/DATA/GitHub/WhoseOnFirst`
