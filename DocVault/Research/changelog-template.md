---
tags: []
doc_type: reference
project: whoseonfirst
source: migrated
aliases: ["Changelog Entry Template"]
created: "2025-11-09"
updated: "2026-06-09"
migrated_from: "repo:docs/TEMPLATE_CHANGELOG.md"
---

# Version X.Y.Z - Brief Description

**Release Date**: YYYY-MM-DD
**Linear Issues**: [WHO-XXX](https://linear.app/whoseonfirst/issue/WHO-XXX)

## Overview

One concise paragraph (1-3 sentences) summarizing what this version accomplishes.

---

## Changes

### Added

#### Feature Name (WHO-XXX) - YYYY-MM-DD

**Description**: One-sentence summary of what was added and why.

**Key Features**:
- Feature detail 1 with technical specifics
- Feature detail 2 with user-facing benefits
- Feature detail 3 with implementation notes

**Technical Implementation**:
- Component/module affected: `src/path/to/file.py:123`
- API endpoints: `/api/v1/new-endpoint`
- Database changes: New `table_name` table with migration
- Scheduler jobs: New job at HH:MM AM/PM CST

**Use Case**: Real-world scenario where this feature provides value.

**Files Modified**:
- `src/models/model_name.py`: Created new model
- `src/services/service_name.py`: Added business logic
- `src/api/routes/route_name.py`: Added API endpoints
- `frontend/page.html`: Added UI components

**Docker Changes**:
- Rebuild required: Yes/No
- Migration needed: Yes/No
- Environment variables: Added `NEW_VAR` (optional)

**Validation**:
- ✅ Docker container starts without errors
- ✅ API endpoints respond correctly (tested with curl)
- ✅ UI changes visible in browser
- ✅ Scheduler job registered (visible in logs)
- ✅ Database migration applied successfully
- ✅ Tests passed (if applicable)

**Linear Issue**: [WHO-XXX](https://linear.app/whoseonfirst/issue/WHO-XXX)

---

### Fixed

- **Issue**: [Description of bug]
  - **Symptom**: What users experienced
  - **Root Cause**: Why it happened
  - **Solution**: How it was fixed
  - **Files**: `src/path/to/file.py:123`
  - **Linear Issue**: [WHO-XXX](https://linear.app/whoseonfirst/issue/WHO-XXX)

---

### Changed

- **Change**: [Description of modification]
  - **Before**: Old behavior
  - **After**: New behavior
  - **Reason**: Why the change was made
  - **Migration Required**: Yes/No
  - **Linear Issue**: [WHO-XXX](https://linear.app/whoseonfirst/issue/WHO-XXX)

---

### Security

- **Enhancement**: [Security improvement]
  - **Impact**: What this protects against
  - **Implementation**: How it works
  - **Linear Issue**: [WHO-XXX](https://linear.app/whoseonfirst/issue/WHO-XXX)

---

## Notes

### Breaking Changes

**⚠️ BREAKING**: [Description of breaking change]

**Migration Steps**:
1. Step 1
2. Step 2
3. Step 3

**Affected Users**: [Who this impacts]

### Known Issues

- **Issue**: [Description]
  - **Workaround**: [Temporary solution]
  - **Fix Planned**: [Future version]

### Docker Deployment

**Required Steps**:
```bash
# Rebuild Docker container
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d

# Apply migrations (if needed)
docker exec whoseonfirst-dev alembic upgrade head

# Verify deployment
docker-compose -f docker-compose.dev.yml logs -f
```

---

## Template Instructions

**Before Committing**:
1. Replace `X.Y.Z` with actual version number
2. Replace `YYYY-MM-DD` with release date
3. Replace `WHO-XXX` with Linear issue IDs
4. Fill in all relevant sections (delete unused)
5. Update `CHANGELOG.md` with entry
6. Update `README.md` version (if applicable)

**Section Guidelines**:
- **Added**: New features, capabilities
- **Fixed**: Bug fixes and corrections
- **Changed**: Modifications to existing features
- **Security**: Security-related changes

**Writing Style**:
- Use past tense ("Added", "Fixed", "Changed")
- Be specific and technical but clear
- Include file paths with line numbers when relevant
- Link to Linear issues for traceability
- Describe user-facing impact

---

*Template Version: 1.0 | Last Updated: 2025-11-09 | Project: WhoseOnFirst*
