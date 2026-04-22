# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> See `~/.claude/CLAUDE.md` for global workflow rules (push safety, version checkout gate, PR lifecycle, MCP tools, code search tiers, UI design workflow, plugins).

## Branch & Push Policy (overrides global)

**Default branch is `dev`** — both locally and as the PR target. `main` is the production branch and is only updated via a deliberate `dev → main` PR during a scheduled maintenance window (see WHO-49). The Portainer GitOps stack auto-deploys from `main`, so any push to `main` fires real SMS at real coworkers on the next scheduler tick.

- **All work happens on `dev`** (or worktrees branched off `dev`).
- **Both `main` and `dev` require PRs** — direct push is blocked by GitHub repository rules on both branches. Always work in a worktree off `dev` and open a PR targeting `dev`.
- **`dev → main` PRs** are only opened when shipping to production. Open or merge a `dev → main` PR only when the user explicitly says "ship" or "release".
- **Always use worktrees for changes to `main` or `dev`.** Both are protected by branch protection rules; direct pushes are rejected. Additionally, any direct push to `main` would deploy to production immediately.
- No version lock, no Codacy gate on PRs.

**Before any code change:** verify you are on `dev` (or a worktree off `dev`), not `main`. If you find yourself on `main`, stop and switch.

## DEV DB — DO NOT RESTORE FROM PROD

The dev environment uses **sanitized data only**. Production databases contain real names and phone numbers.

- **NEVER** copy from `~/Nextcloud/Backups/whoseonfirst/` or production `.stvault` files into the dev environment.
- **Correct procedure:** rebuild from `~/whoseonfirst-dev-data/backups/dev-seed-sanitized.stvault` or let first-boot auto-seed handle it.
- `docker-compose.dev.yml` enforces safety rails: `SMS_MOCK_MODE=true`, no shared `.env` with production.
- **Why this guardrail exists:** an AI agent once restored the production database over the dev environment, exposing real PII to a local container with mock security. This must not recur.

## Quick Start

**Project:** WhoseOnFirst - Automated on-call rotation and SMS notification system for 7-person technical team

- Backend: FastAPI / APScheduler / Twilio
- Frontend: 8 pages with live data (Tabler.io / Bootstrap 5)
- Testing: 467+ tests
- Deployment: Docker containerized (Portainer GitOps on production)

**Work From:**

- **Issues:** DocVault vault, prefix `WHO` (see `issue` skill)
- **Requirements:** `/docs/planning/PRD.md` (living document)
- **Code Patterns:** `/docs/reference/code-patterns.md`

---

## DocVault — Project Documentation

Technical documentation lives in **DocVault** at `/Volumes/DATA/GitHub/DocVault/Projects/WhoseOnFirst/`. Read relevant pages before discussing architecture or planning changes.

Key pages: Start at `/Volumes/DATA/GitHub/DocVault/Projects/WhoseOnFirst/_Index.md` and follow the index.

```
Read /Volumes/DATA/GitHub/DocVault/Projects/WhoseOnFirst/Overview.md
```

When making changes that affect documented behavior, run `/vault-update` before pushing.

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

**Database:** SQLite (`./data/whoseonfirst.db`)

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

### Dev Database — ALWAYS Use Sanitized Seed

**Production data lives in the Portainer container only.** Use sanitized seed data for local Mac dev builds.

The sanitized seed DB lives at:
```
~/whoseonfirst-dev-data/backups/dev-seed-sanitized.stvault
```

**At the start of each local dev session**, if `~/whoseonfirst-dev-data/whoseonfirst.db` is missing or empty, load the sanitized seed:

```bash
cp ~/whoseonfirst-dev-data/backups/dev-seed-sanitized.stvault \
   ~/whoseonfirst-dev-data/whoseonfirst.db
docker restart whoseonfirst-dev
```

**Restore only from the sanitized seed backup** into the local dev container. Real production backups (`~/Nextcloud/Backups/whoseonfirst/`) contain real names and phone numbers and belong in Nextcloud only — keep them out of the dev environment entirely.

### Testing (Local Environment)

```bash
source venv/bin/activate
pytest --cov=src --cov-report=html
```

---

## Production Debugging

Production runs on Portainer VM `192.168.1.81` (stack #12) behind Cloudflare Zero Trust Access. Use `docker --context portainer <cmd>` for remote docker ops — no SSH needed.

- **Filter healthcheck noise from logs** (~99% of output): `docker --context portainer logs whoseonfirst --since 24h 2>&1 | grep -v "GET /health"`
- **"Can't log in" + container healthy + zero POSTs in filtered logs** = Cloudflare Zero Trust session expired. Requests never reach FastAPI. Fix is user-side CF re-auth, not a code change.
- **Production admin password is not documented anywhere.** The `Admin123!` credential in auto-memory applies only to local dev container recovery — use it only for local dev, not against production.

---

## Critical Implementation Details

### Database Schema

**Core Tables:** `team_members`, `shifts`, `schedule`, `notification_log`, `settings`

**Important Indexes:** `schedule(start_datetime)`, `schedule(notified, start_datetime)`, `team_members(is_active)`

### API Endpoint Structure

All APIs under `/api/v1/` prefix:

- `/team-members/` - CRUD, `/reorder` (drag-drop), `/{id}/permanent` (hard delete)
- `/shifts/` - Shift configuration management
- `/schedules/` - Generation, queries, notifications
- `/settings/` - Auto-renewal configuration

### Security Requirements

- All credentials in `.env` file (never commit)
- Pydantic validates all inputs (phone: `^\+1\d{10}$`)
- Use SQLAlchemy ORM exclusively; do not write raw SQL
- Mask phone numbers in logs (last 4 digits)

---

## Testing Requirements

**Baseline:** 467+ tests. Rotation algorithm: 100%, Critical paths: 100%
**Target:** Maintain 80%+ coverage

---

## Important Constraints

1. **Timezone:** Always use America/Chicago (CST/CDT) via `pytz`
2. **Phone Format:** E.164 only (+1XXXXXXXXXX)
3. **Shift Config:** Default 6 shifts, Shift 2 is 48h double (Tue-Wed)
4. **Schedule Gen:** Minimum 4 weeks advance
5. **Transactions:** Explicit transactions with rollback on errors

---

## Common Pitfalls (Best Practices)

- Use APScheduler (project standard) instead of system cron
- Use `timezone('America/Chicago')` (CST/CDT) instead of hardcoding timezones
- Regenerate schedule from change date forward only, not the entire schedule
- Use sanitized seed data only when restoring to dev; never restore real production DB (see Dev Database section above)

---

## RPI Workflow (Research → Plan → Implement)

WhoseOnFirst uses **RPI** — a lightweight 3-phase process (Research → Plan → Implement). This is a project-specific override to the global spec-workflow. Full process: `/docs/RPI_PROCESS.md`

---

## Issue Tracking

Issues tracked in DocVault vault. Prefix: `WHO` (see `issue` skill).

---

## Hooks

- **gitleaks**: Pre-commit hook scans for accidental secret commits (`github-pat`, `aws`, `stripe`, etc.). Runs via `pre-commit` framework. Installed 2026-04-14 (OPS-116).

## Code Search

> See global `~/.claude/CLAUDE.md` for the full code search tier order (HARD GATE).

**Project search path**: `/Volumes/DATA/GitHub/WhoseOnFirst`
