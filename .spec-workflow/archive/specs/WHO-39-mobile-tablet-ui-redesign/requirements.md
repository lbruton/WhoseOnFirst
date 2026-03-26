# Requirements Document

## References

- **Issue:** WHO-39
- **Parent Epic:** WHO-37 (Mobile-First UI and PWA Installability)
- **Spec Path:** `.spec-workflow/specs/WHO-39-mobile-tablet-ui-redesign/`
- **Discovery Brief:** mem0 (2026-03-18, Approach C — Progressive Enhancement)

## Introduction

WhoseOnFirst's UI was built desktop-first using Tabler.io (Bootstrap 5). On mobile and tablet devices, the app has critical usability issues: the sidebar has no collapse toggle and fills the entire viewport, the team-members drag-to-sort card grid hijacks scroll gestures on touch devices (trapping users), and most pages lack proper responsive breakpoints. This spec covers a progressive enhancement of all 8 user-facing pages plus a versioning system with dynamic footer display.

## Alignment with Product Vision

WhoseOnFirst is deployed at `whoseonfirst.lbruton.cc` and will be deployed on corporate Kubernetes. Team members checking the on-call schedule will primarily use mobile devices (checking who's on call from their phone). A non-functional mobile experience undermines the core value proposition of the app.

## Requirements

### Requirement 1: Mobile Sidebar Navigation

**User Story:** As a mobile user, I want to access the navigation sidebar via a hamburger menu, so that the sidebar doesn't consume the entire screen.

#### Acceptance Criteria

1. WHEN the viewport is below 992px (lg breakpoint) THEN the sidebar SHALL collapse into an offcanvas drawer
2. WHEN the user taps the hamburger toggle icon THEN the sidebar SHALL slide in from the left as an offcanvas overlay
3. WHEN the user taps outside the offcanvas drawer or taps a navigation link THEN the drawer SHALL close
4. WHEN the viewport is 992px or wider THEN the sidebar SHALL display as a permanent vertical sidebar (current behavior)
5. IF the sidebar is in offcanvas mode THEN the page content SHALL occupy the full viewport width

### Requirement 2: Team Member Sortable List Redesign

**User Story:** As an admin user on any device, I want to reorder team members using a drag handle, so that I can sort the rotation order without accidentally triggering a re-sort when scrolling.

#### Acceptance Criteria

1. WHEN the team-members page loads THEN the system SHALL display team members in a single-column vertical list (not a card grid)
2. WHEN drag-and-drop is enabled (active filter, admin role) THEN each list row SHALL display a hamburger grip icon (drag handle) on the left side
3. WHEN the user initiates a drag via the grip icon THEN Sortable.js SHALL reorder the list (using `handle` option)
4. WHEN the user touches/scrolls anywhere on the row EXCEPT the grip icon THEN normal scrolling SHALL occur without triggering drag
5. WHEN the user completes a drag reorder THEN the "Save Rotation Order" floating button SHALL appear (existing behavior preserved)
6. IF the user is a viewer role THEN the grip icon SHALL NOT be displayed and drag-and-drop SHALL be disabled
7. WHEN viewed on any screen width (375px to 2560px) THEN the list layout SHALL remain single-column and properly sized

### Requirement 3: Responsive Breakpoints for All Pages

**User Story:** As a user on a mobile device, I want all pages to display properly at my screen size, so that I can use the app without horizontal scrolling or overlapping elements.

#### Acceptance Criteria

1. WHEN any page is viewed at 375px width THEN no content SHALL overflow horizontally and no elements SHALL overlap
2. WHEN any page is viewed between 375px-767px (mobile) THEN multi-column layouts SHALL stack to single column
3. WHEN any page is viewed between 768px-1023px (tablet) THEN layouts SHALL use 2-column grids where appropriate
4. WHEN any page is viewed at 1024px+ (desktop) THEN layouts SHALL display as currently designed
5. WHEN the dashboard (index.html) escalation chain is viewed on mobile THEN the 4-column chain SHALL stack vertically (Primary → Backup → 1st Escalation → 2nd Escalation)
6. WHEN data tables (notifications, shifts, schedule-overrides) are viewed on mobile THEN the system SHALL provide a card-view toggle as an alternative to horizontal scrolling
7. WHEN the schedule.html 14-day preview is viewed on mobile THEN it SHALL reflow to a compact single-column list

### Requirement 4: Touch-Friendly Interactive Elements

**User Story:** As a mobile user, I want buttons and interactive elements to be large enough to tap accurately, so that I don't accidentally trigger the wrong action.

#### Acceptance Criteria

1. WHEN any interactive element (button, link, toggle) is displayed on a touch device THEN it SHALL have a minimum touch target of 44x44px
2. WHEN action buttons (Edit, Deactivate) are displayed in the team member list THEN they SHALL be spaced at least 8px apart to prevent mis-taps
3. WHEN form inputs are displayed on mobile THEN they SHALL use appropriate mobile input types (`type="tel"` for phone, `type="date"` for dates)
4. WHEN the admin page file drop zone is displayed on mobile THEN the system SHALL provide a standard file input button as the primary upload method (drag-drop is secondary)

### Requirement 5: App Versioning System

**User Story:** As any user, I want to see the current app version in the sidebar footer, so that I can verify which version is deployed.

#### Acceptance Criteria

1. WHEN the app starts THEN the backend SHALL read the version from a `VERSION` file in the project root
2. WHEN `/api/v1/version` is called THEN the system SHALL return `{"version": "X.Y.Z"}`
3. WHEN any page loads THEN the sidebar footer SHALL fetch and display the current version from the API
4. WHEN a developer bumps the version THEN they SHALL only need to edit the `VERSION` file (single source of truth)
5. IF the version endpoint fails THEN the sidebar SHALL display "v?" as a graceful fallback

## Open Questions

> **GATE:** All blocking questions resolved during discovery.

### Blocking (must resolve before approval)

(None — all resolved during discovery phase)

### Non-blocking (can defer to Design)

- [ ] Minimum supported screen width: 320px or 375px? (Defaulting to 375px — iPhone SE minimum)
- [ ] Whether to add `user-scalable=no` meta tag for PWA feel (currently zoom is enabled)

### Resolved

- [x] ~~Sidebar mobile pattern~~ — Offcanvas drawer (Tabler native pattern, least rework)
- [x] ~~Drag-sort mobile UX~~ — Vertical list with hamburger drag handles, same UI desktop + mobile
- [x] ~~Versioning approach~~ — VERSION file in repo root, backend endpoint, sidebar fetches dynamically
- [x] ~~Overall approach~~ — Approach C (Progressive Enhancement), ~15 tasks

## Non-Functional Requirements

### Code Architecture and Modularity
- **Single Responsibility**: Each page's responsive CSS stays in its own `<style>` block (existing pattern)
- **Shared Components**: Sidebar changes apply via `components/sidebar.html` (affects all pages automatically)
- **No Build Step**: All CSS is inline or CDN-loaded; no Sass/PostCSS compilation required
- **Sortable.js Config**: Reuse existing Sortable.js library (v1.15.0 CDN), only change initialization options

### Performance
- No additional JavaScript libraries beyond existing Sortable.js
- CSS media queries add negligible overhead
- VERSION endpoint must respond in under 50ms (single file read)
- No layout shifts (CLS) during responsive reflow — use explicit column sizing

### Security
- VERSION endpoint is read-only, no authentication required
- No new user inputs introduced (version is server-read-only)
- Existing input validation (phone E.164, Pydantic) unchanged

### Reliability
- Sidebar must function without JavaScript (HTML `collapse` class provides CSS-only fallback)
- Version fetch failure must not block page load (graceful "v?" fallback)
- Drag-sort must not be possible without explicit grip-icon interaction (prevents accidental reorders)

### Usability
- 44px minimum touch targets on all interactive elements (WCAG 2.5.8)
- Proper spacing between action buttons to prevent mis-taps
- Card-view toggle for data tables provides mobile-friendly alternative to wide tables
- Version display confirms deployment state at a glance
