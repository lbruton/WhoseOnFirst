# Tasks Document

## References

- **Issue:** WHO-39
- **Spec Path:** `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/`
- **Requirements:** `requirements.md` (approved 2026-03-18)
- **Design:** `design.md` (approved 2026-03-18)

## File Touch Map

| Action | File | Scope |
|--------|------|-------|
| CREATE | `VERSION` | App version (semver, single line) |
| CREATE | `src/api/routes/version.py` | GET /api/v1/version endpoint |
| CREATE | `tests/test_version_endpoint.py` | Unit tests for version endpoint |
| MODIFY | `src/main.py` | Register version router |
| MODIFY | `frontend/components/sidebar.html` | Offcanvas toggle, collapse class, version fetch, logo placeholder |
| MODIFY | `frontend/team-members.html` | Card grid → sortable list, Sortable.js handle config, responsive CSS |
| MODIFY | `frontend/index.html` | Dashboard responsive CSS refinements |
| MODIFY | `frontend/schedule.html` | Schedule responsive CSS |
| MODIFY | `frontend/notifications.html` | Responsive CSS + card-view toggle |
| MODIFY | `frontend/schedule-overrides.html` | Responsive CSS + card-view toggle |
| MODIFY | `frontend/shifts.html` | Responsive CSS + card-view toggle |
| MODIFY | `frontend/admin.html` | Responsive CSS + mobile file input |
| MODIFY | `frontend/help.html` | Minor responsive spacing |
| MODIFY | `frontend/change-password.html` | Minor responsive spacing |
| MODIFY | `frontend/js/sidebar-loader.js` | Version fetch after sidebar load |
| TEST | All `frontend/*.html` | Manual: Chrome DevTools mobile emulation |
| TEST | `tests/test_version_endpoint.py` | pytest |

---

## UI Prototype Gate

> **BLOCKING:** Tasks 0.1-0.3 MUST be completed and approved before ANY `ui:true` task begins.

- [x] 0.1 Create visual mockup for mobile UI
  - Create mockups for: (a) sidebar offcanvas on mobile, (b) team-members sortable list, (c) card-view toggle for data tables
  - Cover all states: populated list, empty list, drag in progress, offcanvas open/closed
  - Include light and dark theme variants
  - Include a logo placeholder area (cowork is designing new logos — use a generic placeholder)
  - _Requirements: REQ-1, REQ-2, REQ-3_
  - _Prompt: Role: UI/UX Designer | Task: Create visual mockups using the ui-mockup skill for WhoseOnFirst mobile UI redesign. Three key views needed - (1) Sidebar in offcanvas drawer mode with hamburger toggle at top-left and version/theme in fixed footer, (2) Team members page with vertical sortable list using hamburger grip handles, rotation badge, name/phone, and action buttons in a single row, (3) Card-view toggle pattern for data tables showing table vs card alternatives. Cover states - populated, empty, drag-in-progress, offcanvas open/closed. Show both light and dark themes. Include a logo placeholder slot (new logo coming from external designer). | Restrictions: Do NOT write production code. Use Tabler.io/Bootstrap 5 visual patterns. Output is mockup artifacts only. | Success: Mockups cover all three views, both themes, all key states. Presented to user for feedback._

- [x] 0.2 Build interactive playground prototype
  - Build a single-file HTML playground using Tabler CDN
  - Include working sidebar offcanvas toggle, sortable list with drag handles, card-view toggle
  - Use realistic sample data (8 team members with names, phones, rotation numbers)
  - Test at 375px, 768px, and 1024px widths
  - Save to `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/artifacts/playground.html`
  - _Requirements: REQ-1, REQ-2, REQ-3, REQ-4_
  - _Prompt: Role: Frontend Prototyper | Task: Build an interactive single-file HTML playground using the playground skill for the WhoseOnFirst mobile UI redesign. Use Tabler.io CDN (same as production). Include - (1) Working offcanvas sidebar with hamburger toggle, nav items, version display, theme toggle, (2) Team members as a sortable vertical list with grip handles using Sortable.js CDN, (3) A sample data table with card-view toggle button group. Use realistic data (8 team members). Include width controls to test at 375px/768px/1024px. Both light and dark themes must work. Include a logo placeholder area for future logo swap. Save to .spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/artifacts/playground.html | Restrictions: Single self-contained HTML file. Use CDN links only. This is a throwaway prototype. | Success: Prototype works in browser at all three widths, sidebar collapses properly, drag handles work without hijacking scroll, card-view toggle swaps views._

- [x] 0.3 Visual approval checkpoint
  - Present prototype to user for review
  - Collect explicit approval or revision feedback
  - Update design.md `Prototype Artifacts` section with artifact paths
  - _Requirements: All UI requirements_
  - _Prompt: Role: Project Coordinator | Task: Present the interactive prototype from Task 0.2 to the user. Open it in a browser or describe it clearly. Ask - does the sidebar offcanvas, team member list layout, and card-view toggle look and feel right? Collect approval or revision feedback. If approved, update design.md UI Impact Assessment Prototype Artifacts section with the playground file path. | Restrictions: Do NOT proceed to any ui:true task until user explicitly approves. | Success: User approves visual design. design.md Prototype Artifacts section populated._

---

## Implementation Tasks

- [x] 1. Create VERSION file and backend version endpoint
  - **Recommended Agent:** Claude
  - **ui:false**
  - Create `VERSION` file in project root with `1.6.0`
  - Create `src/api/routes/version.py` with GET `/api/v1/version` endpoint
  - Register router in `src/main.py`
  - Create `tests/test_version_endpoint.py` with unit tests
  - _Leverage: `src/api/routes/admin.py` (existing route pattern), `src/main.py` (router registration pattern), `tests/test_settings_api.py` (existing test pattern)_
  - _Requirements: REQ-5 (AC 1, 2, 4)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Python Backend Developer | Task: Create a VERSION file in the project root containing `1.6.0`. Create `src/api/routes/version.py` with a FastAPI GET endpoint at `/api/v1/version` that reads the VERSION file and returns `{"version": "X.Y.Z"}`. If the file is missing, return `{"version": "unknown"}`. Register the router in `src/main.py` following the pattern used by other routes (see `src/api/routes/admin.py`). Create `tests/test_version_endpoint.py` testing: (a) returns correct version, (b) handles missing file gracefully. Run tests with `pytest tests/test_version_endpoint.py -v`. | Restrictions: No caching of version — read file on each request. No authentication required on this endpoint. Follow existing FastAPI route patterns exactly. | Success: `curl localhost:8000/api/v1/version` returns `{"version":"1.6.0"}`. Tests pass. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [x] 2. Sidebar offcanvas toggle and version fetch `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/components/sidebar.html`:
    - Add `collapse` class to `navbar-collapse` div
    - Add `id="sidebar-menu"` for toggle targeting
    - Add `<button class="navbar-toggler">` before the brand
    - Move `navbar-footer` outside the `collapse` div
    - Remove inline flex styles (let Tabler handle layout)
    - Replace hardcoded `v1.5.0` with `<span id="appVersion">v...</span>`
    - Add logo placeholder class for future logo swap
  - Modify `frontend/js/sidebar-loader.js`:
    - After sidebar is loaded, fetch `/api/v1/version` and populate `#appVersion`
    - Graceful fallback to "v?" on fetch failure
  - _Leverage: `frontend/components/sidebar.html` (current sidebar), `frontend/js/sidebar-loader.js` (loader), design.md Component 1 (target state HTML)_
  - _Requirements: REQ-1 (all ACs), REQ-5 (AC 3, 5)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Modify `frontend/components/sidebar.html` to add Tabler offcanvas sidebar support. Changes: (1) Add `collapse` class to the `navbar-collapse` div and set `id="sidebar-menu"`, (2) Add a `<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#sidebar-menu">` before the navbar-brand, (3) Move the `navbar-footer` div (version + theme toggle) OUTSIDE the collapse div so it remains visible when sidebar is collapsed, (4) Remove the inline `style="display: flex; flex-direction: column; height: 100vh;"` from the container-fluid — let Tabler CSS handle layout, (5) Replace the hardcoded `WhoseOnFirst v1.5.0` text with `<span id="appVersion">v...</span>`. Then modify `frontend/js/sidebar-loader.js` to fetch `/api/v1/version` after sidebar loads and populate `#appVersion` with `v` + version string, falling back to `v?` on error. Source the visual design from the approved prototype file at `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/artifacts/playground.html`. | Restrictions: Do NOT change nav item structure or auth-init.js. Do NOT add new JS libraries. Keep dark mode compatibility. Test with Chrome DevTools at 375px and 992px+. | Success: At 375px width, sidebar is hidden with hamburger toggle visible. Tapping toggle opens offcanvas drawer. At 992px+, sidebar is permanently visible (current behavior). Version displays dynamically. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [x] 3. Team members list redesign `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/team-members.html`:
    - Replace card grid (`.row.row-cards` with `col-md-6 col-lg-4`) with `.list-group` vertical list
    - Each list item: drag handle (grip icon) | avatar | name+phone | rotation badge | action buttons
    - Drag handle visible only for admin role on active filter (`.admin-only`)
    - Update Sortable.js config: add `handle: '.drag-handle'`, `delayOnTouchOnly: true`, `delay: 100`, `touchStartThreshold: 5`
    - Update CSS: remove card grid styles, add list-group hover styles, drag handle feedback
    - Ensure dark mode compatibility with `[data-bs-theme="dark"]` selectors
  - _Leverage: `frontend/team-members.html` (current implementation), design.md Component 2 (target HTML + Sortable config), `frontend/js/team-colors.js` (color assignment)_
  - _Requirements: REQ-2 (all ACs), REQ-4 (AC 1, 2)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Redesign the team-members page from a card grid to a vertical sortable list. In `frontend/team-members.html`: (1) Replace the `<div class="row row-cards" id="membersContainer">` and its `col-md-6 col-lg-4` card children with a `<div class="list-group" id="membersContainer">` containing `list-group-item` rows. Each row layout: drag-handle grip icon (`.drag-handle.admin-only`) on left, avatar with team color, name+phone in flex-fill div, rotation badge, then Edit/Deactivate buttons. (2) Update the `initSortable()` function config to add `handle: '.drag-handle'`, `delayOnTouchOnly: true`, `delay: 100`, `touchStartThreshold: 5`. (3) Update CSS: remove `.member-card` hover transform and card shadow styles, add `.member-row` hover background highlight, `.drag-handle` grab cursor, `.drag-handle:active` grabbing cursor. (4) Add `[data-bs-theme="dark"]` variants for list hover and drag states. (5) Ensure 44px minimum touch targets on buttons with 8px spacing between them. Source visual design from the approved prototype file at `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/artifacts/playground.html`. | Restrictions: Do NOT change the save order logic, modal forms, or API calls. Preserve all existing JS functions (renderMembers, saveRotationOrder, etc.) — only change the HTML template and Sortable config within them. Keep the drag hint alert. Test drag on desktop (mouse) and mobile emulation (touch). | Success: Team members display as a vertical list at all screen widths. Dragging only initiates from the grip icon. Scrolling works normally on touch devices. Save order button appears after drag. Dark mode works. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [x] 4. Dashboard (index.html) responsive CSS `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/index.html`:
    - Verify escalation chain mobile stacking (existing `@media` at 768px)
    - Add `col-6` to stat card at xs breakpoint for 2-per-row on small mobile
    - Verify calendar grid mobile reflow
    - Ensure 44px touch targets on any interactive elements
  - _Leverage: `frontend/index.html` (lines 214-237 existing media queries), design.md Component 4_
  - _Requirements: REQ-3 (AC 1, 2, 5), REQ-4 (AC 1)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Enhance responsive CSS in `frontend/index.html`. (1) The escalation chain already has a `@media (max-width: 768px)` rule stacking columns — verify it works at 375px and fix any overflow issues. (2) The stat card row uses `col-sm-6 col-lg-4` — add a `col-6` class so cards show 2-per-row even at xs widths instead of full-width stacking. (3) Verify the calendar grid reflow (existing `@media` makes it single-column at 768px) works cleanly. (4) Check all interactive elements for 44px minimum touch target. Fix any that are too small. (5) Verify dark mode compatibility of any new/changed CSS. | Restrictions: Minimal changes — this page already has decent mobile CSS. Do NOT restructure the dashboard layout. Only add/fix what's needed. | Success: Dashboard looks good at 375px, 768px, and 1024px. No horizontal overflow. Stat cards show 2-per-row on small screens. Escalation chain stacks cleanly. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [ ] 5. Schedule pages responsive CSS `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/schedule.html`:
    - 14-day preview: add single-column reflow at 576px (existing is 2-col at 768px)
    - Verify form layout stacking
  - Modify `frontend/schedule-overrides.html`:
    - Stat cards: add `col-6` for xs
    - Data table: add card-view toggle (shared pattern from design.md Component 5)
  - _Leverage: `frontend/schedule.html`, `frontend/schedule-overrides.html`, design.md Components 4 and 5_
  - _Requirements: REQ-3 (AC 1, 2, 7), REQ-4 (AC 1)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Enhance responsive CSS on schedule pages. In `frontend/schedule.html`: (1) The 14-day preview has `@media (max-width: 768px)` reflowing to 2 columns — add a second breakpoint at 576px reflowing to single column. (2) Verify form inputs (Start Date, Duration) stack cleanly on mobile. In `frontend/schedule-overrides.html`: (1) Add `col-6` to stat cards for 2-per-row at xs. (2) Add a card-view toggle for the overrides data table — use a button group (`d-md-none`) with Table/Cards options. When Cards is active, render each table row as a stacked card with key-value pairs. Toggle state persists via `localStorage.setItem('wof-overrides-view', 'cards')`. (3) Verify dark mode on all changes. | Restrictions: Reuse the same card-view toggle pattern across all table pages (consistent UI). Do NOT change table data fetching or API calls. | Success: Schedule pages work cleanly at 375px, 768px, 1024px. Card-view toggle works on overrides page. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [x] 6. Notifications page responsive + card-view toggle `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/notifications.html`:
    - Stat cards: add `col-6` for xs (currently `col-sm-6 col-lg-3`)
    - Data table: add card-view toggle (same pattern as Task 5)
    - SMS template section: verify mobile layout
    - Verify 44px touch targets on Send Test SMS button
  - _Leverage: `frontend/notifications.html`, Task 5 card-view toggle pattern, design.md Component 5_
  - _Requirements: REQ-3 (AC 1, 2, 6), REQ-4 (AC 1)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Enhance responsive CSS on `frontend/notifications.html`. (1) Add `col-6` to the 4 stat cards for 2-per-row at xs. (2) Add card-view toggle for the notification log data table — same pattern as schedule-overrides (Task 5): button group visible below 768px, Table/Cards toggle, localStorage persistence with key `wof-notifications-view`. (3) Verify the SMS template editor section lays out cleanly on mobile. (4) Ensure the Send Test SMS button meets 44px touch target. (5) Dark mode compatibility. | Restrictions: Same card-view toggle pattern as Task 5. Do NOT change notification data fetching or table rendering logic. | Success: Notifications page works at 375px/768px/1024px. Card toggle works. Stat cards 2-per-row on mobile. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [x] 7. Shifts page responsive + card-view toggle `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/shifts.html`:
    - Add card-view toggle for the shifts configuration table
    - Verify form modal works on mobile (Bootstrap modal is responsive by default)
  - _Leverage: `frontend/shifts.html`, Task 5 card-view toggle pattern_
  - _Requirements: REQ-3 (AC 1, 2, 6), REQ-4 (AC 1)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Enhance responsive CSS on `frontend/shifts.html`. (1) Add card-view toggle for the shifts configuration table — same pattern as Tasks 5-6: button group visible below 768px, Table/Cards toggle, localStorage key `wof-shifts-view`. Each shift card should show shift name, days, hours, and duration clearly. (2) Verify the shift edit/create modal works on mobile (Bootstrap modals are responsive by default, but check for any overflow issues). (3) Dark mode compatibility. | Restrictions: Same card-view toggle pattern. Do NOT change shift CRUD logic. | Success: Shifts page works at 375px/768px/1024px. Card toggle works. Modals usable on mobile. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [ ] 8. Admin, Help, Change Password responsive CSS `ui:true`
  - **Recommended Agent:** Claude
  - Modify `frontend/admin.html`:
    - Add visible file input button for mobile (`d-md-none`) alongside drop zone
    - Verify form layout stacking
  - Modify `frontend/help.html`:
    - Minor spacing adjustments for mobile card layout
  - Modify `frontend/change-password.html`:
    - Verify form stacking (should work naturally with `col-md-6`)
  - _Leverage: `frontend/admin.html`, `frontend/help.html`, `frontend/change-password.html`_
  - _Requirements: REQ-3 (AC 1, 2), REQ-4 (AC 1, 3, 4)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: Frontend Developer | Task: Final responsive CSS pass on three pages. In `frontend/admin.html`: (1) Add a visible file input button (`<input type="file">` styled as a Tabler button) with class `d-md-none` above the drag-drop zone — mobile users can't drag files, they need a tap-to-browse button. The existing drop zone stays visible on desktop (hide the button with `d-none d-md-block` is wrong — the button is for mobile, drop zone for desktop). (2) Verify export/import forms stack cleanly. In `frontend/help.html`: minor spacing check — info cards use `col-md-6` which stacks on mobile naturally. Verify no overflow. In `frontend/change-password.html`: verify `col-md-6` forms stack properly, check input types (`type="password"` is correct). (3) Dark mode compatibility on all changes. (4) Ensure all form inputs use appropriate mobile input types (REQ-4 AC 3). | Restrictions: Minimal changes on help/change-password — they should mostly work already. Focus effort on admin page file upload UX. | Success: Admin file upload works via tap on mobile. All three pages display correctly at 375px. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._

- [ ] 9. Cross-page dark mode and touch target audit
  - **Recommended Agent:** Claude
  - **ui:true**
  - Audit all modified pages in Chrome DevTools:
    - Dark mode: toggle theme, verify no white-on-white or invisible elements
    - Touch targets: verify 44px minimum on all buttons and interactive elements
    - Test at 375px, 768px, 1024px on every page
    - Fix any issues found
  - _Leverage: All modified frontend files, `frontend/js/theme.js`_
  - _Requirements: REQ-3 (AC 1), REQ-4 (all ACs)_
  - _Prompt: Implement the task for spec WHO-39-mobile-tablet-ui-redesign, first run spec-workflow-guide to get the workflow guide then implement the task. Role: QA/Frontend Developer | Task: Perform a cross-page audit of all modified pages. For each of the 8 user-facing pages + sidebar: (1) Toggle dark mode — check for white-on-white text, invisible borders, broken backgrounds, missing `[data-bs-theme="dark"]` selectors on new CSS. (2) Set viewport to 375px — check every button, link, and interactive element has at least 44x44px touch target area. Fix any that are too small by adding `min-height: 44px; min-width: 44px;` or padding. (3) Check button spacing — Edit/Deactivate buttons on team members list must have 8px+ gap. (4) Test at 768px (tablet) and 1024px (desktop) for layout correctness. Document all findings and fixes. | Restrictions: This is an audit + fix task — read every page, fix issues in place. Do NOT restructure layouts. | Success: All pages pass dark mode visual check. All touch targets are 44px+. No layout issues at any breakpoint. Mark task [-] in tasks.md before starting, log implementation with log-implementation tool after completion, then mark [x]._
