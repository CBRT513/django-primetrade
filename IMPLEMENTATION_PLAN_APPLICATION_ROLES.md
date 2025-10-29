# PrimeTrade SSO Authorization Fix - Implementation Plan

**Date:** October 28, 2025  
**Project:** django-primetrade  
**Risk Level:** MEDIUM RISK (26/60) - modifying authentication/authorization  
**Assigned To:** Claude Code  
**Conventions:** Follow BARGE2RAIL_CODING_CONVENTIONS_v1.2.md

---

## Context

**Current State:**
- PrimeTrade successfully redirects to SSO for authentication
- SSO OAuth endpoints working (`/o/authorize/`, `/o/token/`)
- User authenticates via Google OAuth through SSO
- **PROBLEM:** Authorization fails because PrimeTrade checks `is_sso_admin` flag instead of application-specific roles

**Goal:**
- Implement proper application-specific authorization using SSO's `ApplicationRole` model
- Users must have `primetrade` application role to access PrimeTrade
- Maintain backward compatibility with existing SSO integrations

---

## Architecture Overview

**SSO System (barge2rail-auth):**
- Has `ApplicationRole` model that grants per-application permissions
- Custom OAuth validator includes application roles in JWT tokens
- JWT tokens should contain `application_roles` claim with structure:
  ```json
  {
    "application_roles": {
      "primetrade": {
        "role": "admin",
        "permissions": ["full_access"]
      }
    }
  }
  ```

**PrimeTrade (django-primetrade):**
- Currently checks `is_sso_admin` in JWT (line 283-286 of auth_views.py)
- Needs to check `application_roles['primetrade']` instead
- Must gracefully handle users without PrimeTrade access

---

## Prerequisites (Already Completed)

- ✅ SSO OAuth application exists: client_id=`primetrade_client`
- ✅ PrimeTrade .env configured with correct credentials
- ✅ OAuth redirect loop fixed (LOGIN_URL points to `/auth/login/`)
- ✅ OAuth endpoints corrected (`/o/authorize/` and `/o/token/`)

---

## Implementation Tasks

### Task 0: Pre-Flight Checks (REQUIRED - DO NOT SKIP)

**Purpose:** Verify prerequisites before making any code changes. Catches configuration issues early.

**Time Estimate:** 5 minutes

**Run these checks in order:**

#### Check 1: Verify SSO Application Exists

```bash
cd /Users/cerion/Projects/barge2rail-auth
source .venv/bin/activate
python manage.py shell
```

```python
from sso.models import Application

# Check if PrimeTrade application exists
try:
    app = Application.objects.get(slug='primetrade')
    print(f"✅ PrimeTrade application exists")
    print(f"   Slug: {app.slug}")
    print(f"   Name: {app.name}")
    print(f"   Client ID: {app.client_id}")
except Application.DoesNotExist:
    print("❌ ERROR: PrimeTrade application not found!")
    print("   Create it first in SSO admin before proceeding.")
    exit()

exit()
```

**Expected Output:**
```
✅ PrimeTrade application exists
   Slug: primetrade
   Name: PrimeTrade
   Client ID: primetrade_client
```

**If fails:** Create Application in SSO admin panel first.

---

#### Check 2: Verify ApplicationRole Model Exists

```bash
python manage.py shell
```

```python
from sso.models import ApplicationRole

# Check model is accessible
print(f"✅ ApplicationRole model exists")
print(f"   Total roles in system: {ApplicationRole.objects.count()}")

# Check if any user has primetrade role
app = Application.objects.get(slug='primetrade')
primetrade_roles = ApplicationRole.objects.filter(application=app)
print(f"   Users with PrimeTrade access: {primetrade_roles.count()}")

if primetrade_roles.exists():
    for role in primetrade_roles:
        print(f"     - {role.user.email}: {role.role}")

exit()
```

**Expected Output:**
```
✅ ApplicationRole model exists
   Total roles in system: X
   Users with PrimeTrade access: 0 or more
```

---

#### Check 3: Verify Both Servers Can Start

**SSO Server:**
```bash
cd /Users/cerion/Projects/barge2rail-auth
source .venv/bin/activate
python manage.py check --deploy
```

**Expected:** `System check identified no issues (0 silenced).`

**PrimeTrade Server:**
```bash
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate
python manage.py check --deploy
```

**Expected:** `System check identified no issues (0 silenced).`

---

#### Check 4: Verify OAuth Configuration

```bash
cd /Users/cerion/Projects/django-primetrade
cat .env | grep SSO
```

**Expected Output:**
```
SSO_URL=http://127.0.0.1:8000
SSO_CLIENT_ID=primetrade_client
SSO_CLIENT_SECRET=[some_secret]
```

**Verify values match:**
- `SSO_CLIENT_ID` matches Application's `client_id` from Check 1
- `SSO_URL` points to correct SSO server (port 8000)

---

#### Check 5: Verify Database Connectivity

**SSO Database:**
```bash
cd /Users/cerion/Projects/barge2rail-auth
source .venv/bin/activate
python manage.py dbshell
```

```sql
SELECT COUNT(*) FROM sso_application WHERE slug='primetrade';
-- Should return: 1
\q
```

**PrimeTrade Database:**
```bash
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate
python manage.py dbshell
```

```sql
SELECT COUNT(*) FROM django_session;
-- Should return: any number (confirms DB works)
\q
```

---

### Pre-Flight Checklist

Before proceeding to Task 1, confirm:

- [ ] ✅ PrimeTrade Application exists in SSO with slug='primetrade'
- [ ] ✅ ApplicationRole model accessible and queryable
- [ ] ✅ Both servers pass `manage.py check --deploy`
- [ ] ✅ PrimeTrade .env has correct SSO_CLIENT_ID
- [ ] ✅ Both databases accessible via dbshell

**If ANY check fails → STOP and fix before proceeding.**

**If ALL checks pass → Proceed to Task 1.**

---

### Task 1: Update SSO to Include ApplicationRoles in JWT

**File:** `/Users/cerion/Projects/barge2rail-auth/sso/oauth_validators.py`

**Location:** `get_additional_claims()` method (lines 141-175)

**Current Code:**
```python
def get_additional_claims(self, request):
    """Add custom claims to the ID token (for OpenID Connect)."""
    claims = {}
    
    if hasattr(request, "user") and request.user:
        user = request.user
        
        # Add user profile information
        claims.update({
            "email": user.email,
            "email_verified": bool(user.email),
            "name": user.display_name or user.get_full_name(),
            "preferred_username": user.username,
        })
        
        # Add SSO admin flag
        claims["is_sso_admin"] = user.is_sso_admin
        
        # Add role information if available (currently per-client, not per-application)
        if hasattr(request, "client") and request.client:
            try:
                role = UserRole.objects.get(user=user, application=request.client)
                claims["role"] = role.role
                claims["permissions"] = role.permissions
            except UserRole.DoesNotExist:
                pass
    
    return claims
```

**Required Changes:**
1. Import `ApplicationRole` model at top of file
2. Add `application_roles` claim that includes ALL applications user has access to
3. Keep `is_sso_admin` for backward compatibility
4. Structure: `{"application_roles": {"app_slug": {"role": "admin", "permissions": [...]}}}`

**Updated Code:**
```python
def get_additional_claims(self, request):
    """
    Add custom claims to the ID token (for OpenID Connect).
    
    Includes user profile and application-specific roles for multi-app authorization.
    """
    claims = {}
    
    if hasattr(request, "user") and request.user:
        user = request.user
        
        # Add user profile information
        claims.update({
            "email": user.email,
            "email_verified": bool(user.email),
            "name": user.display_name or user.get_full_name(),
            "preferred_username": user.username,
        })
        
        # Add SSO admin flag (backward compatibility)
        claims["is_sso_admin"] = user.is_sso_admin
        
        # Add application-specific roles for all apps user has access to
        from sso.models import ApplicationRole
        app_roles = ApplicationRole.objects.filter(user=user).select_related('application')
        
        claims["application_roles"] = {}
        for app_role in app_roles:
            if app_role.application and app_role.application.slug:
                claims["application_roles"][app_role.application.slug] = {
                    "role": app_role.role,
                    "permissions": app_role.permissions or []
                }
        
        logger.debug(f"Added application_roles for {user.email}: {list(claims['application_roles'].keys())}")
    
    return claims
```

**Testing:**
- Decode JWT after change to verify `application_roles` claim exists
- Check logs for "Added application_roles" message

---

### Task 2: Update PrimeTrade to Check ApplicationRoles

**File:** `/Users/cerion/Projects/django-primetrade/primetrade_project/auth_views.py`

**Location:** Lines 279-293 (authorization check in `sso_callback` view)

**Current Code:**
```python
# Check for primetrade role in application_roles claim
application_roles = decoded.get("application_roles", {})
primetrade_role = application_roles.get("primetrade")

if not primetrade_role:
    logger.warning(f"User {email} lacks PrimeTrade application role. Available apps: {list(application_roles.keys())}")
    logger.error(f"[FLOW DEBUG 7.5] User lacks PrimeTrade role - returning 403")
    return HttpResponseForbidden("You don't have access to PrimeTrade. Contact admin.")

# Extract role details for session storage
role_name = primetrade_role.get("role")
permissions = primetrade_role.get("permissions", [])
```

**Status:** ✅ Already correct! Code checks `application_roles['primetrade']`

**Verification Needed:**
- Confirm this code matches SSO's application slug (`primetrade` not `PrimeTrade`)
- Add logging to show what `application_roles` contains when empty

**Enhanced Code (add better error handling):**
```python
# Check for primetrade role in application_roles claim
application_roles = decoded.get("application_roles", {})

logger.error(f"[FLOW DEBUG 7.4] Full application_roles claim: {application_roles}")

primetrade_role = application_roles.get("primetrade")

if not primetrade_role:
    available_apps = list(application_roles.keys()) if application_roles else "none"
    logger.warning(f"User {email} lacks PrimeTrade application role. Available apps: {available_apps}")
    logger.error(f"[FLOW DEBUG 7.5] User lacks PrimeTrade role - returning 403")
    
    return HttpResponseForbidden(
        "You don't have access to PrimeTrade. Contact admin to request access. "
        f"Your current applications: {', '.join(available_apps) if available_apps != 'none' else 'none'}"
    )

# Extract role details for session storage
role_name = primetrade_role.get("role")
permissions = primetrade_role.get("permissions", [])

logger.info(f"User {email} authenticated with PrimeTrade role: {role_name}")
logger.error(f"[FLOW DEBUG 8] Role check PASSED - role: {role_name}, permissions: {permissions}")
```

---

### Task 3: Grant PrimeTrade Role to Test User

**Run in SSO project:**

```bash
cd /Users/cerion/Projects/barge2rail-auth
source .venv/bin/activate
python manage.py shell
```

**Python commands:**
```python
from sso.models import User, Application, ApplicationRole

# Get your user
user = User.objects.get(email='clif@barge2rail.com')  # Replace with actual email

# Get PrimeTrade application
app = Application.objects.get(slug='primetrade')

# Create or update ApplicationRole
role, created = ApplicationRole.objects.get_or_create(
    user=user,
    application=app,
    defaults={
        'role': 'admin',
        'permissions': ['full_access']
    }
)

if created:
    print(f"✅ Granted PrimeTrade admin role to {user.email}")
else:
    print(f"ℹ️  {user.email} already has PrimeTrade role: {role.role}")
    # Update if needed
    role.role = 'admin'
    role.permissions = ['full_access']
    role.save()
    print(f"✅ Updated role to admin")

exit()
```

---

### Task 4: Restart Both Servers

**SSO (port 8000):**
```bash
pkill -f "manage.py runserver 8000"
cd /Users/cerion/Projects/barge2rail-auth
source .venv/bin/activate
python manage.py runserver 8000
```

**PrimeTrade (port 8001):**
```bash
pkill -f "manage.py runserver 8001"
cd /Users/cerion/Projects/django-primetrade
source venv/bin/activate
python manage.py runserver 8001
```

---

### Task 5: Test the Integration

**Test Flow:**
1. Clear browser cache/cookies (or use new incognito window)
2. Visit: http://127.0.0.1:8001/
3. Should redirect to SSO login
4. Login with Google
5. Should redirect back to PrimeTrade
6. **Expected:** Successfully logged in and see home page

**Check Logs:**

**SSO logs (look for):**
```
Added application_roles for user@email.com: ['primetrade']
```

**PrimeTrade logs (look for):**
```
[FLOW DEBUG 7.4] Full application_roles claim: {'primetrade': {'role': 'admin', 'permissions': ['full_access']}}
[FLOW DEBUG 8] Role check PASSED - role: admin, permissions: ['full_access']
User user@email.com authenticated with PrimeTrade role: admin
```

**If access denied:**
- Check `[FLOW DEBUG 7.4]` to see what `application_roles` contains
- Verify ApplicationRole exists in SSO database
- Check SSO logs for "Added application_roles" message

---

## Success Criteria

- ✅ SSO JWT tokens include `application_roles` claim
- ✅ PrimeTrade checks `application_roles['primetrade']` not `is_sso_admin`
- ✅ Test user has PrimeTrade ApplicationRole in SSO database
- ✅ User can successfully login to PrimeTrade
- ✅ Users without PrimeTrade role get clear error message
- ✅ Backward compatibility maintained (other apps still work)

---

## Rollback Plan

If something breaks:

1. **Revert SSO changes:**
   ```bash
   cd /Users/cerion/Projects/barge2rail-auth
   git checkout sso/oauth_validators.py
   pkill -f "manage.py runserver 8000"
   python manage.py runserver 8000
   ```

2. **Revert PrimeTrade changes:**
   ```bash
   cd /Users/cerion/Projects/django-primetrade
   git checkout primetrade_project/auth_views.py
   pkill -f "manage.py runserver 8001"
   python manage.py runserver 8001
   ```

3. **Emergency access:** Use emergency_admin account in SSO admin

---

## Coding Conventions (REQUIRED)

**IMPORTANT:** All code changes MUST follow BARGE2RAIL_CODING_CONVENTIONS_v1.2.md

**Key requirements:**
- ✅ Docstrings on all modified functions
- ✅ Error handling with specific exceptions (no bare `except:`)
- ✅ Logging at appropriate levels (INFO for success, WARNING for issues, ERROR for failures)
- ✅ Input validation on user data
- ✅ Meaningful variable names
- ✅ Comments explaining WHY not just WHAT
- ✅ Follow existing code style (4-space indentation, etc.)

**Security checklist:**
- ✅ No secrets in code
- ✅ Authentication required (already implemented)
- ✅ Authorization checks before granting access
- ✅ User-friendly error messages (don't expose internals)
- ✅ Logging for audit trail

---

## Notes for Claude Code

1. **Test each change incrementally** - don't modify both projects at once
2. **Check logs frequently** - they show exactly what's happening
3. **ApplicationRole model uses application.slug** not application.name
4. **JWT decoding** - Use `jwt.decode(token, options={"verify_signature": False})` for debugging
5. **Session clearing** - If testing multiple times, clear Django sessions between tests

---

## Timeline Estimate

- Task 0 (Pre-flight checks): 5 minutes
- Task 1 (SSO JWT update): 10 minutes
- Task 2 (PrimeTrade auth check): 5 minutes (mostly done)
- Task 3 (Grant role): 5 minutes
- Task 4 (Restart servers): 2 minutes
- Task 5 (Testing): 10 minutes
- **Total:** ~35 minutes

---

## Questions to Ask Before Starting

1. What email address should get PrimeTrade access?
2. Should we keep `is_sso_admin` check as fallback?
3. Do we want role-based features (admin vs user) or just access control?

---

**Ready to implement? Start with Task 0 (Pre-Flight Checks) and work sequentially.**
