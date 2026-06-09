# RPI Process Guide for WhoseOnFirst

**Research → Plan → Implement**

## Overview

The RPI (Research-Plan-Implement) process is a lightweight 3-phase workflow designed for WhoseOnFirst development. This is adapted from HexTrackr's proven SRPI/RPI methodology but simplified for our smaller codebase and Docker-first environment.

### When to Use RPI

Use RPI for:
- **Bug Fixes**: Broken functionality that needs correction
- **Enhancements**: Improvements to existing features
- **Technical Debt**: Code quality improvements
- **Small Features**: Well-defined additions to the system

For major new features (Phase 2+), consider the full SRPI process (Specification → Research → Plan → Implement).

---

## Phase 1: RESEARCH (The WHAT)

**Duration**: 30-90 minutes
**Linear Issue**: `RESEARCH: <feature name>`
**Goal**: Understand what exists and what needs to change

### MCP Tool Usage (CRITICAL - Token Efficiency)

**Use these tools FIRST before manual file operations**:

1. **`mcp__claude-context__search_code`** - Semantic codebase search
   ```javascript
   mcp__claude-context__search_code({
     path: "/Volumes/DATA/GitHub/WhoseOnFirst",
     query: "schedule generation rotation algorithm",
     limit: 10
   })
   ```
   - **Returns**: Exact file:line locations
   - **Token savings**: 80-90% vs manual Grep/Read

2. **`mcp__memento__semantic_search`** - Historical knowledge
   ```javascript
   mcp__memento__semantic_search({
     query: "schedule auto-renewal pattern",
     entity_types: ["WHOSEONFIRST:DEVELOPMENT:PATTERN"],
     min_similarity: 0.6
   })
   ```
   - **Returns**: Past decisions and patterns
   - **Token savings**: 90%+ vs reading session logs

3. **`mcp__sequential-thinking__sequentialthinking`** - Complex problems
   - Use for breaking down multi-step architectural questions

### Process

1. **Search codebase semantically** (claude-context) for affected files
2. **Query Memento** (semantic_search) for related patterns
3. **Read specific files** identified by searches (not exploratory!)
4. **Document current state**: entry points, key modules, data models
5. **Analyze impact**: UI/UX, database, scheduler, Docker deployment
6. **Identify risks** and safeguards
7. **Estimate scope**: Can this be done in 1-2 Docker rebuild cycles?

### Outputs

- **Current State Summary**: File locations with line numbers (from claude-context)
- **Impacted Files List**: What will change
- **Impact Analysis**: UI, DB, scheduler, Docker, dependencies
- **Risks & Safeguards**: What could break, how to prevent
- **Feasibility Assessment**: Complexity estimate (low/medium/high)

### Readiness Gate

- [ ] Current state documented with **file:line references**
- [ ] Risks & rollback strategy outlined
- [ ] Affected modules enumerated
- [ ] Docker rebuild requirements identified
- [ ] Open questions answered or deferred

**When ready**: Create child `PLAN:` issue and proceed to Phase 2

---

## Phase 2: PLAN (The HOW)

**Duration**: 30-60 minutes
**Linear Issue**: `PLAN: <feature name>` (child of RESEARCH)
**Goal**: Break down implementation into concrete tasks

### Process

1. **Create task table** with: ID, Step, Est (min), Files, Validation, Risk
2. **Estimate task sizes** (target 15-60 minutes per task)
3. **Write before/after code** for each task
4. **Define validation plan** (tests, manual checks)
5. **Document Docker rebuild points** (after which tasks?)
6. **Mark NEXT task** (only one at a time)

### Task Table Format

| ID | Step (action verb) | Est | Files/Modules | Validation | Risk | Docker Rebuild? |
|----|-------------------|-----|---------------|------------|------|-----------------|
| 1.1 | Add auto-renewal check function | 30 | `src/scheduler/schedule_manager.py:45` | Unit test | Low | No |
| 1.2 | Register scheduler job | 15 | `src/scheduler/schedule_manager.py:80` | Check logs | Low | Yes (test job) |
| 1.3 | Add settings API endpoint | 45 | `src/api/routes/settings.py` (NEW) | API test | Med | Yes (test API) |

### Before/After Example

**Task 1.1 - Add auto-renewal check function**:
```python
# Before: No auto-renewal logic exists

# After: Add function to schedule_manager.py
def check_auto_renewal() -> None:
    """
    Check if schedule auto-renewal is needed and generate new schedules.
    Runs daily at 2:00 AM CST.
    """
    with get_db_session() as db:
        settings_service = SettingsService(db)

        if not settings_service.is_auto_renew_enabled():
            logger.info("Auto-renewal is disabled")
            return

        # Implementation...
```

### Outputs

- **Task table** with 3-10 actionable tasks
- **Before/after code** for each task
- **Validation plan** (pytest, manual checks, log verification)
- **Docker rebuild points** (when to rebuild container)
- **Backout strategy** (git revert commands)

### Preflight Checklist

- [ ] Branch created (or working on main if simple fix)
- [ ] Task sizes fit 15-60 minute windows
- [ ] Docker rebuild points identified
- [ ] Test/validation approach clear
- [ ] Database migration needs identified (if any)

**When ready**: Create child `IMPLEMENT:` issue and proceed to Phase 3

---

## Phase 3: IMPLEMENT (The BUILD)

**Duration**: 1-3 hours (may span multiple sessions)
**Linear Issue**: `IMPLEMENT: <feature name>` (child of PLAN)
**Goal**: Execute tasks with Docker rebuild checkpoints

### Docker-First Implementation Pattern

**Critical**: WhoseOnFirst uses Docker for development. Code changes require container rebuild.

```bash
# Before starting implementation
git status  # Verify clean worktree

# Safety commit (optional but recommended)
git add -A
git commit -m "🔐 pre-work snapshot (WHO-XX)"

# Implementation cycle:
# 1. Make code changes (Edit/Write tools)
# 2. Test locally if needed (Python syntax check)
# 3. Commit changes
# 4. Rebuild Docker container
# 5. Verify in running container
# 6. Repeat for next task

# Rebuild Docker (after each task or batch of tasks)
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d

# Verify changes
docker-compose -f docker-compose.dev.yml logs -f
```

### Process

1. **Verify clean worktree**: `git status` must be clean
2. **Create safety commit** (optional): `git commit -m "🔐 pre-work snapshot (WHO-XX)"`
3. **Read PLAN** and locate task marked **NEXT**
4. **Execute Task 1.1**:
   - Apply code changes (Edit/Write)
   - Run validation (if possible without Docker)
   - Commit: `git commit -m "feat(scheduler): Add auto-renewal check (WHO-XX Task 1.1)"`
   - **Rebuild Docker if needed**
   - Verify in logs
5. **Execute Task 1.2** (repeat pattern)
6. **Run full validation** after all tasks complete
7. **Prepare PR** (if using branches) or update Linear issue

### Git Commit Pattern

```bash
# Safety checkpoint (before starting)
git commit -m "🔐 pre-work snapshot (WHO-XX)"

# Task commits (descriptive, reference issue + task)
git commit -m "feat(settings): Add auto-renewal configuration model (WHO-XX Task 1.1)"
git commit -m "feat(scheduler): Register auto-renewal job at 2:00 AM (WHO-XX Task 1.2-1.3)"
git commit -m "feat(frontend): Add auto-renewal toggle UI (WHO-XX Task 1.4)"

# Final Docker rebuild and verification
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d
```

### Outputs

- **Completed code changes** (all PLAN tasks executed)
- **Git commits** (every 1-3 tasks)
- **Docker container rebuilt** and verified
- **Validation results** (tests passed, logs clean)
- **Linear issue updated** with completion notes

### Live Checklist

- [ ] Clean worktree confirmed
- [ ] Safety commit created (optional)
- [ ] Task 1.1 completed and committed
- [ ] Docker rebuilt (if needed for Task 1.1)
- [ ] Task 1.2 completed and committed
- [ ] Docker rebuilt (if needed for Task 1.2)
- [ ] ...continue for all tasks
- [ ] Final Docker rebuild and verification
- [ ] All validation checks passed
- [ ] Linear issue marked complete

### Verification (post-implementation)

- [ ] Docker container starts without errors
- [ ] Logs show expected behavior (scheduler jobs, API endpoints)
- [ ] Manual testing complete (UI changes, API calls)
- [ ] No console errors in browser (if frontend changes)
- [ ] Database migrations applied (if schema changes)

**When complete**: Mark Linear issues as Done, update Memento with insights

---

## Docker-Specific Considerations

### When to Rebuild

- **Always rebuild** when changing Python code (backend logic)
- **Always rebuild** when adding new dependencies
- **Always rebuild** when modifying scheduler jobs
- **Optional rebuild** for frontend-only changes (can refresh browser)
- **Always rebuild** for testing integration changes

### Debugging in Docker

```bash
# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Access database
docker exec -it whoseonfirst-dev sqlite3 /app/data/whoseonfirst.db

# Verify scheduler jobs
# Look for log lines: "Scheduled job: Auto-Renewal Schedule Check (next run: ...)"

# Check container health
docker ps | grep whoseonfirst-dev
```

---

## MCP Tool Best Practices

### Token Efficiency Hierarchy

1. **First**: Memento semantic search (find historical decisions)
2. **Second**: Claude-context semantic search (find current code)
3. **Third**: Sequential thinking (decompose complex problems)
4. **Last**: Manual file operations (Read specific files only)

### Anti-Patterns (Avoid These)

❌ **Reading multiple files speculatively**
```javascript
// Don't do this:
Read('src/scheduler/schedule_manager.py')  // 200 lines
Read('src/services/schedule_service.py')   // 300 lines
Read('src/models/schedule.py')             // 150 lines
// Total: 650 lines, most irrelevant
```

✅ **Semantic search first, targeted reads second**
```javascript
// Do this instead:
mcp__claude-context__search_code({
  query: "auto-renewal schedule generation function",
  limit: 5
})
// Returns: schedule_manager.py:75-95 (exact location)

Read('src/scheduler/schedule_manager.py', { offset: 70, limit: 30 })
// Only reads 30 lines around target
```

---

## Example: Schedule Auto-Renewal Feature (WHO-2)

### Phase 1: RESEARCH (45 min)

**Created**: WHO-2

**Claude-Context Search**:
```javascript
mcp__claude-context__search_code({
  query: "schedule generation service database query",
  limit: 10
})
// Found: src/services/schedule_service.py:120-145
```

**Current State**:
- Schedule generation: `schedule_service.py:generate_schedule()`
- Settings model: Needs creation
- Scheduler jobs: `schedule_manager.py:45`
- Frontend toggle: Needs addition to `schedule.html`

**Impact Analysis**:
- **Database**: Add `settings` table (new migration)
- **Backend**: New SettingsService, API endpoints
- **Scheduler**: New `check_auto_renewal()` job at 2:00 AM
- **Frontend**: Toggle UI in schedule.html
- **Docker**: Rebuild required after backend changes

**Risks**:
- Migration could fail if table exists → Use `alembic stamp head` if needed
- Scheduler job conflicts → Use unique job ID `auto_renewal_check`

**Readiness**: ✅ All checkboxes complete

### Phase 2: PLAN (30 min)

**Created**: WHO-2 (continue in same issue for small features)

**Task Table**:
| ID | Step | Est | Files | Validation | Docker Rebuild? |
|----|------|-----|-------|------------|-----------------|
| 1.1 | Create Settings model | 15 | `src/models/settings.py` (NEW) | Import test | No |
| 1.2 | Create SettingsRepository | 15 | `src/repositories/settings_repository.py` (NEW) | Import test | No |
| 1.3 | Create SettingsService | 20 | `src/services/settings_service.py` (NEW) | Import test | No |
| 1.4 | Add settings API routes | 20 | `src/api/routes/settings.py` (NEW) | Manual API test | Yes |
| 1.5 | Add check_auto_renewal job | 30 | `src/scheduler/schedule_manager.py:80` | Check logs | Yes |
| 1.6 | Add frontend toggle | 30 | `frontend/schedule.html:250` | Manual UI test | Yes |
| 1.7 | Create migration | 15 | `alembic/versions/` | Run migration | Yes |

**Preflight**: ✅ All checkboxes complete

### Phase 3: IMPLEMENT (2 hours)

**Created**: WHO-2 (continue tracking in same issue)

```bash
# Tasks 1.1-1.3: Create models/repositories/services
git commit -m "feat(settings): Add Settings model and service layer (WHO-2 Tasks 1.1-1.3)"

# Task 1.4: Add API endpoints
git commit -m "feat(api): Add settings API endpoints for auto-renewal (WHO-2 Task 1.4)"
# Rebuild Docker to test API
docker-compose -f docker-compose.dev.yml down && docker-compose -f docker-compose.dev.yml build && docker-compose -f docker-compose.dev.yml up -d

# Task 1.5: Add scheduler job
git commit -m "feat(scheduler): Add auto-renewal check job at 2:00 AM (WHO-2 Task 1.5)"
# Rebuild Docker to verify job registration
docker-compose -f docker-compose.dev.yml down && docker-compose -f docker-compose.dev.yml build && docker-compose -f docker-compose.dev.yml up -d
# Check logs: "Scheduled job: Auto-Renewal Schedule Check"

# Task 1.6: Frontend toggle
git commit -m "feat(frontend): Add auto-renewal toggle UI (WHO-2 Task 1.6)"
# Rebuild Docker for full integration test
docker-compose -f docker-compose.dev.yml down && docker-compose -f docker-compose.dev.yml build && docker-compose -f docker-compose.dev.yml up -d

# Task 1.7: Migration
alembic revision --autogenerate -m "Add settings table for auto-renewal"
docker exec whoseonfirst-dev alembic upgrade head
git commit -m "feat(db): Add settings table migration (WHO-2 Task 1.7)"
```

**Verification**: ✅ All tests passed, Docker logs clean, UI functional

---

## Summary

| Aspect | WhoseOnFirst RPI | HexTrackr SRPI |
|--------|------------------|----------------|
| **Phases** | 3 (Research, Plan, Implement) | 4 (+ Specification) |
| **Linear Issues** | 1-3 issues (can combine for small features) | 4 parent-child issues |
| **Docker-Aware** | ✅ Yes (rebuild checkpoints) | N/A |
| **Duration** | 2-4 hours total | 5-12 hours total |
| **Use Case** | Bug fixes, enhancements, small features | Major new features |
| **MCP Tools** | claude-context, memento, sequential-thinking | Same + context7 |

---

**Version**: 1.0.0
**Last Updated**: 2025-11-09
**Authority**: This document defines the official RPI process for WhoseOnFirst development
**Adapted From**: HexTrackr SRPI_PROCESS.md
