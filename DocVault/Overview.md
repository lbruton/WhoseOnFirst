---
tags: []
doc_type: overview
project: whoseonfirst
source: manual
aliases: ["WhoseOnFirst Overview", "WhoseOnFirst"]
created: "2026-03-11"
updated: "2026-06-09"
---

# WhoseOnFirst

> **Public copy.** Deployment and infra details (hosts, IPs, ports) are in the private companion: `Devops/DocVault/Projects/WhoseOnFirst/Overview.md` (`vault-path private`).

Automated on-call rotation and SMS notification system. Manages team schedules, shift assignments, and real-time notifications via Twilio for coordinating who is on-call at any given time.

## At a Glance

| Field | Value |
|-------|-------|
| Repo | [lbruton/WhoseOnFirst](https://github.com/lbruton/WhoseOnFirst) |
| Language | Python 3.12 (FastAPI backend), vanilla JavaScript frontend (Tabler.io) |
| Branch | `dev` (default + PR target). `main` is production — auto-deploys via Portainer GitOps; both branches require PRs (direct push blocked) |
| Version Lock | None (planned — WOF-5) |
| Issues | [Plane](https://plane.lbruton.cc/lbruton/), prefix `WOF` |
| Path | `/Volumes/DATA/GitHub/WhoseOnFirst/` |

## Status

Phase 1 MVP complete: 100% backend, 100% frontend, 538 tests at 81% coverage. PWA, dark mode, and service worker shipped (WHO-37 epic, Mar 2026). Mobile/tablet UI redesign shipped (WHO-39, Mar 2026): responsive stat cards (col-6), card-view toggles with localStorage, 44px touch targets, dark mode audit across all 10 pages, login branding (green gradient + icon-bare.svg), first-boot admin seeding in lifespan hook.

**June 2026 behavior changes (on `dev`, ships with next release):**

- **Schedule generation anchors at the chosen start date** (WOF-9, PR #48). Previously any start date snapped to Monday of that week — member 1 always landed on Monday, mid-week starts silently created past-day entries and bumped member 1 off the chosen day. Now member 1 (lowest `rotation_order`) goes on call on the exact start date, no entries are created before it, multi-day shifts straddling the start are skipped whole (never truncated), and a mid-week start adds one trailing week so coverage ≥ requested weeks. `POST /schedules/generate` returns a `{schedules, warnings}` envelope — warns when start = today after the 8 AM job (no SMS that day) and when the start day is uncovered by a skipped 48h shift.
- **Monday weekly digest recipients are now per-person opt-in** (WOF-10, PR #50). Recipients = active team members with the new `weekly_digest_optin` flag (toggle on the member profile) ∪ escalation contacts whose per-contact digest flags are on (default ON, preserving prior behavior), deduped by phone. Escalation-contact status and digest receipt are fully independent — a supervisor outside the escalation pair can opt in; an escalation contact can opt out.
- **Dependabot now targets `dev`** (PR #49) — security updates may still open PRs against `main`; close and re-land via dev.

**Next phases**: pre-ship security fixes (WOF-15, WOF-17/18/19), version bump absorbing WOF-14, `dev → main` release; then Twilio Admin-UI/DB hardening backlog, PostgreSQL migration.

## How It's Deployed

Runs as a Docker container on the [Portainer](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Portainer.md) VM, behind [NPM](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/NPM.md) reverse proxy via [Cloudflare](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Cloudflare.md) tunnel.

| Component | Detail |
|-----------|--------|
| Stack | [Stack Registry](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Stack%20Registry.md) ID 12, repo-based from `main` branch |
| Port | 8900 (host) -> 8000 (container) |
| Database | SQLite on [named volume](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Named%20Volumes.md) `whoseonfirst_whoseonfirst-data` (228K) |
| Health check | `GET /health` (30s interval) |
| Backups | [Backups](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Backups.md) stack pulls SQLite via `sqlite3 .backup` |

## Architecture

**Pattern**: FastAPI with SQLAlchemy ORM, Alembic migrations

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.115.0 + Uvicorn |
| Database | SQLAlchemy 2.0.31 + Alembic (SQLite Phase 1, PostgreSQL Phase 2+) |
| Scheduling | APScheduler 3.10.4 |
| Admin Seeding | First-boot: seeds `admin/Admin123!` via lifespan hook when `user_count == 0` (idempotent) |
| SMS | Twilio SDK 9.2.3 |
| Auth | Argon2-cffi (OWASP 2025 recommended) |
| Validation | Pydantic 2.8.2 |
| Frontend | Tabler.io 1.0.0-beta20 (Bootstrap 5), vanilla JS, 8 HTML pages |
| Testing | pytest (288 tests), black, flake8, mypy, pylint |

### Corporate Deployment (Planned)

In addition to the home Portainer deployment, WhoseOnFirst will be deployed at the corporate office:

| Component | Detail |
|-----------|--------|
| Source sync | Personal GitHub → Corporate GitLab (manual sync at office) |
| GitOps | Ernie (server admin) deploys from GitLab → corporate Kubernetes |
| Secrets | Production Twilio API keys configured in K8s environment (not in repo) |
| Dev safety | Development uses dummy Twilio keys / dummy phone numbers — no live keys in dev |

**Flow**: Develop locally with dummy keys → push to GitHub → sync to corporate GitLab at office → GitOps deploy to K8s with production secrets.

This eliminates the duplicate SMS risk entirely — dev environments never have live Twilio credentials.

### Development Workflow

Uses RPI (Research -> Plan -> Implement) — a lightweight 3-phase process, not the full spec-workflow. Templates and process documented in the repo at `.context/rpi-process.md`.

## Architecture Decisions

- **FastAPI over Express** — Python ecosystem has better scheduling (APScheduler) and SMS (Twilio) libraries
- **SQLite Phase 1, PostgreSQL Phase 2** — start simple, migrate when multi-instance needed
- **Tabler.io frontend** — Bootstrap 5 based, 16-color WCAG AA team member system, no build step
- **Cloudflare Tunnel access** — Zero Trust authentication instead of exposing port directly
- **RPI over spec-workflow** — lighter-weight process for a smaller, single-developer project

## Documentation

Foundation docs (architecture, tech stack, code patterns, auth, RPI workflow) are tracked **in-repo** under `.context/` so they travel with the code to any GitLab mirror — start at `.context/README.md`. Product and research material lives here in DocVault.

| Doc | Notes |
|-----|-------|
| [[PRD]] | Product Requirements Document |
| [[Research/research-notes]] | Framework / library selection research (Nov 2025) |
| [[Research/memento-taxonomy]] | Memento knowledge-graph taxonomy |
| [[Sprints/WHO-14-manual-shift-override-ui]] · [[Sprints/WHO-22-color-consistency]] · [[Sprints/WHO-23-weekly-escalation-summary]] | Archived sprint logs |

## Related

- [Plane issues](https://plane.lbruton.cc/lbruton/) — active and closed `WOF` issues
- [Portainer](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Portainer.md) — Docker host for the container
- [Stack Registry](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Stack%20Registry.md) — Stack ID 12
- [Named Volumes](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Named%20Volumes.md) — Database volume
- [Backups](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Backups.md) — Automated SQLite backup target
- [Cloudflare](/Volumes/DATA/GitHub/Devops/DocVault/KnowledgeBase/Infrastructure/Cloudflare.md) — Tunnel and Zero Trust access
