# Design Document

## References

- **Issue:** WHO-39
- **Parent Epic:** WHO-37
- **Spec Path:** `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/`
- **Requirements:** `requirements.md` (5 requirements, approved 2026-03-18)

## Overview

Progressive enhancement of WhoseOnFirst's frontend for mobile and tablet devices. The design touches all 8 user-facing HTML pages plus the shared sidebar component, introduces a new backend version endpoint, and redesigns the team-members page from a card grid to a sortable vertical list. No new JavaScript libraries are added — all changes use existing Tabler.io/Bootstrap 5 responsive utilities and Sortable.js configuration options.

## Steering Document Alignment

### Technical Standards
- **No build step**: All CSS remains inline in `<style>` blocks per existing pattern
- **CDN dependencies**: Tabler.io, Tabler Icons, Sortable.js — no additions
- **Vanilla JS**: No framework introduction; existing event-driven patterns preserved
- **FastAPI backend**: New endpoint follows existing `/api/v1/` pattern

### Project Structure
- Frontend files: `frontend/*.html`, `frontend/components/sidebar.html`, `frontend/js/*.js`
- Backend: `src/api/routes/` for new version endpoint
- Config: `VERSION` file in project root

## Code Reuse Analysis

### Existing Components to Leverage
- **Tabler `navbar-vertical navbar-expand-lg`**: Already used in `sidebar.html:1` — just needs `collapse` class and toggler button added
- **Bootstrap responsive grid**: `col-sm-*`, `col-md-*`, `col-lg-*` already used across all pages — extends to missing breakpoints
- **Sortable.js v1.15.0**: Already loaded via CDN in `team-members.html:470` — add `handle` option to existing `Sortable.create()` call
- **Theme system**: `frontend/js/theme.js` handles dark mode — new CSS must use `[data-bs-theme="dark"]` selectors (existing pattern)
- **Auth-init.js**: `frontend/js/auth-init.js` gates admin-only elements — drag handle visibility follows `.admin-only` pattern

### Integration Points
- **Sidebar component**: `frontend/components/sidebar.html` is loaded by `sidebar-loader.js` into all pages — sidebar changes propagate automatically
- **FastAPI route registration**: New version route registers in `src/api/routes/` and mounts in main app
- **Docker build**: `VERSION` file must be included in Docker image (already in build context)

## Architecture

The design follows three layers of change:

```
Layer 1: Shared (sidebar.html, new JS)
  ↓ applies to all pages automatically
Layer 2: Per-Page CSS (responsive breakpoints in each HTML file's <style> block)
  ↓ page-specific layout fixes
Layer 3: Component Redesign (team-members list, table card-view toggle)
  ↓ structural HTML changes
```

### Responsive Breakpoint Strategy

| Breakpoint | Bootstrap Class | Layout Behavior |
|------------|----------------|-----------------|
| 0-575px (xs) | Default | Single column, stacked cards, offcanvas sidebar |
| 576-767px (sm) | `col-sm-*` | 2-column stat cards where space allows |
| 768-991px (md) | `col-md-*` | 2-column layouts, tablet-friendly spacing |
| 992px+ (lg) | `col-lg-*` | Full desktop layout, permanent sidebar |

## Components and Interfaces

### Component 1: Sidebar Offcanvas Toggle

**Purpose:** Make the sidebar collapsible on mobile via Tabler's native offcanvas pattern.

**Current state** (`sidebar.html:1-131`):
```html
<aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
  <div class="container-fluid" style="...">
    <!-- No toggler button -->
    <div class="navbar-collapse" style="flex: 1; overflow-y: auto;">
      <!-- Nav items -->
    </div>
  </div>
</aside>
```

**Target state:**
```html
<aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
  <div class="container-fluid">
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
            data-bs-target="#sidebar-menu" aria-controls="sidebar-menu"
            aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <h1 class="navbar-brand navbar-brand-autodark">...</h1>
    <div class="collapse navbar-collapse" id="sidebar-menu">
      <!-- Nav items (unchanged) -->
    </div>
    <div class="navbar-footer">
      <!-- Version + theme toggle (moved outside collapse so always visible) -->
    </div>
  </div>
</aside>
```

**Key changes:**
- Add `collapse` class to `navbar-collapse` div
- Add `id="sidebar-menu"` for toggle targeting
- Add `<button class="navbar-toggler">` before the brand
- Move `navbar-footer` outside the `collapse` div so version/theme toggle remain accessible
- Remove inline `style="display: flex; flex-direction: column; height: 100vh;"` — let Tabler handle layout

**Dependencies:** Tabler CSS handles all responsive behavior automatically once `collapse` class is present.

### Component 2: Team Members Sortable List

**Purpose:** Replace the card grid with a single-column sortable list with hamburger drag handles.

**Current state** (`team-members.html:556-593`):
```html
<div class="row row-cards" id="membersContainer">
  <!-- Cards: col-md-6 col-lg-4 grid -->
  <div class="col-md-6 col-lg-4" data-member-id="${member.id}">
    <div class="card member-card draggable">...</div>
  </div>
</div>
```

**Target state:**
```html
<div class="list-group" id="membersContainer">
  <div class="list-group-item member-row" data-member-id="${member.id}">
    <div class="d-flex align-items-center">
      <!-- Drag handle (admin only) -->
      <div class="drag-handle admin-only me-3" style="cursor: grab; padding: 8px;">
        <i class="ti ti-grip-vertical text-muted" style="font-size: 1.2rem;"></i>
      </div>
      <!-- Avatar -->
      <span class="avatar avatar-md me-3 ${getTeamColor(member.id, activeMembers)} avatar-initials">
        ${getInitials(member.name)}
      </span>
      <!-- Info -->
      <div class="flex-fill">
        <div class="fw-bold">${member.name}</div>
        <div class="text-muted small">${member.phone}</div>
      </div>
      <!-- Rotation badge -->
      <div class="rotation-badge me-3">${member.rotation_order + 1}</div>
      <!-- Action buttons -->
      <div class="btn-list admin-only">
        <button class="btn btn-sm btn-outline-primary">Edit</button>
        <button class="btn btn-sm btn-outline-warning">Deactivate</button>
      </div>
    </div>
  </div>
</div>
```

**Sortable.js config change** (line 607-615):
```javascript
sortableInstance = Sortable.create(container, {
    animation: 150,
    handle: '.drag-handle',        // NEW: restrict drag to grip icon
    ghostClass: 'sortable-ghost',
    dragClass: 'sortable-drag',
    delayOnTouchOnly: true,        // NEW: touch-specific delay
    delay: 100,                    // NEW: 100ms hold before drag on touch
    touchStartThreshold: 5,        // NEW: 5px movement threshold
    onEnd: function() {
        orderChanged = true;
        document.getElementById('saveOrderBtn').style.display = 'block';
    }
});
```

**CSS changes:**
- Remove `.member-card` grid styles (hover transform, card shadows)
- Add `.member-row` list styles with hover highlight
- Add `.drag-handle:active { cursor: grabbing; }` feedback
- Responsive: list items are naturally single-column at all widths

### Component 3: Version Endpoint and Sidebar Fetch

**Purpose:** Dynamic version display in sidebar footer.

**Backend** — new file `src/api/routes/version.py`:
```python
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["version"])

_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"

@router.get("/version")
def get_version():
    try:
        version = _VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        version = "unknown"
    return {"version": version}
```

**Frontend** — sidebar footer update:
```javascript
// In sidebar-loader.js or inline in sidebar.html
fetch('/api/v1/version')
  .then(r => r.json())
  .then(data => {
    const el = document.getElementById('appVersion');
    if (el) el.textContent = 'v' + data.version;
  })
  .catch(() => {
    const el = document.getElementById('appVersion');
    if (el) el.textContent = 'v?';
  });
```

**VERSION file** (project root): `1.6.0`

### Component 4: Per-Page Responsive CSS

Each page gets targeted `@media` queries. Design pattern per page:

**Dashboard (index.html):**
- Escalation chain: already has `@media (max-width: 768px)` stacking — verify it works
- Stat cards: add `col-6` for xs breakpoint (2 per row on small mobile)
- Calendar: existing reflow to single column — good as-is

**Schedule (schedule.html):**
- Two-column layout (`col-lg-7` + `col-lg-5`) already stacks below 992px — good
- 14-day preview: existing `@media` reflowing to 2 cols — add single-col at 576px

**Notifications (notifications.html):**
- 4 stat cards (`col-sm-6 col-lg-3`): add `col-6` for consistent 2-per-row on xs
- Data table: add card-view toggle (show/hide table vs card list)

**Schedule Overrides (schedule-overrides.html):**
- 3 stat cards (`col-sm-6 col-lg-4`): similar treatment
- Data table: card-view toggle

**Shifts (shifts.html):**
- Single table page — add card-view toggle for mobile

**Admin (admin.html):**
- Forms stack naturally with `col-md-6` — good
- File drop zone: add visible file input button for mobile, keep drop zone for desktop

**Help (help.html):**
- Info cards stack naturally — minor spacing adjustments

**Change Password (change-password.html):**
- Forms stack naturally — no changes needed

### Component 5: Table Card-View Toggle

**Purpose:** On mobile, wide data tables are hard to read. A card-view toggle shows each row as a stacked card.

**Pattern** (reusable across notifications, shifts, schedule-overrides):
```html
<!-- Toggle button (visible below 768px) -->
<div class="d-md-none mb-3">
  <div class="btn-group w-100">
    <button class="btn btn-outline-secondary active" data-view="table">
      <i class="ti ti-table"></i> Table
    </button>
    <button class="btn btn-outline-secondary" data-view="cards">
      <i class="ti ti-cards"></i> Cards
    </button>
  </div>
</div>

<!-- Table view (default on desktop, toggleable on mobile) -->
<div class="table-responsive" id="tableView">...</div>

<!-- Card view (hidden by default, shown when toggled on mobile) -->
<div id="cardView" style="display: none;">
  <!-- Rendered from same data as table rows -->
</div>
```

**JavaScript**: Toggle function swaps `display` between table and card views. Persists choice in `localStorage`.

## Data Models

No database changes. The only new data element is:

### VERSION File
```
1.6.0
```
Plain text, single line, semver format. Read by backend at request time (not cached).

## UI Impact Assessment

### Has UI Changes: Yes

### Visual Scope
- **Impact Level:** Redesign existing components (sidebar toggle, team-members list) + minor element additions (card-view toggles, version display)
- **Components Affected:** sidebar.html, team-members.html (major), index.html, notifications.html, schedule.html, schedule-overrides.html, shifts.html, admin.html, help.html (minor CSS)
- **Prototype Required:** Yes — team-members list redesign is a significant layout change affecting the primary admin workflow

### Prototype Artifacts
- **Stitch Screen IDs:** N/A (mockup created as HTML instead)
- **Mockup File:** `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/artifacts/mockup.html`
- **Playground File:** `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/artifacts/playground.html`
- **Brand Kit:** `/Users/lbruton/CoWork/WhoseOnFirst-Logos/final/` (banner-logo-compact.svg, icon-bare.svg, avatar-admin.svg, avatar-viewer.svg)

### Design Constraints
- **Theme Compatibility:** Must work in both light and dark modes (existing `[data-bs-theme="dark"]` selectors)
- **Existing Patterns to Match:** Tabler list-group, Tabler navbar-toggler, existing stat card layout
- **Responsive Behavior:** Single-column below 576px, 2-column at 576-991px, full layout at 992px+

### Visual Approval Gate
> **BLOCKING:** Prototype required for team-members list redesign before implementation.

## Open Questions

### Blocking (must resolve before approval)

(None)

### Resolved

- [x] ~~Minimum screen width~~ — Design targets 375px minimum (iPhone SE). Bootstrap xs breakpoint (0-575px) covers this range.
- [x] ~~user-scalable=no~~ — Defer to a future decision. Keep zoom enabled for accessibility.
- [x] ~~Card-view toggle persistence~~ — Use localStorage key per page (e.g., `wof-notifications-view`)
- [x] ~~Version caching~~ — No cache; read file on each request. The endpoint is called once per page load and the file read is sub-millisecond.

## Error Handling

### Error Scenarios
1. **VERSION file missing**
   - **Handling:** Backend returns `{"version": "unknown"}`
   - **User Impact:** Sidebar shows "v?" — functional, clearly signals a build issue

2. **Version endpoint unreachable**
   - **Handling:** Frontend catch block sets text to "v?"
   - **User Impact:** No functional impact; version display is informational only

3. **Sortable.js fails to initialize**
   - **Handling:** Existing error handling (Sortable is optional; page functions without it)
   - **User Impact:** Admin cannot reorder but can still view team members

4. **Offcanvas sidebar doesn't close**
   - **Handling:** Tabler/Bootstrap handles this natively; clicking outside or on a nav link closes it
   - **User Impact:** None expected — well-tested Bootstrap pattern

## Testing Strategy

### Unit Tests
- `test_version_endpoint.py`: Test `/api/v1/version` returns correct version, handles missing file
- Existing Sortable.js tests: No server-side changes to rotation logic — existing 30 rotation tests remain valid

### Manual Verification
- Test sidebar toggle on Chrome DevTools mobile emulation (iPhone SE, iPad, Pixel 7)
- Test drag handle on actual mobile device (iOS Safari, Chrome Android)
- Test card-view toggle on notifications, shifts, schedule-overrides pages
- Verify dark mode compatibility on all changed pages
- Verify version displays correctly in sidebar footer

### Browser Targets
- iOS Safari 16+ (iPhone SE minimum width 375px)
- Chrome Android (latest)
- Desktop Chrome, Firefox, Safari (existing support)
