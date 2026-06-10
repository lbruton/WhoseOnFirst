# E2E Tests (Playwright)

Frontend regression specs. Not wired into CI — run locally before a release.

## Prerequisites

- Node 20+ and the Python venv (`venv/`) set up per the main README
- Chromium for Playwright: `npx playwright install chromium` (one-time)

## Setup and run

```bash
npm ci                          # installs @playwright/test (pinned)

# First run only: the app needs an existing data/ dir and migrated DB.
# The SQLite path is relative (data/whoseonfirst.db) and tables are
# created by alembic, not by the app on boot.
mkdir -p data
source venv/bin/activate && alembic upgrade head

# Playwright starts uvicorn on port 8000 itself (see playwright.config.js).
# The venv must be on PATH so the webServer command can find uvicorn.
PATH="$PWD/venv/bin:$PATH" PLAYWRIGHT_HTML_OPEN=never npx playwright test
```

On a fresh database the app seeds `admin` / `Admin123!` at first boot; the
specs use those credentials against the local server only.

## Specs

- `smoke.spec.js` — app loads
- `xss.spec.js` — WOF-18 regression: members with XSS-payload names render
  inert on team-members.html and the toggle action resolves the right member
