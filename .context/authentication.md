# Authentication System Specification
**Version:** 2.0
**Date:** 2025-11-09
**Status:** Production-Ready Design

---

## 1. Technology Stack

### Password Encryption
- **Algorithm:** Argon2id (via `argon2-cffi`)
- **Parameters:** OWASP 2025 recommended configuration
  - Time cost: 2 iterations
  - Memory cost: 19456 KiB (19 MiB)
  - Parallelism: 1 thread
  - Hash length: 32 bytes
  - Salt length: 16 bytes (auto-generated per password)
- **Storage:** Hashed passwords stored in `users.password_hash` column (VARCHAR 255)
- **Why Argon2id:**
  - OWASP/NIST 2025 #1 recommended algorithm
  - Winner of Password Hashing Competition (2015)
  - Memory-hard (resistant to GPU/ASIC attacks)
  - No 72-byte password limit (unlike bcrypt)
  - Combines security of Argon2d and Argon2i variants

```python
# Implementation
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# OWASP recommended parameters
ph = PasswordHasher(
    time_cost=2,        # OWASP minimum
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16
)

def hash_password(password: str) -> str:
    return ph.hash(password)  # Automatic salting

def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False
```

### Session Management
- **Method:** HTTP-only cookies (not localStorage)
- **Cookie Name:** `session`
- **Cookie Attributes:**
  - `HttpOnly=True` - Prevents JavaScript access (XSS protection)
  - `SameSite=Lax` - CSRF protection
  - `Secure=True` (production only, HTTPS required)
  - **NO max_age** - Session expires on browser close
  - **NO "Remember Me"** - Security requirement, session-only

```python
# Session cookie structure (JSON)
{
    "user_id": 1,
    "created_at": "2025-11-09T12:00:00Z"
}
```

### Backend Stack
- **Framework:** FastAPI 0.115.0+
- **Database:** SQLite (Phase 1) → PostgreSQL (Phase 2+)
- **ORM:** SQLAlchemy 2.0.31+
- **Dependencies:**
  - `passlib[bcrypt]` - Password hashing
  - `python-jose` - NOT USED (we use simple cookies)
  - `python-multipart` - Form data parsing

---

## 2. Authentication Flow Diagrams

### 2.1 Login Flow
```
┌──────────┐                 ┌──────────┐              ┌──────────┐
│          │                 │          │              │          │
│  Browser │                 │  FastAPI │              │ Database │
│          │                 │          │              │          │
└────┬─────┘                 └────┬─────┘              └────┬─────┘
     │                            │                         │
     │ GET /login.html            │                         │
     ├───────────────────────────>│                         │
     │                            │                         │
     │ 200 OK (login page)        │                         │
     │<───────────────────────────┤                         │
     │                            │                         │
     │ POST /api/v1/auth/login    │                         │
     │ {username, password}       │                         │
     ├───────────────────────────>│                         │
     │                            │                         │
     │                            │ SELECT * FROM users     │
     │                            │ WHERE username=?        │
     │                            ├────────────────────────>│
     │                            │                         │
     │                            │ User record + hash      │
     │                            │<────────────────────────┤
     │                            │                         │
     │                            │ bcrypt.checkpw()        │
     │                            │ (verify password)       │
     │                            │                         │
     │ 200 OK                     │                         │
     │ Set-Cookie: session={...}  │                         │
     │ {username, role}           │                         │
     │<───────────────────────────┤                         │
     │                            │                         │
     │ Redirect to /              │                         │
     │                            │                         │
```

### 2.2 Page Access Flow (Every Page)
```
┌──────────┐                 ┌──────────┐              ┌──────────┐
│  Browser │                 │  FastAPI │              │ Database │
└────┬─────┘                 └────┬─────┘              └────┬─────┘
     │                            │                         │
     │ GET /index.html            │                         │
     ├───────────────────────────>│                         │
     │                            │                         │
     │ 200 OK (HTML)              │                         │
     │<───────────────────────────┤                         │
     │                            │                         │
     │ <script loads>             │                         │
     │                            │                         │
     │ GET /api/v1/auth/me        │                         │
     │ Cookie: session={...}      │                         │
     ├───────────────────────────>│                         │
     │                            │                         │
     │                            │ Parse cookie JSON       │
     │                            │ Extract user_id         │
     │                            │                         │
     │                            │ SELECT * FROM users     │
     │                            │ WHERE id=? AND active=1 │
     │                            ├────────────────────────>│
     │                            │                         │
     │                            │ User record             │
     │                            │<────────────────────────┤
     │                            │                         │
     │ 200 OK                     │                         │
     │ {id, username, role,       │                         │
     │  is_active}                │                         │
     │<───────────────────────────┤                         │
     │                            │                         │
     │ Store user in JS var       │                         │
     │ Apply role-based UI        │                         │
     │                            │                         │
     │ GET /api/v1/team-members   │                         │
     │ Cookie: session={...}      │                         │
     ├───────────────────────────>│                         │
     │                            │                         │
     │ (Same auth check...)       │                         │
     │                            │                         │
```

### 2.3 Unauthenticated Access
```
┌──────────┐                 ┌──────────┐
│  Browser │                 │  FastAPI │
└────┬─────┘                 └────┬─────┘
     │                            │
     │ GET /index.html            │
     ├───────────────────────────>│
     │                            │
     │ 200 OK (HTML)              │
     │<───────────────────────────┤
     │                            │
     │ GET /api/v1/auth/me        │
     │ (NO COOKIE)                │
     ├───────────────────────────>│
     │                            │
     │ 401 Unauthorized           │
     │ {detail: "Not auth..."}    │
     │<───────────────────────────┤
     │                            │
     │ window.location.href =     │
     │   '/login.html'            │
     │                            │
```

---

## 3. UI Modifications & Mockups

### 3.1 Navigation Sidebar (All Pages)
**Current:** No user display
**New Design:**

```
┌─────────────────────────────┐
│ WhoseOnFirst                │ ← Brand/Logo
├─────────────────────────────┤
│ Dashboard                   │
│ Team Members                │
│ Shift Configuration         │
│ Schedule Generation         │
│ Notifications               │
├─────────────────────────────┤
│                             │
│ (spacer)                    │
│                             │
├─────────────────────────────┤
│ 👤 admin                    │ ← User dropdown (bottom of sidebar)
│    ▼                        │
│ ┌─────────────────────────┐ │
│ │ Dashboard               │ │ ← Dropdown menu
│ │ Change Password (admin) │ │
│ │ ──────────────          │ │
│ │ Logout                  │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘

VIEWER ROLE:
┌─────────────────────────────┐
│ 👤 viewer                   │
│    ▼                        │
│ ┌─────────────────────────┐ │
│ │ Dashboard               │ │ ← "Change Password" NOT shown
│ │ ──────────────          │ │
│ │ Logout                  │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

### 3.2 Login Page Redesign
**Remove:**
- Purple gradient background
- "Remember me" checkbox
- Default credentials display

**New Design (Tabler.io Standard):**
```
┌────────────────────────────────────────────────────────┐
│                                                        │
│                                                        │
│                  WhoseOnFirst                          │ ← Clean, professional
│          On-Call Rotation Management                  │
│                                                        │
│  ┌──────────────────────────────────────────────┐    │
│  │                                              │    │
│  │        Sign in to your account               │    │
│  │                                              │    │
│  │  Username: [___________________________]     │    │
│  │                                              │    │
│  │  Password: [___________________________] 👁   │    │
│  │                                              │    │
│  │  [       Sign In       ]                     │    │
│  │                                              │    │
│  └──────────────────────────────────────────────┘    │
│                                                        │
│                                                        │
│           White background, clean typography           │
│                                                        │
└────────────────────────────────────────────────────────┘

NO "Remember Me" - Sessions expire on browser close
NO default credentials shown in UI
```

---

## 4. Security Requirements

### 4.1 Unauthenticated Access Prevention
**Rule:** Unauthenticated users can ONLY access `/login.html`

**Implementation:**
Every HTML page (index.html, team-members.html, etc.) must include:

```javascript
// FIRST thing to execute on page load
window.addEventListener('DOMContentLoaded', async function() {
    try {
        const response = await fetch('http://localhost:8000/api/v1/auth/me', {
            credentials: 'include'
        });

        if (!response.ok) {
            // Not authenticated - redirect immediately
            window.location.href = '/login.html';
            return; // Stop all page initialization
        }

        const user = await response.json();
        // Continue with page initialization...
        initializePage(user);
    } catch (error) {
        // Network error or invalid response - redirect to login
        window.location.href = '/login.html';
    }
});
```

### 4.2 API Endpoint Protection
**All** API endpoints except `/api/v1/auth/login` require authentication.

```python
# Read endpoints - Both roles can access
@router.get("/", dependencies=[Depends(require_auth)])

# Write endpoints - Admin only
@router.post("/", dependencies=[Depends(require_admin)])
@router.put("/{id}", dependencies=[Depends(require_admin)])
@router.delete("/{id}", dependencies=[Depends(require_admin)])
```

### 4.3 Role-Based UI Restrictions
**Admin Role:**
- Sees ALL buttons (Add, Edit, Delete, Generate, etc.)
- Can change password via Settings modal

**Viewer Role:**
- NO create/edit/delete buttons visible
- Settings modal shows "Read-only user - password cannot be changed"
- Form submissions blocked with alert: "You do not have permission"

---

## 5. Implementation Checklist

### Phase 1: Rollback Broken Code ✅
- [x] Backend auth is working (already tested with curl)
- [x] Need to fix frontend auth guards

### Phase 2: Fix Frontend Auth Guards
- [ ] Update all 5 pages with correct cookie-based auth check
- [ ] Remove localStorage references
- [ ] Use `/api/v1/auth/me` endpoint for auth validation
- [ ] Test: Unauthenticated user redirects to login

### Phase 3: Add User Menu to Sidebar
- [ ] Add user dropdown at bottom of sidebar (all 5 pages)
- [ ] Show username from current user
- [ ] Dropdown options:
  - Dashboard (all users)
  - Change Password (admin only)
  - Logout (all users)
- [ ] Test: Dropdown works, logout clears cookie

### Phase 4: Redesign Login Page
- [ ] Remove purple gradient (use white background)
- [ ] Remove "Remember Me" checkbox
- [ ] Remove default credentials display
- [ ] Follow Tabler.io sign-in.html example
- [ ] Test: Login still works

### Phase 5: Fix Password Change
- [ ] Remove "Remember Me" functionality from backend
- [ ] Session cookies expire on browser close (no max_age)
- [ ] Settings modal - admin can change password
- [ ] Settings modal - viewer sees read-only message
- [ ] Test: Admin can change, viewer cannot

### Phase 6: Role-Based UI
- [ ] Hide all `.admin-only` buttons for viewers
- [ ] Disable form submissions for viewers
- [ ] Test: Viewer sees read-only UI

### Phase 7: Integration Testing
- [ ] Login as admin → see all features
- [ ] Login as viewer → see read-only features
- [ ] Close browser → session expires
- [ ] Reopen browser → redirected to login

---

## 6. Expected Outcomes

### ✅ Success Criteria
1. **Zero UI Access Without Login:**
   - Visiting any page (/, /team-members.html, etc.) without auth → redirects to /login.html
   - No data loads, no placeholders show

2. **Zero API Access Without Login:**
   - All API calls return 401 Unauthorized
   - No data leakage

3. **Session Expires on Browser Close:**
   - No "Remember Me" feature
   - Closing browser clears session
   - Reopening requires login again

4. **Role-Based UI:**
   - Admin: Sees all buttons, can change password
   - Viewer: Read-only, cannot change password

5. **Professional UI:**
   - Clean Tabler.io design
   - No default credentials shown
   - User menu in sidebar

---

## 7. Technical Notes

### Why Cookies Over localStorage?
- **XSS Protection:** HttpOnly cookies cannot be accessed by JavaScript
- **Industry Standard:** OAuth2 best practices recommend cookies for web apps
- **CSRF Protection:** SameSite=Lax prevents cross-site request forgery

### Why Argon2id Over bcrypt?
- **OWASP 2025:** #1 recommended algorithm (bcrypt is "legacy systems only")
- **Memory-Hard:** Resistant to GPU/FPGA/ASIC attacks (bcrypt is only CPU-hard)
- **No Password Limit:** bcrypt truncates at 72 bytes, Argon2id has no limit
- **Future-Proof:** Winner of Password Hashing Competition, actively maintained
- **Python 3.13 Compatible:** No compatibility issues (bcrypt 5.0+ breaks with passlib)

### Why Session-Only Cookies?
- **Security:** Reduces attack window
- **User Expectation:** Corp environments expect session expiry
- **Compliance:** Meets most security audit requirements

---

## 8. Files to Modify

### Backend (Already Done ✅)
- `src/models/user.py` ✅
- `src/repositories/user_repository.py` ✅
- `src/auth/utils.py` ✅
- `src/api/routes/auth.py` ✅ (needs minor fix: remove remember_me)
- All route files (team_members, shifts, schedules, notifications) ✅

### Frontend (Needs Fixes)
- `frontend/login.html` - Redesign, remove remember_me
- `frontend/index.html` - Fix auth guard
- `frontend/team-members.html` - Fix auth guard
- `frontend/shifts.html` - Fix auth guard
- `frontend/schedules.html` - Fix auth guard
- `frontend/notifications.html` - Fix auth guard
- All 5 pages - Add user menu to sidebar

---

## Next Steps

1. **Review this specification** - Confirm approach
2. **Fix one page at a time** - Test each step
3. **Add user menu** - After pages work
4. **Redesign login** - After auth works
5. **Integration test** - Before Docker

**Estimated Time:** 2-3 hours (methodical, tested approach)
