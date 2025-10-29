# PrimeTrade Production Deployment Plan

**Project:** django-primetrade  
**Target:** https://prt.barge2rail.com or https://primetrade-u2a6.onrender.com  
**Date:** October 29, 2025  
**Status:** READY TO EXECUTE  
**Risk Level:** MEDIUM (32/60)  
**Protocol:** MEDIUM RISK DEPLOYMENT  
**Conventions:** BARGE2RAIL_CODING_CONVENTIONS_v1.2.md

---

## Executive Summary

**Current Status:** PrimeTrade has excellent SSO integration but a CRITICAL frontend/backend authentication mismatch that prevents actual use after SSO login.

**What Works:**
- ✅ SSO OAuth flow (authentication)
- ✅ Application-specific role authorization
- ✅ Backend API endpoints
- ✅ Data models and business logic
- ✅ Production infrastructure configured

**Critical Issue:**
- ❌ Frontend uses Firebase Auth (expects localStorage tokens)
- ❌ Backend uses Django sessions (provides session cookies)
- ❌ Result: Users can't access app after SSO login

**Fix Required:** Replace Firebase auth code with Django session-based authentication (2-3 hours)

**Timeline to Production:** 5–6 days (modified MEDIUM protocol)

---

## Risk Assessment

**Risk Score:** 32/60 (MEDIUM RISK)

### Risk Breakdown
- **Authentication Changes:** 10/20 (modifying existing SSO, not breaking it)
- **Data Impact:** 0/20 (no schema changes, no data migration)
- **User Impact:** 12/20 (blocking issue for all users, but caught pre-production)
- **Reversibility:** 10/20 (can rollback frontend changes easily)

### Why MEDIUM, Not HIGH
- SSO backend is proven and stable (won't touch it)
- No database migrations required
- Frontend changes are isolated
- Can test thoroughly before production
- Rollback is straightforward

---

## Phase 0: Governance, Protocol Alignment, and Reviews (REQUIRED)

Time Estimate: 2–3 hours  
Risk: LOW  
Priority: MUST DO

- Protocol alignment: MEDIUM RISK normally requires 1–2 week parallel operation. Since PrimeTrade has no prior working production version, we will run a modified protocol (5–6 day soft launch) and document the deviation.
- Document deviation: Add FRAMEWORK_SKIPS.md with rationale, risk assessment, and approval (see template below).
- Checklist: Complete DEPLOYMENT_CHECKLIST_MEDIUM.md (use org template) before Day 0.
- Three-Perspective Review (sign-off required before deploy):
  - Security: SSO untouched, CSRF on POSTs, HTTPS, secure cookies, no secrets in code, auth on all endpoints, emergency login SOP.
  - Data Safety: No migrations, read/write paths verified (BOL create, customers/carriers), input validation, rollback plan.
  - Business Logic: Role gating via application_roles['primetrade'], core workflows (login → dashboard → create BOL) verified.
- Staff training: 15–20 min brief covering login steps, emergency login URL, and how to report issues.
- Approval: Clif selects Option B (Modified MEDIUM) and signs Approval section.

## Phase 1: Frontend Authentication Fix (CRITICAL)

**Time Estimate:** 2-3 hours  
**Risk:** MEDIUM  
**Priority:** MUST DO

### Task 1.1: Add Django Session Auth Endpoint

**Create:** `/api/auth/me/`

```python
# bol_system/views.py additions

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """
    Return current authenticated user info.
    
    Used by frontend to display user information after SSO login.
    Requires Django session authentication.
    """
    user = request.user
    
    # Get SSO role from session if available
    primetrade_role = request.session.get('primetrade_role', {})
    
    return Response({
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_authenticated': True,
        'role': primetrade_role.get('role', 'user'),
        'permissions': primetrade_role.get('permissions', [])
    })
```

**Add to URLs:**
```python
# bol_system/urls.py
path('auth/me/', views.current_user, name='current-user'),
```

### Task 1.2: Replace Frontend Auth Module

**File:** `static/js/auth.js`

**Remove:** All Firebase code (lines 78-196)

**Replace with:**
```javascript
/**
 * Django Session Authentication Module
 * Works with SSO OAuth backend using Django sessions
 */

const Auth = (function() {
  'use strict';
  
  // Get CSRF token from cookies
  function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'csrftoken') {
        return value;
      }
    }
    return null;
  }
  
  // Check if user is authenticated (session-based)
  async function isAuthenticated() {
    try {
      const response = await fetch('/api/auth/me/', {
        credentials: 'same-origin'
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  }
  
  // Get current user info
  async function getCurrentUser() {
    try {
      const response = await fetch('/api/auth/me/', {
        credentials: 'same-origin'
      });
      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error('Error fetching user:', error);
      return null;
    }
  }
  
  // Get user email
  async function getUserEmail() {
    const user = await getCurrentUser();
    return user ? user.email : '';
  }
  
  // Logout user
  function logout() {
    window.location.href = '/auth/logout/';
  }
  
  // Redirect to login if not authenticated
  async function requireAuth(redirectUrl = null) {
    const authenticated = await isAuthenticated();
    if (!authenticated) {
      const redirect = redirectUrl || window.location.href;
      window.location.href = '/login/?next=' + encodeURIComponent(redirect);
      return false;
    }
    return true;
  }
  
  // Initialize auth UI elements
  async function initAuthUI() {
    const user = await getCurrentUser();
    if (user) {
      const userEmailElement = document.getElementById('userEmail');
      if (userEmailElement) {
        userEmailElement.textContent = user.email;
      }
      
      const usernameDisplay = document.getElementById('usernameDisplay');
      if (usernameDisplay) {
        usernameDisplay.textContent = `Welcome, ${user.username}`;
      }
    }
    
    // Set up logout buttons
    const logoutButtons = document.querySelectorAll('[onclick*="logout"]');
    logoutButtons.forEach(button => {
      button.onclick = (e) => {
        e.preventDefault();
        logout();
      };
    });
  }
  
  // Handle authentication error (redirect to login)
  function handleAuthError() {
    window.location.href = '/login/?next=' + encodeURIComponent(window.location.href);
  }
  
  // Public API
  return {
    isAuthenticated,
    getCurrentUser,
    getUserEmail,
    getCsrfToken,
    logout,
    requireAuth,
    initAuthUI,
    handleAuthError
  };
})();

// Make logout globally available
window.logout = Auth.logout;
```

### Task 1.3: Update API Module

**File:** `static/js/api.js`

**Changes:**
1. Remove Bearer token headers
2. Add CSRF token to POST/PUT/DELETE requests
3. Use credentials: 'same-origin' for session cookies

```javascript
// BASE API request function (updated)
async function request(url, options = {}) {
  const defaultOptions = {
    credentials: 'same-origin',  // Include session cookies
    headers: {
      'Content-Type': 'application/json',
    }
  };
  
  // Add CSRF token for non-GET requests
  if (options.method && options.method !== 'GET') {
    const csrfToken = Auth.getCsrfToken();
    if (csrfToken) {
      defaultOptions.headers['X-CSRFToken'] = csrfToken;
    }
  }
  
  const finalOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...(options.headers || {})
    }
  };
  
  const response = await fetch(url, finalOptions);
  
  // Handle authentication errors (redirect to login)
  if (response.status === 401 || response.status === 403) {
    Auth.handleAuthError();
    return;
  }
  
  // Handle other errors
  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || `Request failed: ${response.status}`);
  }
  
  // Parse JSON response
  try {
    return await response.json();
  } catch (e) {
    return response.text();
  }
}
```

### Task 1.4: Update Index Page

**File:** `static/index.html`

**Lines 88-96:** Update user loading

```javascript
// Load current user info (updated)
try {
  const user = await Auth.getCurrentUser();
  if (user && user.username) {
    qs("usernameDisplay").textContent = `Welcome, ${user.username}`;
  } else {
    // Not logged in - redirect
    Auth.requireAuth();
  }
} catch (e) {
  console.log("Could not load user info:", e);
  Auth.requireAuth();
}
```

### Task 1.5: Quarantine Firebase Artifacts (no code deletion)

To preserve history and comply with security standards while avoiding confusion:
- Move legacy Firebase-related files to `docs/legacy/` (e.g., `static/js/firebase-config.js`, any Firebase SDK references).
- Remove all Firebase script tags/imports from HTML files.
- Note the quarantine in CHANGELOG/commit message.

---

## Phase 2: Testing (REQUIRED)

**Time Estimate:** 1 hour  
**Risk:** LOW  
**Priority:** MUST DO

### Test 2.1: Local SSO Login Flow

**Steps:**
```bash
# Start SSO (if not already running)
cd /Users/cerion/Projects/barge2rail-auth
source .venv/bin/activate
python manage.py runserver 8000

# Start PrimeTrade
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate
python manage.py runserver 8001

# Test in browser
```

**Test Checklist:**
- [ ] Visit http://127.0.0.1:8001/
- [ ] Auto-redirects to SSO login
- [ ] Can authenticate via SSO (Google or password)
- [ ] Redirects back to PrimeTrade
- [ ] Dashboard loads with user info displayed
- [ ] Can access products page
- [ ] Can access customers page
- [ ] Can create a BOL (preview and confirm)
- [ ] Logout works correctly

### Test 2.2: Session Persistence

**Test:**
- [ ] Login successfully
- [ ] Close browser
- [ ] Reopen browser to http://127.0.0.1:8001/
- [ ] Should still be logged in (session persists)

### Test 2.3: Role Authorization

**Test:**
- [ ] Login with user that has `primetrade` role → Success
- [ ] Try accessing /api/products/ → Returns data
- [ ] Logout
- [ ] Try accessing /api/products/ without login → Redirects to login

### Test 2.4: API Calls with CSRF

**Test:**
- [ ] Login successfully
- [ ] Create a customer (POST request) → Success
- [ ] Create a carrier (POST request) → Success
- [ ] Preview BOL (POST request) → Success
- [ ] Confirm BOL (POST request) → Success

**Expected:** All POST requests succeed (CSRF token sent correctly)

### Test 2.5: Coverage ≥ 70% (MEDIUM RISK requirement)

BLOCKER: Deployment cannot proceed if coverage < 70%

Run tests with coverage and enforce threshold:

```bash
pytest --maxfail=1 --disable-warnings -q
pytest --cov --cov-report=term --cov-fail-under=70
```

- Record coverage % in deployment PR and DEPLOYMENT_CHECKLIST_MEDIUM.md.
- If <70%: Add tests for auth flow and BOL creation BEFORE proceeding to Phase 4.
- Do not proceed to production configuration until this passes.

---

## Phase 3: Code Quality & Security (RECOMMENDED)

**Time Estimate:** 1 hour  
**Risk:** LOW  
**Priority:** SHOULD DO

### Task 3.1: Add Basic Tests

**Create:** `bol_system/test_auth.py`

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User


class AuthenticationTests(TestCase):
    """Test authentication and authorization."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_unauthenticated_redirects_to_login(self):
        """Verify unauthenticated users redirect to login."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_authenticated_user_can_access_home(self):
        """Verify authenticated users can access home."""
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_api_requires_authentication(self):
        """Verify API endpoints require authentication."""
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 403)
    
    def test_current_user_endpoint(self):
        """Verify /api/auth/me/ returns user info."""
        self.client.force_login(self.user)
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['email'], 'test@example.com')
        self.assertTrue(data['is_authenticated'])


class CSRFTests(TestCase):
    """Test CSRF protection."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_post_requires_csrf_token(self):
        """Verify POST requests require CSRF token."""
        self.client.force_login(self.user)
        
        # Without CSRF token - should fail
        response = self.client.post('/api/products/', 
            {'name': 'Test Product', 'start_tons': 100},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
```

**Run tests:**
```bash
python manage.py test bol_system.test_auth
```

### Task 3.2: Security Audit

**Checklist:**
- [ ] All secrets in environment variables (not code)
- [ ] CSRF protection enabled for POST/PUT/DELETE
- [ ] Session cookies use secure flags in production
- [ ] HTTPS enforced in production (settings.py)
- [ ] Authentication required on all sensitive endpoints
- [ ] No SQL injection risks (using ORM)
- [ ] Input validation on user data
- [ ] Proper error messages (don't expose internals)

### Task 3.3: Remove Debug Logging

**File:** `primetrade_project/auth_views.py`

**Change:** All `logger.error(f"[FLOW DEBUG...]")` → `logger.debug(f"...")`

**Reason:** Debug logs should use DEBUG level, not ERROR

```python
# Before
logger.error(f"[FLOW DEBUG 1] State validation result...")

# After
logger.debug(f"State validation result...")
```

---

## Phase 4: Production Configuration (REQUIRED)

**Time Estimate:** 30 minutes  
**Risk:** LOW  
**Priority:** MUST DO

### Task 4.1: Update Environment Variables

**Production .env (set in Render dashboard):**

```bash
# Django Settings
SECRET_KEY=[generate new key]
DEBUG=False
ALLOWED_HOSTS=primetrade-u2a6.onrender.com,prt.barge2rail.com

# Database
DATABASE_URL=[from Render PostgreSQL]

# SSO Configuration
SSO_BASE_URL=https://sso.barge2rail.com
SSO_CLIENT_ID=app_0b97b7b94d192797
SSO_CLIENT_SECRET=[same as current]
SSO_REDIRECT_URI=https://primetrade-u2a6.onrender.com/auth/callback/
SSO_SCOPES=openid email profile
```

**Generate new SECRET_KEY:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Task 4.2: Update SSO Redirect URI

**In SSO Admin Panel:**
1. Login to https://sso.barge2rail.com/admin
2. Navigate to Applications → PrimeTrade
3. Add redirect URI: `https://primetrade-u2a6.onrender.com/auth/callback/`
4. Save

### Task 4.3: Update CSRF Trusted Origins

**File:** `primetrade_project/settings.py`

**Lines 204-209:** Already configured correctly ✅

```python
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        'https://prt.barge2rail.com',
        'https://primetrade-u2a6.onrender.com',
        'https://sso.barge2rail.com'
    ]
```

### Task 4.4: Verify render.yaml

**File:** `render.yaml`

**Check:** Already properly configured ✅

---

## Phase 5: Deployment (REQUIRED)

**Time Estimate:** 30 minutes  
**Risk:** MEDIUM  
**Priority:** MUST DO

### Task 5.1: Commit Changes

```bash
cd /Users/cerion/Projects/django-primetrade

# Add all changes
git add .

# Commit with conventional message
git commit -m "fix: replace Firebase auth with Django session auth for SSO

- Add /api/auth/me/ endpoint for current user info
- Replace Firebase auth.js with Django session-based auth
- Update API module to use CSRF tokens and session cookies
- Remove Bearer token authentication
- Add authentication tests
- Update debug logging to use logger.debug()

Fixes #[issue-number]
Risk: MEDIUM (32/60)
Protocol: MEDIUM RISK DEPLOYMENT"

# Push to GitHub
git push origin main
```

### Task 5.2: Deploy to Render

**If connected to GitHub (automatic):**
1. Push triggers automatic deploy
2. Monitor build logs in Render dashboard
3. Wait for health check to pass

**If manual deploy:**
1. Login to Render dashboard
2. Select primetrade service
3. Click "Manual Deploy" → "Deploy latest commit"
4. Monitor build logs

### Task 5.3: Post-Deployment Verification

**Wait for:** Health check passing at `/api/health/`

**Test Checklist:**
- [ ] Visit https://primetrade-u2a6.onrender.com
- [ ] Auto-redirects to SSO login
- [ ] Login with SSO account that has primetrade role
- [ ] Redirects back to PrimeTrade
- [ ] Dashboard loads with user info
- [ ] Can navigate to products, customers, carriers
- [ ] Can create a BOL
- [ ] Can view BOL history
- [ ] Logout works
- [ ] Can log back in successfully

### Task 5.4: Monitor for Issues

**Check:**
- [ ] Render logs for errors
- [ ] SSO logs for failed authentications
- [ ] Database connections stable
- [ ] No 500 errors in first hour
- [ ] Session cookies working across requests

---

## Soft Launch & Monitoring (Days 1–5) (REQUIRED for Modified MEDIUM)

Timeframe: 5 days post-deploy  
Scope: Internal cohort → broader users

### Daily Verification Checklist (run each day)
- Login via SSO (multiple users) succeeds
- Session persists across navigation and browser restart
- CSRF-protected POSTs work: create carrier, preview BOL, confirm BOL
- Role gating enforced: non-primetrade role gets 403
- No 500s in logs; error rate within acceptable range
- PDF generation works or degrades gracefully

### Monitoring & Alerts
- Review Render logs and `logs/primetrade.log` daily
- Watch SSO logs for callback/token errors
- Track 401/403 spikes, CSRF failures
- Define rollback triggers: repeated auth/csrf failures, >1% error rate, or critical workflow failure

### Rollout Plan
- Days 1–2: Internal users only (office staff); collect feedback
- Days 3–4: Expand to small external cohort
- Day 5: Go/No-Go for full production traffic (business sign-off)

### Internal Test Cohort (Days 1–2)
- clif@barge2rail.com — Primary BOL creator (test full workflow)
- clif@barge2rail.com — Admin user (test all permissions)
- clif@barge2rail.com — View-only user (test read access)

## Phase 6: Documentation (SHOULD DO)

**Time Estimate:** 30 minutes  
**Risk:** LOW  
**Priority:** SHOULD DO

### Task 6.1: Update README

**Add section:** "Authentication"

```markdown
## Authentication

PrimeTrade uses SSO authentication via sso.barge2rail.com.

### How It Works

1. User visits PrimeTrade
2. Redirects to SSO for authentication
3. User authenticates (Google OAuth or password)
4. SSO redirects back with authorization code
5. PrimeTrade exchanges code for tokens
6. User logged in with Django session

### Requirements

- User must have `primetrade` application role in SSO
- Contact admin to request access

### Development

```bash
# Ensure SSO is running on port 8000
cd /path/to/barge2rail-auth
python manage.py runserver 8000

# Run PrimeTrade on port 8001
cd /path/to/django-primetrade
python manage.py runserver 8001

# Visit http://127.0.0.1:8001
```

### Production

Production uses session-based authentication with Django.
No client-side tokens or Firebase required.
```

### Task 6.2: Create Post-Mortem Document

**Create:** `docs/POST_MORTEM_FRONTEND_AUTH.md`

Document the frontend/backend mismatch issue and resolution for future reference.

---

## Rollback Plan

### If Frontend Auth Breaks

**Symptoms:**
- Can't access app after SSO login
- API calls fail with 403
- CSRF errors

**Rollback Steps:**
```bash
# Revert to previous commit
cd /Users/cerion/Projects/django-primetrade
git log --oneline -5  # Find last working commit
git revert [commit-hash]
git push origin main

# OR restore from backup
cp static/js/auth.js.backup static/js/auth.js
git commit -am "revert: restore previous auth.js"
git push origin main
```

### If SSO Integration Breaks

**Symptoms:**
- Can't redirect to SSO
- Token exchange fails
- 403 on callback

**Rollback Steps:**
1. Check SSO redirect URI in admin panel
2. Verify SSO_CLIENT_ID and SSO_CLIENT_SECRET in env vars
3. Check SSO server logs
4. Verify auth_views.py not modified (we're NOT changing it)

### Emergency Access SOP
**URL:** `/emergency-local-login/`
**Credentials:** Django superuser account (Clif only)
**When to Use:** SSO completely broken AND immediate access is required (not for routine use)
**Process:**
1. Visit emergency URL
2. Login with superuser credentials
3. Fix configuration issue
4. Test SSO flow
5. Logout of emergency session
**Security:** Disable or restrict this route after resolution (e.g., comment out route or IP-restrict) and log all emergency logins.

---

## Success Criteria

### Must Have (Go/No-Go)
- [ ] ✅ Can login via SSO
- [ ] ✅ Dashboard displays after login
- [ ] ✅ Can access all pages (products, customers, carriers)
- [ ] ✅ Can create BOLs
- [ ] ✅ API calls work with CSRF
- [ ] ✅ Logout works correctly
- [ ] ✅ No console errors
- [ ] ✅ No 500 errors in logs

### Should Have (Monitor Post-Deploy)
- [ ] Session persists across browser restart
- [ ] Role authorization working
- [ ] Tests passing
- [ ] Metrics within targets

### Nice to Have (Future Improvements)
- [ ] Token refresh logic
- [ ] Remember me functionality
- [ ] Activity logging
- [ ] User profile page

---

## Timeline (Modified MEDIUM Protocol)

- Day -1: Phase 0 (Governance, reviews, checklist, approval)
- Day 0: Deploy to production (Phase 5) after Phase 1–4 complete
- Days 1–2: Soft launch to internal cohort; daily verification + monitoring
- Days 3–4: Expand cohort; continue daily checks; address feedback
- Day 5: Go/No-Go decision for full rollout (Business sign-off)
- Week 1: Post-deploy monitoring and clean-up

---

## Post-Deployment

### Week 1: Monitor
- [ ] Check error logs daily
- [ ] Monitor user feedback
- [ ] Track authentication failures
- [ ] Verify session stability

### Week 2: Optimize
- [ ] Add performance metrics
- [ ] Implement token refresh
- [ ] Add audit logging
- [ ] Improve error messages

### Month 1: Enhance
- [ ] Add user preferences
- [ ] Implement remember me
- [ ] Create admin dashboard
- [ ] Add usage analytics

---

## Conventions Compliance

### Per BARGE2RAIL_CODING_CONVENTIONS_v1.2.md

**✅ Security Standards (REQUIRED):**
- All secrets in environment variables
- Authentication required on all endpoints
- CSRF protection enabled
- HTTPS enforced in production
- Using Django ORM (no SQL injection)

**✅ Code Quality:**
- Docstrings on all new functions
- Proper error handling
- Logging at appropriate levels
- Meaningful variable names

**✅ Testing:**
- MEDIUM RISK requires ≥70% coverage
- Tests added for authentication flow
- Manual testing completed

**✅ Git Workflow:**
- Conventional commit messages
- PR includes risk assessment
- Security checklist completed

**✅ Deployment:**
- Modified MEDIUM protocol followed (documented deviation)
- DEPLOYMENT_CHECKLIST_MEDIUM.md completed
- Rollback plan documented

---

## Approval Required

**Deployment Approval:** Clif (Business Owner)

**Option Selection:**
- [x] Option B – Modified MEDIUM protocol (5–6 day soft launch)  
  Justification: First-time launch (no prior prod), low technical risk (frontend session-auth replacement), high user impact warrants measured rollout.

**Checklist Before Approval:**
- [ ] Three-Perspective Review signed (Security, Data, Business)
- [ ] DEPLOYMENT_CHECKLIST_MEDIUM.md completed
- [ ] Coverage ≥ 70% recorded
- [ ] Rollback plan documented
- [ ] Success criteria defined
- [ ] FRAMEWORK_SKIPS.md drafted (see template below)

**Approval Signature:**
```
Approved by: ________________
Date: ________________
Risk Level Confirmed: MEDIUM (32/60) – Modified Protocol
```

### FRAMEWORK_SKIPS.md (to add at repo root)

```markdown
# FRAMEWORK_SKIPS

## Deviation: MEDIUM RISK parallel operation shortened to 5–6 day soft launch
- Project: django-primetrade
- Date: 2025-10-29
- Convention Reference: BARGE2RAIL_CODING_CONVENTIONS_v1.2.md (Deployment Standards → Environment Tiers / Deployment Checklist)
- Reason: First-time production launch; no existing working system to run in parallel. Technical change is frontend-only (session auth), SSO backend unchanged.
- Risk Mitigations:
  - Three-Perspective Review before deploy
  - Coverage ≥ 70%
  - Intensive daily verification Days 1–5
  - Defined rollback triggers and emergency login SOP
- Approval: Clif (Business Owner)
```

---

## Execution

**Ready to execute?**

```bash
# Start here:
cd /Users/cerion/Projects/django-primetrade

# Follow Phase 1, Task 1.1...
```

**Questions or issues during execution?**
1. Check rollback plan
2. Review conventions document
3. Test in local environment first
4. Escalate to Clif if blocked
