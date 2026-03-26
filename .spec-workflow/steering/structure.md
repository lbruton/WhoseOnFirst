# Project Structure

## Directory Organization

```
WhoseOnFirst/
├── src/                          # Python backend application
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory, middleware, scheduler startup
│   ├── api/                      # API layer
│   │   ├── __init__.py
│   │   ├── dependencies.py       # FastAPI dependency injection (get_db, etc.)
│   │   ├── routes/               # Route handlers — one file per resource
│   │   │   ├── admin.py          # Admin dashboard data endpoints
│   │   │   ├── auth.py           # Login/logout, session management, role decorators
│   │   │   ├── notifications.py  # SMS notification history and stats
│   │   │   ├── schedule_overrides.py  # Manual shift override CRUD
│   │   │   ├── schedules.py      # Schedule generation and queries
│   │   │   ├── settings.py       # Auto-renewal and system settings
│   │   │   ├── shifts.py         # Shift configuration CRUD
│   │   │   ├── team_members.py   # Team member CRUD, reorder, permanent delete
│   │   │   └── version.py        # Version endpoint
│   │   └── schemas/              # Pydantic request/response models — one file per resource
│   │       ├── auth_schemas.py
│   │       ├── notification.py
│   │       ├── schedule_override.py
│   │       ├── schedule.py
│   │       ├── settings.py
│   │       ├── shift.py
│   │       └── team_member.py
│   ├── auth/                     # Authentication utilities
│   │   └── utils.py              # hash_password(), verify_password() — Argon2id
│   ├── models/                   # SQLAlchemy ORM models — one file per table
│   │   ├── database.py           # Engine, SessionLocal, Base declarative
│   │   ├── notification_log.py
│   │   ├── schedule_override.py
│   │   ├── schedule.py
│   │   ├── settings.py
│   │   ├── shift.py
│   │   ├── team_member.py
│   │   └── user.py
│   ├── repositories/             # Data access layer — one file per model
│   │   ├── base_repository.py    # Generic CRUD (get_by_id, get_all, create, update, delete)
│   │   ├── notification_log_repository.py
│   │   ├── schedule_override_repository.py
│   │   ├── schedule_repository.py
│   │   ├── settings_repository.py
│   │   ├── shift_repository.py
│   │   ├── team_member_repository.py
│   │   └── user_repository.py
│   ├── services/                 # Business logic layer — one file per domain
│   │   ├── export_service.py     # Data export (JSON/CSV)
│   │   ├── import_service.py     # Data import
│   │   ├── rotation_algorithm.py # Core circular rotation logic (100% test coverage)
│   │   ├── schedule_override_service.py
│   │   ├── schedule_service.py   # Schedule generation, queries
│   │   ├── settings_service.py
│   │   ├── shift_service.py
│   │   ├── sms_service.py        # Twilio SMS sending, retry logic
│   │   └── team_member_service.py
│   ├── scheduler/                # Background job management
│   │   └── schedule_manager.py   # APScheduler setup, daily SMS job, auto-renewal job
│   └── utils/                    # Shared utility functions
│       └── __init__.py
├── frontend/                     # Static HTML/JS/CSS frontend
│   ├── index.html                # Dashboard — calendar, escalation chain, stats
│   ├── admin.html                # Admin overview page
│   ├── team-members.html         # Team member CRUD with drag-drop reorder
│   ├── shifts.html               # Shift configuration page
│   ├── schedule.html             # Schedule generation (1-104 weeks)
│   ├── schedule-overrides.html   # Manual shift override management
│   ├── notifications.html        # SMS delivery history and stats
│   ├── help.html                 # Help and setup guide
│   ├── login.html                # Login page
│   ├── change-password.html      # Password change page
│   ├── styleguide.html           # Color palette reference
│   ├── components/
│   │   └── sidebar.html          # Shared sidebar navigation (loaded via fetch)
│   ├── js/
│   │   ├── auth-init.js          # Auth check on page load, redirect to login
│   │   ├── pwa.js                # Service worker registration
│   │   ├── sidebar-loader.js     # Sidebar component loader
│   │   ├── team-colors.js        # 16-color WCAG AA palette utilities
│   │   └── theme.js              # Dark/light mode with localStorage persistence
│   └── sw.js                     # Service worker for PWA offline support
├── alembic/                      # Database migrations
│   ├── env.py                    # Migration environment config
│   └── versions/                 # Numbered migration files
├── tests/                        # Test suite — mirrors src/ structure
│   ├── conftest.py               # Root fixtures (in-memory SQLite, test data factories)
│   ├── api/
│   │   ├── conftest.py           # API-specific fixtures (FastAPI TestClient)
│   │   ├── test_schedules.py
│   │   ├── test_settings.py
│   │   ├── test_shifts.py
│   │   ├── test_team_members.py
│   │   └── test_version.py
│   ├── auth/
│   │   └── test_auth_utils.py
│   ├── models/
│   │   └── test_schedule_model.py
│   ├── repositories/
│   │   ├── test_notification_log_repository.py
│   │   ├── test_schedule_repository.py
│   │   ├── test_shift_repository.py
│   │   ├── test_team_member_repository.py
│   │   └── test_user_repository.py
│   ├── scheduler/
│   │   └── test_schedule_manager.py
│   └── services/
│       ├── test_export_service.py
│       ├── test_rotation_algorithm.py  # 30 tests, 100% coverage
│       ├── test_schedule_override_service.py
│       ├── test_schedule_service.py
│       ├── test_settings_service.py
│       ├── test_shift_service.py
│       ├── test_sms_service.py
│       └── test_team_member_service.py
├── scripts/                      # Utility scripts
│   ├── bump_version.py           # Version bump automation
│   ├── docker-entrypoint.sh      # Container startup (permission checks, migrations, uvicorn)
│   └── seed_users.py             # Default admin/viewer user creation
├── docs/                         # Project documentation
│   ├── planning/
│   │   ├── PRD.md                # Product Requirements Document (living)
│   │   └── architecture.md       # Architecture documentation
│   ├── reference/
│   │   └── code-patterns.md      # Code pattern reference
│   ├── DOCUMENTATION_GUIDE.md
│   └── RPI_PROCESS.md            # Research-Plan-Implement workflow
├── data/                         # SQLite database directory (gitignored)
├── backups/                      # Database backup files (gitignored)
├── deployment-packages/          # Offline installer bundles (gitignored)
├── docker-compose.yml            # Production compose (Portainer GitOps)
├── docker-compose.dev.yml        # Development compose (local Docker)
├── Dockerfile                    # Multi-stage UBI9 production image
├── requirements.txt              # Production Python dependencies
├── requirements-dev.txt          # Development dependencies (includes production)
├── alembic.ini                   # Alembic migration config
├── VERSION                       # Semantic version file
├── CLAUDE.md                     # AI development context
└── CHANGELOG.md                  # Version history
```

## Naming Conventions

### Files
- **Python modules**: `snake_case.py` — always (e.g., `team_member.py`, `sms_service.py`, `base_repository.py`)
- **HTML pages**: `kebab-case.html` (e.g., `team-members.html`, `schedule-overrides.html`)
- **JavaScript**: `kebab-case.js` (e.g., `auth-init.js`, `sidebar-loader.js`, `team-colors.js`)
- **Tests**: `test_[module_name].py` — pytest discovery convention (e.g., `test_rotation_algorithm.py`)
- **Alembic migrations**: Auto-generated hash prefix with description (e.g., `92999f654850_initial_database_schema.py`)

### Code (Python)
- **Classes**: `PascalCase` (e.g., `TeamMemberRepository`, `RotationAlgorithmError`, `TeamMemberCreate`)
- **Functions/Methods**: `snake_case` (e.g., `get_active()`, `list_team_members()`, `hash_password()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `STORAGE_KEY`, `ModelType`)
- **Variables**: `snake_case` (e.g., `active_only`, `item_id`, `team_size`)
- **Type variables**: `PascalCase` (e.g., `ModelType = TypeVar("ModelType")`)

### Code (JavaScript)
- **Functions**: `camelCase` (e.g., `_getTheme()`, `_saveTheme()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `STORAGE_KEY`)
- **Variables**: `camelCase` (e.g., `prefersDark`, `savedTheme`)
- **Global APIs**: `__wofPrefix` namespace (e.g., `window.__wofTheme`)
- **LocalStorage keys**: `wof_` prefix with snake_case (e.g., `wof_theme`)

### API Endpoints
- **URL pattern**: `/api/v1/{resource}/` — plural, kebab-case
- **Examples**: `/api/v1/team-members/`, `/api/v1/shifts/`, `/api/v1/schedules/`
- **Actions**: `/api/v1/team-members/reorder`, `/api/v1/team-members/{id}/permanent`

### Database
- **Table names**: `snake_case`, plural (e.g., `team_members`, `notification_log`, `schedule_overrides`)
- **Column names**: `snake_case` (e.g., `rotation_order`, `is_active`, `start_datetime`)
- **Foreign keys**: `{table_singular}_id` (e.g., `team_member_id`, `shift_id`)

## Import Patterns

### Import Order (Python)
1. Standard library (e.g., `datetime`, `typing`, `os`)
2. Third-party packages (e.g., `fastapi`, `sqlalchemy`, `pytz`)
3. Internal absolute imports from `src.` (e.g., `from src.models.database import Base`)

No relative imports used — all imports are absolute from the `src` package root.

### Import Style
```python
# Standard library
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Third-party
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Internal — always absolute from src
from src.api.dependencies import get_db
from src.api.schemas.team_member import TeamMemberCreate, TeamMemberResponse
from src.services import TeamMemberService, DuplicatePhoneError
from src.api.routes.auth import require_auth, require_admin
```

### Package `__init__.py` Exports
Each package's `__init__.py` re-exports key classes for cleaner imports:
- `from src.services import TeamMemberService` (not `from src.services.team_member_service import TeamMemberService`)
- `from src.repositories import TeamMemberRepository` (not the full path)
- `from src.models import TeamMember, Shift, Schedule` (not individual model files)

## Code Structure Patterns

### Route Handler Pattern
```python
@router.get("/", response_model=List[ResponseSchema])
def list_items(
    filter_param: bool = Query(False, description="..."),
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)    # or require_admin
):
    """Docstring with Args/Returns/Example."""
    service = ItemService(db)
    return service.get_all(filter_param)
```

Routes are thin — they parse HTTP input, call the service, and return. No business logic in routes.

### Service Pattern
```python
class ItemService:
    def __init__(self, db: Session):
        self.repo = ItemRepository(db)

    def get_all(self, filter_param: bool) -> List[Item]:
        if filter_param:
            return self.repo.get_active()
        return self.repo.get_all()
```

Services instantiate their own repositories. Business logic (validation, algorithm, orchestration) lives here.

### Repository Pattern
```python
class ItemRepository(BaseRepository[Item]):
    def __init__(self, db: Session):
        super().__init__(db, Item)

    def get_active(self) -> List[Item]:
        return self.db.query(self.model).filter(
            self.model.is_active == True
        ).all()
```

All repositories extend `BaseRepository[ModelType]` which provides `get_by_id`, `get_all`, `create`, `update`, `delete`, `count`, `exists`. Domain-specific queries go in the concrete repository.

### Test Pattern
```python
class TestItemService:
    def test_get_all_returns_items(self, test_db_session, sample_items):
        service = ItemService(test_db_session)
        result = service.get_all()
        assert len(result) == len(sample_items)
```

Tests use function-scoped in-memory SQLite via pytest fixtures. No mocks for database — real SQLAlchemy sessions against `:memory:`. HTTP mocks used only for Twilio (responses library).

### Frontend Page Pattern
Each HTML page is self-contained:
1. Tabler.io layout with shared sidebar (loaded via `sidebar-loader.js`)
2. Inline `<script>` block at page bottom with page-specific logic
3. API calls via `fetch()` to `/api/v1/` endpoints
4. DOM manipulation with vanilla JS (`document.getElementById`, `innerHTML`)
5. No global state management — each page fetches fresh data on load

## Module Boundaries

### Dependency Direction (strict)
```
Routes → Services → Repositories → Models
  ↓         ↓
Schemas   Auth Utils
```

- **Routes** may import: schemas, services, auth decorators, dependencies
- **Services** may import: repositories, models, other services (for orchestration)
- **Repositories** may import: models only
- **Models** import nothing from `src` — they are leaf nodes
- **Schemas** import nothing from `src` — they are leaf nodes (Pydantic models)

### Forbidden Dependencies
- Repositories MUST NOT import services (no upward dependency)
- Models MUST NOT import anything from `src` (pure SQLAlchemy declarations)
- Frontend JS MUST NOT call repositories or services directly — only via `/api/v1/` HTTP endpoints
- Scheduler calls services directly (bypasses routes) — this is intentional and correct

### Module Responsibilities
| Layer | Responsible For | NOT Responsible For |
|-------|----------------|---------------------|
| Routes | HTTP parsing, auth checks, response formatting | Business logic, direct DB queries |
| Schemas | Input validation, response shape | Database interaction, business rules |
| Services | Business logic, orchestration, algorithm | HTTP concerns, direct SQL |
| Repositories | Database queries via ORM | Business logic, HTTP concerns |
| Models | Table definitions, relationships | Queries, validation, business rules |
| Scheduler | Job timing, triggers | Business logic (delegates to services) |

## Code Size Guidelines

- **File size**: Target under 300 lines. Current largest files are route handlers (~200 lines) and services (~250 lines). If a service exceeds 300 lines, consider splitting by sub-domain.
- **Function size**: Target under 50 lines. Long functions should be decomposed into private helpers within the same class.
- **Class complexity**: One class per file for models, repositories, and services. Route files contain a `router` with multiple endpoint functions (not a class).
- **Nesting depth**: Maximum 3 levels (function > if/for > if/for). Deeper nesting signals a need to extract a helper.

## Documentation Standards

### Python Docstrings
All public classes and functions have Google-style docstrings:
```python
def method_name(self, param: str) -> ReturnType:
    """
    Brief description of what this does.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Raises:
        ExceptionType: When this error occurs
    """
```

### Module-Level Docstrings
Every `.py` file starts with a module docstring explaining the file's purpose:
```python
"""
Rotation Algorithm Service

This module implements the circular rotation algorithm...
"""
```

### Frontend Comments
Page-specific JS uses section comments for organization. Shared JS files (`theme.js`, `team-colors.js`) use JSDoc-style comments for exported APIs.
