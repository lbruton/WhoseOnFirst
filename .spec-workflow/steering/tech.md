# Technology Stack

## Project Type

Web application — a FastAPI backend serving both an API and static HTML frontend, containerized in Docker, deployed via Portainer GitOps. Single-tenant, single-container architecture with SQLite for persistence and APScheduler for background jobs.

## Core Technologies

### Primary Language(s)
- **Language**: Python 3.12
- **Runtime**: CPython on Red Hat UBI9 (`registry.access.redhat.com/ubi9/python-312`)
- **Package Manager**: pip with pinned `requirements.txt`

### Key Dependencies/Libraries

**Backend:**
- **FastAPI 0.115.0**: Web framework — async routing, dependency injection, automatic OpenAPI docs
- **Uvicorn 0.30.1**: ASGI server with standard extras (websockets, httptools)
- **SQLAlchemy 2.0.31**: ORM — 2.0-style with type-annotated models, no raw SQL anywhere
- **Alembic 1.13.1**: Database migrations — version-controlled schema changes
- **APScheduler 3.10.4**: Background job scheduler — cron-like triggers with SQLAlchemy job store for persistence across restarts
- **Twilio SDK 9.2.3**: SMS delivery — `client.messages.create()` with SID tracking
- **Pydantic 2.8.2 + pydantic-settings 2.2.1**: Input validation and settings management from environment variables
- **Argon2-cffi 23.1.0**: Password hashing — Argon2id algorithm (OWASP 2025 recommended over bcrypt)
- **pytz 2024.1**: Timezone handling — all times in `America/Chicago` (CST/CDT)
- **python-dotenv 1.0.1**: `.env` file loading for local development
- **httpx 0.25.2**: Async HTTP client for external API calls
- **python-json-logger 2.0.7**: Structured JSON logging
- **python-multipart 0.0.22**: Form/file upload parsing for FastAPI

**Frontend:**
- **Tabler.io 1.0.0-beta20**: Bootstrap 5-based admin UI framework — loaded via CDN
- **Vanilla JavaScript**: No build step, no framework, no bundler
- **Tabler Icons**: Icon font included with Tabler.io

### Application Architecture

Layered architecture with strict separation:

```
API Layer (FastAPI routes in src/api/v1/)
  |
Service Layer (Business logic in src/services/)
  |
Repository Layer (Data access in src/repositories/)
  |
Database (SQLAlchemy ORM models in src/models/)
```

- **Routes** handle HTTP concerns (request parsing, response formatting, auth checks)
- **Services** contain business logic (rotation algorithm, schedule generation, notification sending)
- **Repositories** encapsulate all database queries via SQLAlchemy ORM
- **Models** define SQLAlchemy table mappings and Pydantic schemas

Background jobs (APScheduler) call services directly — they bypass the API layer.

### Data Storage
- **Primary storage**: SQLite via SQLAlchemy ORM (file: `/app/data/whoseonfirst.db`)
- **WAL journal mode**: Enabled for concurrent read/write without locking
- **Named Docker volume**: `whoseonfirst_whoseonfirst-data` persists across container redeploys
- **Migration path**: SQLAlchemy abstraction supports PostgreSQL swap with connection string change only
- **No caching layer**: Unnecessary at current scale (single-digit team, weekly schedule changes)

### External Integrations
- **Twilio SMS API**: REST API for message delivery. Credentials via environment variables (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`). Retry: 3 attempts with exponential backoff (0s, 60s, 120s).
- **No other external dependencies**: Self-contained application. No external auth providers, no third-party analytics, no CDN dependencies at runtime (Tabler assets are bundled).

### Monitoring and Dashboard Technologies
- **Dashboard Framework**: Vanilla JavaScript with Tabler.io (Bootstrap 5) — 8 HTML pages served as static files
- **Real-time Communication**: None — page refresh model (appropriate for weekly-changing data)
- **Visualization**: Native HTML/CSS calendar grid, color-coded team member avatars (16-color WCAG AA palette)
- **State Management**: Server-side (database) is source of truth. LocalStorage used only for SMS template editing (client preference, not data).

## Development Environment

### Build and Development Tools
- **Build System**: Docker multi-stage build (UBI9 builder + UBI9 runtime)
- **Package Management**: pip with `requirements.txt` (production) and `requirements-dev.txt` (development)
- **Development workflow**: `docker-compose -f docker-compose.dev.yml up -d --build` — no hot reload, rebuild required for backend changes. Frontend changes visible on page refresh (static file mount).

### Code Quality Tools
- **Static Analysis**: mypy 1.8.0 (type checking), pylint 3.0.3 (advanced linting), flake8 6.1.0 (style linting)
- **Formatting**: black 24.3.0 (code formatting), isort 5.13.2 (import sorting)
- **Testing Framework**: pytest 7.4.3 with pytest-asyncio 0.23.0, pytest-cov 4.1.0, pytest-mock 3.12.0
- **Test utilities**: freezegun 1.4.0 (datetime mocking), faker 21.0.0 (test data), responses 0.24.1 (HTTP mocking)
- **Pre-commit hooks**: pre-commit 3.6.0

### Version Control and Collaboration
- **VCS**: Git / GitHub (`lbruton/WhoseOnFirst`)
- **Branching Strategy**: `main` only — direct push OK for small fixes, PRs optional for features
- **Code Review Process**: Claude Code-assisted review, Codacy quality scans on push

## Deployment and Distribution

- **Home deployment**: Portainer GitOps on VM 192.168.1.81 (stack #12). Pulls from `main` branch. Port 8900 (host) mapped to 8000 (container). Cloudflare tunnel + Zero Trust for `whoseonfirst.lbruton.cc`.
- **Corporate deployment (planned)**: Air-gapped RHEL Kubernetes. Source synced from GitHub to corporate GitLab manually. Production Twilio keys injected via K8s environment — never in repo. Ernie (server admin) manages GitLab-to-K8s deployment.
- **Offline installer (planned)**: Pre-downloaded container images and vendored dependencies for air-gapped environments.
- **Update mechanism**: Push to `main` then "Pull and redeploy" in Portainer UI. Named volume preserves database.

## Technical Requirements and Constraints

### Performance Requirements
- SMS delivery within 60 seconds of scheduled time (8:00 AM CST)
- Web dashboard page load under 2 seconds
- API responses under 500ms (95th percentile)
- Support up to 20 team members without degradation

### Compatibility Requirements
- **Container base**: Red Hat UBI9 (RHEL-compatible, OpenShift-compatible with arbitrary UID support)
- **Python**: 3.12+ (type hints, async/await, modern stdlib)
- **Browser support**: Modern browsers (Chrome, Firefox, Safari, Edge). No IE11 support.
- **Mobile**: Responsive design via Bootstrap 5 breakpoints. PWA with service worker for offline dashboard viewing.

### Security and Compliance
- **Authentication**: Session-based with Argon2id password hashing, HTTPOnly cookies, SameSite=Strict
- **Authorization**: Two-tier roles (Admin: full CRUD, Viewer: read-only)
- **Input validation**: Pydantic models on all API endpoints. Phone numbers validated as E.164 (`^\+1\d{10}$`)
- **SQL injection prevention**: SQLAlchemy ORM exclusively — zero raw SQL queries
- **Credential storage**: Environment variables (Infisical for production, `.env` for local dev)
- **Phone privacy**: Phone numbers masked to last 4 digits in all log output

### Scalability and Reliability
- **Expected load**: Single team of 7-8 members, one admin. Tens of requests per day, not per second.
- **Availability target**: 99.9% during business hours (8 AM - 8 PM CST)
- **Scheduler resilience**: APScheduler SQLAlchemy job store survives container restarts. 5-minute misfire grace time.
- **Growth path**: PostgreSQL migration when multi-instance or multi-team needed. SQLAlchemy abstraction makes this a connection-string swap.

## Technical Decisions and Rationale

### Decision Log
1. **FastAPI over Express/Django**: Python ecosystem has superior scheduling (APScheduler) and SMS (Twilio) library support. FastAPI gives async + automatic OpenAPI without Django's overhead.
2. **SQLite for Phase 1, PostgreSQL for Phase 2+**: Single-container deployment doesn't need a separate database server. SQLAlchemy ORM abstraction means zero code changes for the migration — only the connection string changes.
3. **Vanilla JS over React/Vue**: 8 static pages with simple CRUD operations. No build step, no node_modules, no bundler config. The frontend complexity doesn't justify a framework.
4. **Tabler.io over raw Bootstrap**: Pre-built admin components (calendars, data tables, stat cards) accelerate development. Bootstrap 5 underneath means no lock-in.
5. **APScheduler over system cron**: Runs inside the container, persists job state in SQLAlchemy, supports timezone-aware triggers. System cron would require host-level access and lose state on container restart.
6. **Argon2id over bcrypt**: OWASP 2025 recommendation. Memory-hard, resistant to GPU/ASIC attacks. `argon2-cffi` is the reference Python implementation.
7. **Red Hat UBI9 over Alpine/Debian**: Corporate deployment targets RHEL. UBI9 is binary-compatible, free to redistribute, and includes security updates from Red Hat. OpenShift-compatible with arbitrary UID/GID 0 group support.
8. **Cloudflare Tunnel over exposed port**: Zero Trust authentication instead of port-forwarding. No firewall rules to manage, no SSL certificate renewal.

## Known Limitations

- **Single-container SQLite**: No concurrent write scaling. Acceptable for single-team use; PostgreSQL migration needed for multi-team.
- **No hot reload in development**: Backend changes require `docker-compose down && build && up`. Acceptable trade-off for production-identical dev environment.
- **SMS template in LocalStorage**: The editable SMS template is stored client-side. Backend API for template management is planned (REQ-034) but not yet implemented.
- **No WebSocket push**: Dashboard requires manual page refresh for new data. Appropriate for data that changes weekly, but may need WebSocket for future real-time features.
- **Twilio dependency**: SMS is the only notification channel. Email backup (REQ-031) and Teams/Slack integration (REQ-042/043) are planned for Phase 3-4.
