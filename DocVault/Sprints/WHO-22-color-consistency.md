---
tags: []
doc_type: sprint
project: whoseonfirst
source: migrated
aliases: ["WHO-22 Color Consistency"]
created: "2025-11-21"
updated: "2026-06-09"
migrated_from: "repo:docs/sprints/WHO-22-color-consistency.md"
---

# WHO-22: Global Team Member Color Consistency System
**Sprint Plan - Simplified JavaScript Approach**

---

## Sprint Overview

**Linear Issue**: [WHO-22](https://linear.app/hextrackr/issue/WHO-22)
**Type**: Bug Fix / UX Enhancement
**Estimated Time**: 40 minutes
**Approach**: Shared JavaScript function (Option B - Simplified)
**Git Checkpoint**: `WHO-22-checkpoint` (commit: 36fcf3b)

---

## Problem Summary

Team member avatar colors are inconsistent across pages:
- **Dashboard**: Sorts by ID, uses `sorted.findIndex()`
- **Notifications**: Sorts by ID, uses `sorted.findIndex()` ✅ (same as Dashboard)
- **Schedule**: Uses loop index directly ❌
- **Team Members**: Uses forEach index ❌

**Result**: Gary K appears in different colors depending on page.

---

## Solution: Shared JavaScript Function

Create `frontend/js/team-colors.js` with the Dashboard/Notifications algorithm, then include it on all pages.

**Algorithm**:
```javascript
function getTeamColor(memberId, allMembers) {
    const sorted = [...allMembers].sort((a, b) => a.id - b.id);
    const index = sorted.findIndex(m => m.id === memberId);
    return TEAM_COLORS[index % TEAM_COLORS.length];
}
```

**Why This Works**:
- Handles ID gaps gracefully (Lance B is ID 9, but Ken U at ID 5 is inactive)
- Consistent across all pages (same ID = same position in sorted array)
- No database changes needed
- Works with deactivation workflow (primary pattern)

---

## Implementation Plan

### Phase 1: Research (COMPLETE ✅)

**Files Analyzed**:
- ✅ `frontend/index.html:346-350` - Dashboard algorithm (GOOD - use this)
- ✅ `frontend/notifications.html:496-500` - Notifications algorithm (GOOD - same as Dashboard)
- ✅ `frontend/schedule.html:266-268` - Schedule algorithm (BAD - uses loop index)
- ✅ `frontend/team-members.html` - Team Members inline logic (BAD - uses forEach index)

**Current Team Member IDs** (from database):
```
ID  Name      Active  Expected Color Index
1   Lonnie B  True    0 → team-color-1
2   Ben B     True    1 → team-color-2
3   Ben D     True    2 → team-color-3
4   Matt C    True    3 → team-color-4
5   Ken U     False   (inactive - not counted)
6   Gary K    True    4 → team-color-5
7   Clark M   True    5 → team-color-6
9   Lance B   True    6 → team-color-7
```

**Note**: ID 8 is missing, but algorithm handles this perfectly via `sorted.findIndex()`.

---

### Phase 2: Plan (THIS DOCUMENT)

**Tasks Breakdown**:

#### Task 1: Create Shared JavaScript File (10 min)
- **File**: `frontend/js/team-colors.js` (NEW)
- **Contents**: TEAM_COLORS array + getTeamColor function
- **Pattern**: Extract from Dashboard's working implementation

#### Task 2: Update Schedule Page (10 min)
- **File**: `frontend/schedule.html`
- **Changes**:
  1. Add `<script src="/js/team-colors.js"></script>` in `<head>`
  2. Remove local `getTeamColor(index)` function (line 266-268)
  3. Update calendar rendering to pass `member.id` and `allMembers` array
  4. Find and update all calls to `getTeamColor()`

#### Task 3: Update Team Members Page (5 min)
- **File**: `frontend/team-members.html`
- **Changes**:
  1. Add `<script src="/js/team-colors.js"></script>` in `<head>`
  2. Replace inline `team-color-${(index % 16) + 1}` with `getTeamColor(member.id, allMembers)`
  3. Find avatar rendering logic in member list display

#### Task 4: Update Dashboard and Notifications (5 min)
- **Files**: `frontend/index.html`, `frontend/notifications.html`
- **Changes**:
  1. Add `<script src="/js/team-colors.js"></script>` in `<head>`
  2. Remove local TEAM_COLORS arrays (now in shared file)
  3. Remove local `getTeamColor()` functions (now in shared file)
  4. Verify existing calls still work

#### Task 5: Docker Rebuild & Test (10 min)
- **Docker**: Rebuild container to pick up new JavaScript file
- **Manual Testing**:
  1. Navigate to Dashboard → note Gary K's color
  2. Navigate to Team Members → verify same color
  3. Navigate to Schedule → verify same color
  4. Navigate to Notifications → verify same color
  5. Test with all 7 active members
  6. Refresh pages to verify persistence

---

### Phase 3: Implement

**Execute tasks in order. Mark as complete before proceeding to next.**

---

## Task Details

### Task 1: Create `frontend/js/team-colors.js`

**Location**: `/Volumes/DATA/GitHub/WhoseOnFirst/frontend/js/team-colors.js` (NEW)

**File Contents**:
```javascript
/**
 * Team Member Color Utilities
 *
 * Provides consistent color assignment for team member avatars across all pages.
 *
 * Algorithm: Sort members by ID, find index in sorted array, use modulo for color.
 * This ensures the same member always gets the same color regardless of page or data ordering.
 *
 * Handles ID gaps gracefully (e.g., if ID 8 is deleted, ID 9 still gets consistent color).
 */

// 16-color WCAG AA compliant palette
const TEAM_COLORS = [
    'team-color-1',  'team-color-2',  'team-color-3',  'team-color-4',
    'team-color-5',  'team-color-6',  'team-color-7',  'team-color-8',
    'team-color-9',  'team-color-10', 'team-color-11', 'team-color-12',
    'team-color-13', 'team-color-14', 'team-color-15', 'team-color-16'
];

/**
 * Get consistent color class for team member across all pages.
 *
 * @param {number} memberId - Team member ID from database
 * @param {Array} allMembers - Array of all team member objects (must have 'id' property)
 * @returns {string} Color class (e.g., 'team-color-5')
 *
 * @example
 * const members = [{id: 1, name: 'Lonnie'}, {id: 6, name: 'Gary'}];
 * getTeamColor(6, members); // Returns 'team-color-2' (Gary is 2nd in sorted array)
 */
function getTeamColor(memberId, allMembers) {
    // Sort by ID to ensure consistent ordering
    const sorted = [...allMembers].sort((a, b) => a.id - b.id);

    // Find position in sorted array
    const index = sorted.findIndex(m => m.id === memberId);

    // Handle not found (shouldn't happen, but defensive)
    if (index === -1) {
        console.warn(`Team member ID ${memberId} not found in members array`);
        return TEAM_COLORS[0]; // Default to first color
    }

    // Map to color palette using modulo (handles teams > 16 members)
    return TEAM_COLORS[index % TEAM_COLORS.length];
}
```

**Action**: Create this file with exact contents above.

---

### Task 2: Update `frontend/schedule.html`

**File**: `/Volumes/DATA/GitHub/WhoseOnFirst/frontend/schedule.html`

**Step 2.1**: Add script include in `<head>` section

**Find** (around line 30-40, in `<head>`):
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

**Add after**:
```html
<script src="/js/team-colors.js"></script>
```

**Step 2.2**: Remove local `getTeamColor()` function

**Find and DELETE** (lines 266-268):
```javascript
function getTeamColor(index) {
    return `team-color-${(index % 16) + 1}`;
}
```

**Step 2.3**: Update calendar rendering logic

**Find** (search for where `getTeamColor` is called in schedule rendering):
- Look for calendar cell rendering
- Likely in a loop like `schedules.forEach((schedule, index) => ...)`

**Change FROM**:
```javascript
const colorClass = getTeamColor(index);
```

**Change TO**:
```javascript
const colorClass = getTeamColor(schedule.team_member.id, allMembers);
```

**Note**: You'll need to ensure `allMembers` array is available in the scope where colors are assigned. This might require passing it as a parameter to rendering functions.

**Step 2.4**: Verify `allMembers` is available

**Check**: Does the page already fetch all team members? If not, you'll need to add:
```javascript
// Fetch all team members for color consistency
async function fetchAllMembers() {
    const response = await fetch('/api/v1/team-members/');
    const data = await response.json();
    return data;
}
```

Then call this before rendering and store in a variable accessible to rendering functions.

---

### Task 3: Update `frontend/team-members.html`

**File**: `/Volumes/DATA/GitHub/WhoseOnFirst/frontend/team-members.html`

**Step 3.1**: Add script include in `<head>` section

**Find** (around line 30-40, in `<head>`):
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

**Add after**:
```html
<script src="/js/team-colors.js"></script>
```

**Step 3.2**: Update member list rendering

**Find** (search for inline color assignment):
```javascript
team-color-${(index % 16) + 1}
```

**Change TO**:
```javascript
${getTeamColor(member.id, allMembers)}
```

**Note**: The rendering function should already have access to `allMembers` since it's iterating through them.

**Example**:
```javascript
// BEFORE
members.forEach((member, index) => {
    const colorClass = `team-color-${(index % 16) + 1}`;
    // ... render avatar with colorClass
});

// AFTER
members.forEach((member, index) => {
    const colorClass = getTeamColor(member.id, members);
    // ... render avatar with colorClass
});
```

---

### Task 4: Update `frontend/index.html` and `frontend/notifications.html`

**Files**:
- `/Volumes/DATA/GitHub/WhoseOnFirst/frontend/index.html`
- `/Volumes/DATA/GitHub/WhoseOnFirst/frontend/notifications.html`

**Step 4.1**: Add script include in `<head>` section (both files)

**Find** (around line 30-40, in `<head>`):
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

**Add after**:
```html
<script src="/js/team-colors.js"></script>
```

**Step 4.2**: Remove local TEAM_COLORS array (both files)

**Dashboard (index.html) - Find and DELETE** (around line 338-343):
```javascript
const TEAM_COLORS = [
    'team-color-1',  'team-color-2',  'team-color-3',  'team-color-4',
    // ... rest of array
];
```

**Notifications (notifications.html) - Find and DELETE** (around line 488-493):
```javascript
const TEAM_COLORS = [
    'team-color-1',  'team-color-2',  'team-color-3',  'team-color-4',
    // ... rest of array
];
```

**Step 4.3**: Remove local `getTeamColor()` function (both files)

**Dashboard (index.html) - Find and DELETE** (around line 346-350):
```javascript
function getTeamColor(memberId, allMembers) {
    const sorted = [...allMembers].sort((a, b) => a.id - b.id);
    const index = sorted.findIndex(m => m.id === memberId);
    return TEAM_COLORS[index % TEAM_COLORS.length];
}
```

**Notifications (notifications.html) - Find and DELETE** (around line 496-500):
```javascript
function getTeamColor(memberId, allMembers) {
    const sorted = [...allMembers].sort((a, b) => a.id - b.id);
    const index = sorted.findIndex(m => m.id === memberId);
    return TEAM_COLORS[index % TEAM_COLORS.length];
}
```

**Step 4.4**: Verify existing calls still work

The existing `getTeamColor(member.id, allMembers)` calls should now use the shared function automatically.

**No code changes needed** - just verify that the function calls remain the same.

---

### Task 5: Docker Rebuild & Test

**Step 5.1**: Rebuild Docker container

```bash
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d
```

**Step 5.2**: Verify container is healthy

```bash
docker ps --filter "name=whoseonfirst"
```

Should show: `Up X seconds (healthy)`

**Step 5.3**: Manual Testing Checklist

Open browser to `http://localhost:8900`

**Test 1: Dashboard**
- [ ] Navigate to Dashboard
- [ ] Note Gary K's color in "On-Call Now" section
- [ ] Note Gary K's color in calendar (if visible)
- [ ] Screenshot or write down: Gary K = team-color-X

**Test 2: Team Members**
- [ ] Navigate to Team Members page
- [ ] Find Gary K in the list
- [ ] Verify color matches Dashboard
- [ ] Check all 7 active members have colors

**Test 3: Schedule**
- [ ] Navigate to Schedule page
- [ ] Generate schedule if needed
- [ ] Find Gary K in generated schedule
- [ ] Verify color matches Dashboard and Team Members

**Test 4: Notifications**
- [ ] Navigate to Notifications page
- [ ] Find notification with Gary K as recipient
- [ ] Verify color matches other pages

**Test 5: All Members Consistency**
- [ ] For each active member (Lonnie B, Ben B, Ben D, Matt C, Gary K, Clark M, Lance B):
  - [ ] Verify same color on all 4 pages

**Test 6: Page Refresh**
- [ ] Refresh Dashboard → colors unchanged
- [ ] Refresh Team Members → colors unchanged
- [ ] Refresh Schedule → colors unchanged
- [ ] Refresh Notifications → colors unchanged

**Test 7: Browser Console**
- [ ] Open DevTools Console (F12)
- [ ] Check for any JavaScript errors
- [ ] Verify `getTeamColor` is defined globally
- [ ] Test: `getTeamColor(6, [{id:1}, {id:6}, {id:9}])` should return `'team-color-2'`

**Step 5.4**: Docker Logs Verification

```bash
docker-compose -f docker-compose.dev.yml logs -f --tail=50
```

- [ ] No errors in startup
- [ ] FastAPI started successfully
- [ ] No JavaScript load errors (check browser console, not Docker logs)

---

## Expected Color Mapping

Based on current active team members (sorted by ID):

| Position | ID | Name     | Expected Color   |
|----------|----|----------|------------------|
| 0        | 1  | Lonnie B | team-color-1     |
| 1        | 2  | Ben B    | team-color-2     |
| 2        | 3  | Ben D    | team-color-3     |
| 3        | 4  | Matt C   | team-color-4     |
| 4        | 6  | Gary K   | team-color-5     |
| 5        | 7  | Clark M  | team-color-6     |
| 6        | 9  | Lance B  | team-color-7     |

**Key Test**: Gary K (ID 6) should be **team-color-5** on ALL pages.

---

## Rollback Plan

If something breaks:

```bash
# Reset to checkpoint
git reset --hard WHO-22-checkpoint

# Rebuild Docker
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d
```

---

## Success Criteria

- [x] Shared `team-colors.js` file created
- [x] All 4 pages include shared script
- [x] All 4 pages use `getTeamColor(memberId, allMembers)` consistently
- [x] Gary K shows **same color** on all 4 pages
- [x] All 7 active members have consistent colors
- [x] Docker rebuild successful with no errors
- [x] No JavaScript console errors
- [x] Colors persist after page refresh

---

## Completion

**Commit Message**:
```
feat(WHO-22): implement global team member color consistency

- Created shared team-colors.js with consistent getTeamColor() algorithm
- Updated all 4 frontend pages to use shared function
- Removed duplicate TEAM_COLORS arrays and local functions
- Colors now consistent across Dashboard, Team Members, Schedule, and Notifications
- Handles ID gaps gracefully (e.g., missing ID 8)

Estimated time: 40 minutes
Approach: Shared JavaScript function (Option B - Simplified)
Rollback: git reset --hard WHO-22-checkpoint

Closes WHO-22
```

**Next Steps After Commit**:
1. Update WHO-22 Linear issue to "Done" status
2. Add comment with testing results
3. Push to GitHub
4. Update CHANGELOG.md (v1.2.1 patch release)

---

**Sprint Created**: 2025-11-21 19:25 CST
**Sprint Completed**: 2025-11-21 21:00 CST
**Status**: ✅ COMPLETE
**Checkpoint**: WHO-22-checkpoint (commit: 36fcf3b)

---

## 🎉 Sprint Completion Summary

### Implementation Results

**Commits:**
- `76df20c` - Initial color consistency implementation (shared team-colors.js)
- `4ae9e1b` - Bonus fix for inactive member display (gray coloring)

**Actual Time:** ~2 hours (including discovery and bonus fix)
**Estimated Time:** 40 minutes

**Time Breakdown:**
- Research & Planning: 30 min ✅
- Implementation: 45 min ✅
- Testing & Discovery: 30 min ✅
- Bonus Fix (inactive members): 15 min ⭐

### Files Modified

1. ✅ `frontend/js/team-colors.js` (NEW) - Shared color utilities
2. ✅ `frontend/index.html` - Dashboard with conditional coloring
3. ✅ `frontend/team-members.html` - Team Members with activeMembers filter
4. ✅ `frontend/schedule.html` - Schedule with shared function
5. ✅ `frontend/notifications.html` - Notifications with conditional coloring
6. ✅ `docs/sprints/WHO-22-color-consistency.md` (THIS FILE)

### All Success Criteria Met ✅

- ✅ Shared `team-colors.js` file created
- ✅ All 4 pages include shared script
- ✅ All 4 pages use `getTeamColor(memberId, allMembers)` consistently
- ✅ Gary K shows **same color** on all 4 pages (team-color-5 / Purple)
- ✅ Clark M shows **same color** on all 4 pages (team-color-6 / Cyan)
- ✅ All 7 active members have consistent colors
- ✅ Ken U (inactive) displays in gray on historical records
- ✅ Docker rebuild successful with no errors
- ✅ No JavaScript console errors
- ✅ Colors persist after page refresh

### Bonus Achievement ⭐

**Discovered Issue:** Inactive members (Ken U) were missing from historical calendar views after being deactivated on Nov 16th.

**Solution:** Implemented dynamic coloring logic:
- Dashboard & Notifications fetch ALL members (including inactive)
- Conditional color assignment: inactive → `bg-secondary` (gray), active → algorithm
- Filter to active members only before calculating algorithm-based colors

**Result:** Historical schedules/notifications now display correctly with inactive members shown in gray.

### Verified Color Assignments

All pages tested via Chrome DevTools:

| Member | Color | Status | Verification |
|--------|-------|--------|--------------|
| Lonnie B | team-color-1 (Blue) | Active | ✅ All 4 pages |
| Ben B | team-color-2 (Green) | Active | ✅ All 4 pages |
| Ben D | team-color-3 (Yellow) | Active | ✅ All 4 pages |
| Matt C | team-color-4 (Pink) | Active | ✅ All 4 pages |
| Gary K | team-color-5 (Purple) | Active | ✅ All 4 pages |
| Clark M | team-color-6 (Cyan) | Active | ✅ All 4 pages |
| Lance B | team-color-7 (Orange) | Active | ✅ All 4 pages |
| Ken U | bg-secondary (Gray) | Inactive | ✅ Dashboard & Notifications |

### Linear Issue

- **Issue**: [WHO-22](https://linear.app/hextrackr/issue/WHO-22)
- **Status**: ✅ Done
- **Updated**: 2025-11-21 21:00 CST
- **Comment**: Added implementation summary with verified results

### Release

**Version:** v1.2.1 (patch release)
**CHANGELOG:** Updated with both fixes (color consistency + inactive member display)

---

**Sprint Status**: ✅ COMPLETE - Shipped in WhoseOnFirst v1.2.1
