# PrimeTrade Production Gaps

**Project:** django-primetrade (Bill of Lading Management System)
**Date:** November 2, 2025
**Author:** Claude Code (Production Diagnostic)
**Purpose:** Prioritized roadmap to production readiness

---

## Executive Summary

**Current Status:** 57.5% production-ready (23/40 features implemented)
**Primary Blocker:** Admin bypass security issue + undefined client interface requirements
**Test Coverage:** 16% (target 70% for MEDIUM RISK protocol)
**Estimated Work to Production:** 168-250 hours (4-6 weeks for 1 developer)

**Risk Assessment:** MEDIUM RISK (~26/60) - per barge2rail.com RISK_CALCULATOR.md
**Deployment Protocol:** Requires 70% test coverage before production launch

---

## Table of Contents

1. [Gap Overview Dashboard](#gap-overview-dashboard)
2. [Priority 0: Production Blockers](#priority-0-production-blockers)
3. [Priority 1: High Priority](#priority-1-high-priority)
4. [Priority 2: Medium Priority](#priority-2-medium-priority)
5. [Priority 3: Low Priority (Post-Launch)](#priority-3-low-priority-post-launch)
6. [Testing Gaps](#testing-gaps)
7. [Code Quality Gaps](#code-quality-gaps)
8. [Security Gaps](#security-gaps)
9. [Documentation Gaps](#documentation-gaps)
10. [Deployment Checklist](#deployment-checklist)
11. [Timeline & Milestones](#timeline--milestones)

---

## Gap Overview Dashboard

### By Priority

| Priority | Count | Total Effort | Status | Blocking Production? |
|----------|-------|--------------|--------|---------------------|
| **P0 - Blocking** | 7 items | 80-120 hours | ❌ Not Started | YES |
| **P1 - High** | 6 items | 36-54 hours | ❌ Not Started | Recommended |
| **P2 - Medium** | 8 items | 32-48 hours | ❌ Not Started | No |
| **P3 - Low** | 6 items | 52-76 hours | ❌ Not Started | No |
| **TOTAL** | **27 items** | **200-298 hours** | **0% Complete** | - |

### By Category

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| **Security** | 3 | 2 | 1 | 0 | 6 |
| **Testing** | 1 | 3 | 2 | 0 | 6 |
| **Features** | 2 | 1 | 3 | 4 | 10 |
| **Code Quality** | 0 | 0 | 2 | 1 | 3 |
| **Documentation** | 0 | 0 | 0 | 1 | 1 |
| **Deployment** | 1 | 0 | 0 | 0 | 1 |

---

## Priority 0: Production Blockers

**Timeline:** 2-3 weeks (80-120 hours)
**Criteria:** MUST be completed before production. No workarounds available.

---

### P0-1: JWT Signature Verification

**Status:** ❌ MISSING
**Effort:** 6-8 hours
**Risk:** 🔴 CRITICAL SECURITY ISSUE
**Assignee:** TBD

**Current State:**
```python
# primetrade_project/auth_views.py:255
decoded = jwt.decode(id_token, options={"verify_signature": False})
```

**Problem:**
- JWT tokens from SSO not cryptographically verified
- Could accept forged tokens from malicious actor
- Violates OAuth 2.0 security best practices

**Required Actions:**
1. Obtain SSO server's public key (JWKS endpoint or static PEM)
2. Update PyJWT decode call:
   ```python
   from jwt import PyJWKClient
   jwks_client = PyJWKClient(f"{settings.SSO_BASE_URL}/.well-known/jwks.json")
   signing_key = jwks_client.get_signing_key_from_jwt(id_token)
   decoded = jwt.decode(
       id_token,
       signing_key.key,
       algorithms=["RS256"],
       audience=settings.SSO_CLIENT_ID,
       issuer=settings.SSO_BASE_URL
   )
   ```
3. Add error handling for invalid signatures
4. Test with valid and invalid tokens

**Testing Requirements:**
- Unit test: Valid JWT passes verification
- Unit test: Invalid signature raises exception
- Unit test: Expired JWT rejected
- Integration test: End-to-end SSO flow with verified JWT

**Dependencies:** None
**Blocks:** P0-2 (Admin Bypass Removal)

**Acceptance Criteria:**
- [ ] JWKS endpoint discovered or public key obtained
- [ ] JWT signature verified with PyJWT
- [ ] Invalid tokens rejected with 403 response
- [ ] Tests written and passing
- [ ] No performance regression (JWKS cached)

---

### P0-2: Admin Bypass Resolution

**Status:** ⚠️ ACTIVE (SECURITY ISSUE)
**Effort:** 16-24 hours
**Risk:** 🔴 CRITICAL SECURITY ISSUE
**Assignee:** TBD

**Current State:**
```python
# primetrade_project/auth_views.py:311-323
if not primetrade_role:
    bypass_list = getattr(settings, 'ADMIN_BYPASS_EMAILS', [])
    if email and bypass_list and email.lower() in [x.lower() for x in bypass_list]:
        logger.error(f"[FLOW DEBUG 7.5.1] BYPASS engaged for {email}")
        primetrade_role = {"role": "admin", "permissions": ["full_access"]}
    else:
        return HttpResponseForbidden("You don't have access to PrimeTrade. Contact admin.")
```

**Problem:**
- Anyone in `ADMIN_BYPASS_EMAILS` environment variable gets full admin access
- No audit trail for bypass usage
- Bypass grants "admin" role regardless of actual permissions
- Originally temporary workaround, now in production code

**Options for Resolution:**

**Option A: Fix SSO Server (RECOMMENDED)**
- Update barge2rail-auth to include `application_roles['primetrade']` in JWT claims
- Effort: 0 hours for PrimeTrade (depends on SSO team)
- Pros: Proper SSO integration, no workarounds
- Cons: Depends on external team

**Option B: Database-Backed Roles**
- Create `UserRole` model in PrimeTrade database
- Build admin UI to manually assign roles
- Effort: 16-24 hours
- Pros: Full control, no external dependencies
- Cons: Duplicates SSO role management

**Option C: Formalize Bypass (NOT RECOMMENDED)**
- Keep bypass but add audit logging
- Require multi-factor approval
- Effort: 4-6 hours
- Pros: Quick fix
- Cons: Still a security issue

**Required Actions (Option B - Database Roles):**
1. Create `UserRole` model with foreign key to Django User
2. Create admin view to assign roles (Django admin or custom UI)
3. Update `sso_callback` to check database for role after JWT validation
4. Migrate existing bypass emails to database
5. Remove `ADMIN_BYPASS_EMAILS` from code
6. Add audit logging for role assignments

**Testing Requirements:**
- Unit test: User with database role granted access
- Unit test: User without database role denied access
- Integration test: End-to-end SSO flow with database role check
- Manual test: Admin UI to assign/revoke roles

**Dependencies:** P0-1 (JWT Verification must work first)
**Blocks:** P1-2 (RBAC Implementation)

**Acceptance Criteria:**
- [ ] CTO decides Option A vs Option B
- [ ] If Option A: SSO team confirms timeline
- [ ] If Option B: UserRole model created and tested
- [ ] Admin bypass code removed from auth_views.py
- [ ] `ADMIN_BYPASS_EMAILS` env var no longer used
- [ ] Audit logging added for role grants/revocations
- [ ] Tests written and passing

---

### P0-3: Client Interface Requirements Definition

**Status:** ⚠️ UNDEFINED
**Effort:** 0 hours (CTO decision) + 16-24 hours (implementation)
**Risk:** 🔴 BLOCKING - Can't implement without requirements
**Assignee:** Clif (CTO decision), TBD (implementation)

**Current State:**
- `client.html` exists with basic skeleton
- Product balance calculation shown (start tons, shipped, remaining)
- No BOL creation or history view
- Tab exists on `index.html` but unclear what it should do

**Problem:**
- "Client interface" mentioned in STATUS.md and docs
- No specification of what "client" users should be able to do
- Different interpretations possible (see options below)

**Options for Clarification:**

**Option A: Read-Only BOL History**
- Clients view their past BOLs, download PDFs
- No creation, no approval workflow
- Effort: 4-6 hours
- Use case: Customer portal for record-keeping

**Option B: Self-Service BOL Creation**
- Clients create their own BOLs (same as office interface)
- Immediate confirmation, no approval needed
- Effort: 16-24 hours (duplicate office.html logic)
- Use case: Customer self-service

**Option C: Request-Approve Workflow**
- Clients request BOLs, office approves/rejects
- Similar to Release approval flow
- Effort: 24-32 hours (new approval logic)
- Use case: Customer-initiated but controlled

**Option D: External Authenticated Portal**
- Separate login for customers (not SSO)
- Full customer portal with BOL history, balance, requests
- Effort: 40-60 hours (new auth system)
- Use case: External customer access

**Required Actions:**
1. **CTO Decision:** Clif reviews options and selects one (or defines custom requirements)
2. Document requirements in FEATURE_SPEC.md or similar
3. Create wireframes/mockups if needed
4. Implement selected option
5. Write tests for client interface functionality

**Testing Requirements:**
- Depends on selected option
- Minimum: Unit tests for client-specific views
- Integration test: Client user flow (login → view → logout)

**Dependencies:** None (decision only)
**Blocks:** Cannot launch with undefined feature

**Acceptance Criteria:**
- [ ] CTO selects Option A, B, C, D, or defines custom requirements
- [ ] Requirements documented
- [ ] Implementation completed
- [ ] Tests written and passing
- [ ] Manual testing by office users

---

### P0-4: Increase Test Coverage to 70%

**Status:** ❌ 16% CURRENT COVERAGE
**Effort:** 40-60 hours
**Risk:** 🔴 BLOCKING - MEDIUM RISK protocol requires 70%
**Assignee:** TBD

**Current Coverage Breakdown:**
```
bol_system/__init__.py          100%
bol_system/admin.py               54%
bol_system/models.py              69%
bol_system/serializers.py          0% ⚠️ CRITICAL
bol_system/views.py                0% ⚠️ CRITICAL
primetrade_project/auth_views.py   Not measured (estimated 0%)
```

**Gap Analysis:**
- **views.py (1219 LOC, 0% coverage):** 18 API endpoints untested
- **serializers.py (0% coverage):** All validation logic untested
- **auth_views.py (384 LOC, estimated 0%):** SSO flow untested

**Priority Tests Needed:**

**High Priority (Critical Business Logic):**
1. BOL Creation Flow (views.py:confirm_bol)
   - Valid input creates BOL
   - Invalid input returns 400 error
   - BOL number auto-increments correctly
   - PDF generated and saved
   - AuditLog entry created
   - Effort: 6-8 hours

2. Release Approval Flow (views.py:approve_release)
   - Approve updates status to 'approved'
   - ReleaseLoad records created
   - Reject updates status to 'rejected'
   - AuditLog entry created
   - Effort: 4-6 hours

3. SSO Authentication (auth_views.py:sso_callback)
   - Valid JWT creates/updates User
   - Invalid JWT rejected
   - Role extracted from JWT
   - Session created
   - Effort: 6-8 hours

4. Serializer Validation (serializers.py)
   - All required fields validated
   - Invalid data rejected
   - Edge cases (negative numbers, etc.)
   - Effort: 4-6 hours

**Medium Priority (Data Integrity):**
5. Model Methods (models.py)
   - BOL.total_weight_lbs calculation
   - Auto-numbering uniqueness
   - BaseModel timestamps
   - Effort: 4-6 hours

6. PDF Generation
   - Valid BOL data generates PDF
   - PDF contains correct information
   - PDF saved to correct path
   - Effort: 4-6 hours

**Test Infrastructure:**
7. Fixtures and Factories
   - Product, Customer, Carrier test data
   - BOL test data
   - User/auth test data
   - Effort: 4-6 hours

**Required Actions:**
1. Install pytest fixtures: `pip install pytest-factoryboy`
2. Create test fixtures for common models
3. Write tests for views.py (18 endpoints)
4. Write tests for serializers.py (all serializers)
5. Write tests for auth_views.py (SSO flow)
6. Write tests for models.py (business logic methods)
7. Run coverage report: `pytest --cov --cov-report=html`
8. Iterate until 70% coverage achieved

**Testing Requirements:**
- Overall coverage: ≥70%
- views.py: ≥80%
- auth_views.py: ≥70%
- models.py: ≥90%
- serializers.py: ≥80%

**Dependencies:** None (can run in parallel with other tasks)
**Blocks:** Production deployment (per MEDIUM RISK protocol)

**Acceptance Criteria:**
- [ ] Overall test coverage ≥70%
- [ ] All critical paths tested (BOL creation, release approval, SSO auth)
- [ ] All edge cases tested (validation errors, duplicate BOL numbers)
- [ ] Coverage report in htmlcov/ directory
- [ ] Tests run in CI/CD (if applicable)

---

### P0-5: Fix Product Edit Bug

**Status:** ⚠️ BUG - Returns 400 "already exists"
**Effort:** 2-4 hours
**Risk:** 🟡 MEDIUM - Can't update product start_tons
**Assignee:** TBD

**Current State:**
- Product creation works fine
- Editing existing product (POST /api/products/) returns 400 error: "Product with this name already exists"
- Issue likely in upsert logic (should update by ID, not create duplicate)

**Reproduction Steps:**
1. Create product: POST /api/products/ {"name": "Corn", "start_tons": 1000}
2. Edit product: POST /api/products/ {"id": 1, "name": "Corn", "start_tons": 1200}
3. Result: 400 error (should return 200 with updated product)

**Root Cause (Suspected):**
- views.py likely creating new product instead of updating existing
- Unique constraint on `Product.name` triggers duplicate error
- Should check if `id` present in request, then UPDATE instead of INSERT

**Required Actions:**
1. Review views.py endpoint for product management
2. Add conditional logic:
   ```python
   if request.data.get('id'):
       # UPDATE existing product
       product = Product.objects.get(id=request.data['id'])
       serializer = ProductSerializer(product, data=request.data)
   else:
       # CREATE new product
       serializer = ProductSerializer(data=request.data)
   ```
3. Test create, update, delete operations
4. Add unit tests for each

**Testing Requirements:**
- Unit test: Create product returns 201
- Unit test: Update product returns 200 with updated data
- Unit test: Update non-existent product returns 404
- Manual test: Edit product via UI

**Dependencies:** None
**Blocks:** None (workaround: manually edit database)

**Acceptance Criteria:**
- [ ] Update product via API works (POST with id)
- [ ] Create product still works (POST without id)
- [ ] Tests written and passing
- [ ] UI product edit works end-to-end

---

### P0-6: Apply Migration 0007

**Status:** ⚠️ PENDING
**Effort:** 0.5 hours
**Risk:** 🟡 MEDIUM - Schema drift between dev and production
**Assignee:** TBD

**Current State:**
```bash
$ python manage.py makemigrations --dry-run
Migrations for 'bol_system':
  bol_system/migrations/0007_auto_YYYYMMDD_HHMM.py
    - Remove duplicate indexes
    - Clean up model definitions
```

**Problem:**
- Model changes not reflected in migration
- Dev database may differ from production
- May cause deployment failures

**Required Actions:**
1. Run: `python manage.py makemigrations`
2. Review generated migration file
3. Test migration on local database: `python manage.py migrate`
4. Test migration on Neon staging database (if available)
5. Commit migration file to Git
6. Apply migration on production during deployment

**Testing Requirements:**
- Manual test: Run migration locally without errors
- Manual test: Verify database schema matches models
- Check: No data loss during migration

**Dependencies:** None
**Blocks:** Production deployment (schema drift)

**Acceptance Criteria:**
- [ ] Migration 0007 created
- [ ] Migration tested locally
- [ ] Migration committed to Git
- [ ] Migration applied to production Neon database
- [ ] No schema warnings after migration

---

### P0-7: Environment Variable Documentation

**Status:** ⚠️ PARTIAL - .env.example outdated
**Effort:** 1-2 hours
**Risk:** 🟡 MEDIUM - Deployment failures due to missing env vars
**Assignee:** TBD

**Current State:**
- .env.example exists but may be missing new variables
- SSO_* variables added but not documented
- ADMIN_BYPASS_EMAILS not documented (intentionally, since it's temporary)

**Required Environment Variables (12):**
```bash
# Django Core
SECRET_KEY=<django-secret-key>
DEBUG=False
ALLOWED_HOSTS=primetrade.onrender.com,.onrender.com

# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://<user>:<password>@<host>/<dbname>

# SSO Integration (barge2rail-auth)
SSO_BASE_URL=https://barge2rail-auth.onrender.com
SSO_CLIENT_ID=<oauth-client-id>
SSO_CLIENT_SECRET=<oauth-client-secret>
SSO_REDIRECT_URI=https://primetrade.onrender.com/auth/callback/
SSO_SCOPES=openid profile email roles

# Temporary Admin Bypass (⚠️ REMOVE IN PRODUCTION)
ADMIN_BYPASS_EMAILS=clif@barge2rail.com

# Optional Audit Forwarding
GALACTICA_URL=https://galactica.onrender.com/api/events
```

**Required Actions:**
1. Update .env.example with all required variables
2. Add comments explaining each variable
3. Document where to obtain values (SSO_CLIENT_ID, etc.)
4. Create DEPLOYMENT.md with step-by-step setup instructions
5. Test deployment with .env.example values (should fail gracefully with clear errors)

**Testing Requirements:**
- Manual test: Deploy to Render with .env.example (should prompt for real values)
- Manual test: Missing SECRET_KEY raises clear error
- Manual test: Invalid DATABASE_URL raises clear error

**Dependencies:** None
**Blocks:** Production deployment (manual setup required without docs)

**Acceptance Criteria:**
- [ ] .env.example updated with all 12 variables
- [ ] Comments added explaining each variable
- [ ] DEPLOYMENT.md created with setup instructions
- [ ] Tested deployment with .env.example

---

## Priority 1: High Priority

**Timeline:** 1 week (36-54 hours)
**Criteria:** Should be completed before production. Workarounds exist but painful.

---

### P1-1: BOL Voiding/Cancellation

**Status:** ❌ MISSING
**Effort:** 6-8 hours
**Risk:** 🟡 MEDIUM - No way to correct mistakes without database edits
**Assignee:** TBD

**Current State:**
- BOLs are immutable after creation
- Typos or incorrect data require manual database edits
- No audit trail for voided BOLs

**Required Actions:**
1. Add `status` field to BOL model (pending/confirmed/voided)
2. Add `void_reason` and `voided_by` fields
3. Create `/api/bol/{id}/void/` endpoint
4. Update BOL PDF to show "VOIDED" watermark if status = voided
5. Update BOL history view to filter out voided BOLs (or show with indicator)
6. Add audit logging for void operations

**Testing Requirements:**
- Unit test: Void BOL updates status and logs reason
- Unit test: Voided BOL not shown in history (or shown with indicator)
- Integration test: Void BOL via UI
- Manual test: Voided BOL PDF shows watermark

**Dependencies:** None
**Blocks:** None (workaround: manual database edits)

**Acceptance Criteria:**
- [ ] BOL model has status field
- [ ] Void endpoint implemented
- [ ] Voided BOLs shown in history with indicator
- [ ] Audit logging added
- [ ] Tests written and passing

---

### P1-2: RBAC Implementation

**Status:** ❌ MISSING
**Effort:** 16-24 hours
**Risk:** 🔴 HIGH - All users have admin access
**Assignee:** TBD

**Current State:**
- All authenticated users have same permissions
- No role-based access control
- Admin bypass grants "admin" role but not checked anywhere

**Roles Needed:**
1. **Admin** - Full access (create/edit/delete all entities)
2. **Office** - Create BOLs, manage releases, view all data
3. **Client** - View own BOLs, request BOLs (if client interface allows)

**Required Actions:**
1. Create `Permission` model (or use Django's built-in permissions)
2. Assign permissions to roles:
   - Admin: All permissions
   - Office: create_bol, approve_release, view_all
   - Client: view_own_bol, request_bol
3. Update API views to check permissions:
   ```python
   from rest_framework.permissions import IsAuthenticated
   from .permissions import HasPermission

   class BOLViewSet(viewsets.ModelViewSet):
       permission_classes = [IsAuthenticated, HasPermission('create_bol')]
   ```
4. Update UI to hide/show buttons based on role
5. Add tests for each role

**Testing Requirements:**
- Unit test: Admin can create/edit/delete all entities
- Unit test: Office can create BOLs but not delete products
- Unit test: Client can view own BOLs but not create
- Integration test: Each role's full workflow

**Dependencies:** P0-2 (Admin Bypass Resolution - need role source)
**Blocks:** None (current state = all users admin)

**Acceptance Criteria:**
- [ ] Permission model created
- [ ] Permissions assigned to roles
- [ ] API views check permissions
- [ ] UI shows/hides features based on role
- [ ] Tests written and passing

---

### P1-3: Audit Logging (Authentication Events)

**Status:** ⚠️ PARTIAL - Only entity changes logged
**Effort:** 2-4 hours
**Risk:** 🟡 MEDIUM - No audit trail for logins/logouts
**Assignee:** TBD

**Current State:**
- AuditLog model exists and logs entity changes (create/update/delete)
- Login/logout events not logged
- Admin bypass usage not logged
- Failed login attempts not logged

**Required Actions:**
1. Add audit logging to `sso_callback` (successful login)
2. Add audit logging to `sso_logout` (logout)
3. Add audit logging to admin bypass usage (if still present)
4. Add audit logging to failed login attempts (invalid state, no role, etc.)
5. Consider logging to separate `AuthAuditLog` table (different retention policy)

**Testing Requirements:**
- Unit test: Successful login creates AuditLog entry
- Unit test: Logout creates AuditLog entry
- Unit test: Failed login creates AuditLog entry
- Manual test: Verify logs in database after login/logout

**Dependencies:** None
**Blocks:** None (workaround: review Django logs)

**Acceptance Criteria:**
- [ ] Login events logged
- [ ] Logout events logged
- [ ] Failed login attempts logged
- [ ] Admin bypass usage logged (if still present)
- [ ] Tests written and passing

---

### P1-4: Product Balance Calculation Fix

**Status:** ⚠️ PARTIAL - Basic calculation only
**Effort:** 4-6 hours
**Risk:** 🟡 MEDIUM - Incorrect balances shown
**Assignee:** TBD

**Current State:**
- Product balance calculation: `start_tons - shipped_tons`
- `shipped_tons` not accurately tracked (manual updates)
- Doesn't account for voided BOLs
- Doesn't sum from BOL records (should be calculated, not stored)

**Required Actions:**
1. Add `total_shipped` property to Product model:
   ```python
   @property
   def total_shipped(self):
       return self.bol_set.filter(status='confirmed').aggregate(
           total=Sum('net_tons')
       )['total'] or 0
   ```
2. Add `remaining` property:
   ```python
   @property
   def remaining(self):
       return self.start_tons - self.total_shipped
   ```
3. Update `/api/balances` endpoint to use properties
4. Remove manual `shipped_tons` updates (if any)
5. Add tests for calculation accuracy

**Testing Requirements:**
- Unit test: Product with no BOLs has remaining = start_tons
- Unit test: Product with BOLs has remaining = start_tons - sum(bol.net_tons)
- Unit test: Voided BOLs not included in calculation
- Integration test: Create BOL, verify balance decreases

**Dependencies:** P1-1 (BOL Voiding - need to filter out voided BOLs)
**Blocks:** None (current calculation is close enough for now)

**Acceptance Criteria:**
- [ ] Product.total_shipped property implemented
- [ ] Product.remaining property implemented
- [ ] /api/balances uses properties
- [ ] Voided BOLs excluded from calculation
- [ ] Tests written and passing

---

### P1-5: Advanced BOL Search/Filter

**Status:** ⚠️ PARTIAL - Basic date filter only
**Effort:** 6-8 hours
**Risk:** 🟡 MEDIUM - Poor UX for finding BOLs
**Assignee:** TBD

**Current State:**
- BOL history shows all BOLs (no search)
- Date filter exists but limited
- No search by BOL number, customer name, product, etc.

**Required Actions:**
1. Add query parameters to `/api/bol/` endpoint:
   - `?bol_number=PRT-2025-1234` - Exact match
   - `?customer=Cincinnati` - Case-insensitive substring
   - `?product=Corn` - Exact match or substring
   - `?date_from=2025-01-01` - Date range
   - `?date_to=2025-12-31` - Date range
2. Update frontend to show search form
3. Add pagination (currently all BOLs returned)
4. Add sorting (by date, BOL number, customer)

**Testing Requirements:**
- Unit test: Filter by BOL number returns correct BOL
- Unit test: Filter by customer returns matching BOLs
- Unit test: Date range filter works
- Integration test: Search via UI

**Dependencies:** None
**Blocks:** None (workaround: Ctrl+F in browser)

**Acceptance Criteria:**
- [ ] Query parameters added to /api/bol/
- [ ] Frontend search form implemented
- [ ] Pagination added (20 BOLs per page)
- [ ] Sorting by date/BOL number/customer
- [ ] Tests written and passing

---

### P1-6: CSRF Protection on API (Fix)

**Status:** ⚠️ BYPASSED
**Effort:** 2-4 hours
**Risk:** 🟡 MEDIUM - Potential CSRF attacks
**Assignee:** TBD

**Current State:**
```python
# bol_system/views.py:15
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # Bypass CSRF check
```

**Problem:**
- CSRF protection bypassed on all API endpoints
- Rationale: API consumed by same-origin JavaScript (session auth sufficient)
- Still vulnerable to CSRF if session cookie leaked

**Options:**

**Option A: Remove Bypass, Use CSRF Tokens**
- Update frontend to include CSRF token in all requests
- Django provides CSRF token via cookie or template tag
- Effort: 2-4 hours (update all API calls)
- Pros: Proper CSRF protection
- Cons: More complex frontend code

**Option B: Keep Bypass, Add SameSite Cookie**
- Already configured: `SESSION_COOKIE_SAMESITE='Lax'`
- Prevents CSRF from external sites
- Effort: 0 hours (already done)
- Pros: Simple, no frontend changes
- Cons: Not 100% protection (older browsers)

**Recommendation:** Option B (keep bypass, rely on SameSite cookie)

**Required Actions (if Option A selected):**
1. Remove `CsrfExemptSessionAuthentication` class
2. Update all fetch() calls to include CSRF token:
   ```javascript
   fetch('/api/bol/', {
       method: 'POST',
       headers: {
           'Content-Type': 'application/json',
           'X-CSRFToken': getCookie('csrftoken')
       },
       body: JSON.stringify(data)
   });
   ```
3. Test all API calls with CSRF token

**Testing Requirements:**
- Manual test: API call without CSRF token returns 403
- Manual test: API call with CSRF token succeeds
- Integration test: Full BOL creation flow with CSRF

**Dependencies:** None
**Blocks:** None (current bypass is acceptable for same-origin API)

**Acceptance Criteria:**
- [ ] CTO decides Option A or Option B
- [ ] If Option A: All API calls include CSRF token
- [ ] If Option B: Document SameSite cookie protection
- [ ] Tests written and passing

---

## Priority 2: Medium Priority

**Timeline:** 1 week (32-48 hours)
**Criteria:** Improves quality/maintainability but doesn't block production.

---

### P2-1: Reduce Cyclomatic Complexity

**Status:** ⚠️ 6 FUNCTIONS RATED F/E
**Effort:** 8-12 hours
**Risk:** 🟡 MEDIUM - Maintainability/debugging difficulty
**Assignee:** TBD

**Current State (from Radon analysis):**
```
F 152:0 approve_release - E (39)
E 254:0 confirm_bol - D (20)
E 171:0 sso_callback - D (19)
D 407:0 release_history - C (15)
```

**Functions to Refactor:**

**1. approve_release (views.py:152, complexity 39)**
- Current: 100+ lines, handles approval + load creation + audit
- Refactor: Extract `create_release_loads()` helper function
- Target complexity: <15

**2. confirm_bol (views.py:254, complexity 20)**
- Current: 80+ lines, handles validation + creation + PDF + audit
- Refactor: Extract `generate_bol_pdf()` and `create_audit_log()` helpers
- Target complexity: <15

**3. sso_callback (auth_views.py:171, complexity 19)**
- Current: 200+ lines, handles OAuth flow + JWT + user creation + bypass
- Refactor: Extract `validate_oauth_state()`, `exchange_code_for_tokens()`, `create_or_update_user()` helpers
- Target complexity: <15

**Required Actions:**
1. Refactor each function to extract helper methods
2. Run radon again to verify complexity reduced
3. Ensure tests still pass (or write tests if missing)
4. No behavior changes (pure refactoring)

**Testing Requirements:**
- All existing tests still pass
- No new bugs introduced
- Complexity metrics improved

**Dependencies:** P0-4 (Test Coverage - need tests before refactoring)
**Blocks:** None

**Acceptance Criteria:**
- [ ] approve_release complexity <15
- [ ] confirm_bol complexity <15
- [ ] sso_callback complexity <15
- [ ] All tests passing
- [ ] No behavior changes

---

### P2-2: Add Function Docstrings

**Status:** ⚠️ PARTIAL - Some functions documented
**Effort:** 4-6 hours
**Risk:** 🟢 LOW - Documentation only
**Assignee:** TBD

**Current State:**
- Some functions have docstrings, many don't
- Docstrings not consistent format (Google style recommended)
- Complex functions lack examples

**Required Actions:**
1. Add docstrings to all functions in views.py (18 functions)
2. Add docstrings to all functions in auth_views.py (6 functions)
3. Add docstrings to all model methods
4. Use Google style:
   ```python
   def confirm_bol(request):
       """
       Confirm BOL creation and generate PDF.

       Args:
           request (HttpRequest): Django request with BOL data in JSON body

       Returns:
           JsonResponse: BOL data with PDF URL on success, error on failure

       Raises:
           ValidationError: If BOL data invalid
           IntegrityError: If duplicate BOL number

       Example:
           >>> response = confirm_bol(request)
           >>> response.status_code
           201
       """
   ```

**Testing Requirements:**
- None (documentation only)

**Dependencies:** None
**Blocks:** None

**Acceptance Criteria:**
- [ ] All views.py functions have docstrings
- [ ] All auth_views.py functions have docstrings
- [ ] All model methods have docstrings
- [ ] Docstrings follow Google style
- [ ] Complex functions have examples

---

### P2-3: Consolidate Debug Logging

**Status:** ⚠️ EXCESSIVE - [FLOW DEBUG] logs in production code
**Effort:** 2-4 hours
**Risk:** 🟢 LOW - Log noise only
**Assignee:** TBD

**Current State:**
```python
# auth_views.py has 20+ debug log statements like:
logger.error(f"[FLOW DEBUG 1] State validation result: is_valid={is_valid}")
logger.error(f"[FLOW DEBUG 2] Authorization code received: {code[:20]}...")
# etc.
```

**Problem:**
- Debug logs use `logger.error()` (should be `logger.debug()`)
- `[FLOW DEBUG]` prefix suggests temporary debugging
- Clutters production logs

**Required Actions:**
1. Review all `[FLOW DEBUG]` log statements
2. Keep useful ones, change to `logger.debug()` or `logger.info()`
3. Remove temporary debugging logs
4. Add structured logging (JSON format for Galactica forwarding)

**Testing Requirements:**
- Manual test: Verify logs still capture useful information
- Manual test: No error-level logs for normal operations

**Dependencies:** None
**Blocks:** None

**Acceptance Criteria:**
- [ ] No `[FLOW DEBUG]` logs in production code
- [ ] Error logs only for actual errors
- [ ] Info logs for important events (login, BOL creation)
- [ ] Debug logs for diagnostic information

---

### P2-4: Branding Customization Fix

**Status:** ⚠️ /api/branding 404 ERROR (FIXED in quick fixes)
**Effort:** 0 hours (already fixed)
**Risk:** 🟢 LOW - Cosmetic only
**Assignee:** N/A (completed)

**Current State:**
- `/api/branding` endpoint removed
- Frontend still tries to fetch it (commented out as of quick fixes)
- Static branding used instead

**Status:** ✅ FIXED in quick fixes (static/index.html commented out fetch)

**If Branding Customization Needed Later:**
1. Re-implement `/api/branding` endpoint
2. Return JSON with company name, logo URL, address, phone, website
3. Uncomment frontend code to fetch and apply branding

**Effort (if re-implemented):** 4-6 hours

---

### P2-5: Add Request Timeout to Galactica Forwarding

**Status:** ⚠️ MISSING
**Effort:** 0.5 hours
**Risk:** 🟢 LOW - Only affects audit forwarding
**Assignee:** TBD

**Current State:**
- AuditLog.save() forwards to Galactica (if GALACTICA_URL set)
- No timeout on requests.post() call
- Could hang indefinitely if Galactica down

**Required Actions:**
1. Locate Galactica forwarding code (likely in models.py:AuditLog.save())
2. Add timeout parameter:
   ```python
   requests.post(galactica_url, json=data, timeout=5)
   ```
3. Add exception handling for timeout

**Testing Requirements:**
- Unit test: Galactica timeout doesn't block save()
- Unit test: Successful forward still works

**Dependencies:** None
**Blocks:** None

**Acceptance Criteria:**
- [ ] Timeout added to Galactica forwarding
- [ ] Exception handling added
- [ ] Tests written and passing

---

### P2-6: Add Database Connection Pooling

**Status:** ⚠️ MISSING (Optional for current scale)
**Effort:** 2-4 hours
**Risk:** 🟢 LOW - Not needed for 6-8 users
**Assignee:** TBD (post-launch)

**Current State:**
- Django manages database connections internally
- No explicit connection pooling
- Neon handles connection pooling server-side

**When Needed:**
- If scaling to 50+ users
- If seeing "too many connections" errors

**Required Actions (if implemented):**
1. Install pgBouncer or use Neon's pooling
2. Update DATABASE_URL to use pooling mode
3. Test under load

---

### P2-7: Add Health Check Endpoint

**Status:** ✅ EXISTS (/api/health)
**Effort:** 0 hours
**Risk:** 🟢 LOW
**Assignee:** N/A (already implemented)

**Current State:**
- `/api/health` endpoint returns 200 OK
- Render uses for health checks

**Status:** ✅ COMPLETE

---

### P2-8: Add Monitoring/Alerting

**Status:** ❌ MISSING
**Effort:** 8-12 hours
**Risk:** 🟢 LOW (manual monitoring acceptable for now)
**Assignee:** TBD (post-launch)

**Current State:**
- No monitoring/alerting
- No uptime tracking
- No error rate tracking

**When Needed:**
- Post-launch for proactive issue detection

**Options:**
- Render built-in monitoring (free tier limited)
- Sentry for error tracking (free tier available)
- UptimeRobot for uptime monitoring (free tier available)

**Required Actions (if implemented):**
1. Sign up for Sentry or similar
2. Add Sentry SDK to Django: `pip install sentry-sdk`
3. Configure in settings.py
4. Test error reporting

---

## Priority 3: Low Priority (Post-Launch)

**Timeline:** Post-launch (52-76 hours)
**Criteria:** Convenience features, not essential for launch.

---

### P3-1: Bulk Operations (Delete/Export)

**Status:** ❌ MISSING
**Effort:** 8-12 hours
**Assignee:** TBD (post-launch)

**Features Needed:**
- Select multiple BOLs, delete in bulk
- Select multiple BOLs, export to CSV
- Select multiple products, delete in bulk

**Dependencies:** None
**Priority:** POST-LAUNCH

---

### P3-2: BOL Editing (Post-Creation)

**Status:** ❌ MISSING
**Effort:** 12-16 hours
**Assignee:** TBD (post-launch)

**Features Needed:**
- Edit BOL fields after creation
- Track edit history (audit log)
- Regenerate PDF with "AMENDED" watermark

**Dependencies:** P1-1 (Voiding), P1-2 (RBAC)
**Priority:** POST-LAUNCH

**Note:** CTO decision needed on policy (see FEATURE_MATRIX.md)

---

### P3-3: Report Generation (Analytics)

**Status:** ❌ MISSING
**Effort:** 16-24 hours
**Assignee:** TBD (post-launch)

**Features Needed:**
- BOLs by product (date range)
- BOLs by customer (date range)
- Tons shipped by month/quarter
- Top customers by volume

**Dependencies:** None
**Priority:** POST-LAUNCH

---

### P3-4: Export to Excel/CSV

**Status:** ❌ MISSING
**Effort:** 4-6 hours
**Assignee:** TBD (post-launch)

**Features Needed:**
- Export BOL history to CSV
- Export product balances to CSV
- Export customer list to CSV

**Dependencies:** None
**Priority:** POST-LAUNCH

---

### P3-5: Email BOL to Customer

**Status:** ❌ MISSING
**Effort:** 8-12 hours
**Assignee:** TBD (post-launch)

**Features Needed:**
- Email BOL PDF to customer contact email
- Configurable email template
- Send via SendGrid or similar

**Dependencies:** None
**Priority:** POST-LAUNCH

---

### P3-6: User Management UI

**Status:** ❌ MISSING
**Effort:** 12-16 hours
**Assignee:** TBD (post-launch)

**Features Needed:**
- Admin UI to create/edit/delete users
- Assign roles to users
- Audit log for user changes

**Dependencies:** P1-2 (RBAC)
**Priority:** POST-LAUNCH

---

## Testing Gaps

### Summary

| Area | Current Coverage | Target | Gap | Effort |
|------|------------------|--------|-----|--------|
| **Overall** | 16% | 70% | 54% | 40-60 hours |
| **views.py** | 0% | 80% | 80% | 20-30 hours |
| **auth_views.py** | 0% | 70% | 70% | 10-15 hours |
| **models.py** | 69% | 90% | 21% | 5-10 hours |
| **serializers.py** | 0% | 80% | 80% | 5-10 hours |

### Critical Untested Paths

1. **BOL Creation** (views.py:confirm_bol)
   - Validation errors
   - Duplicate BOL numbers
   - PDF generation failures
   - ReleaseLoad updates
   - Effort: 6-8 hours

2. **Release Approval** (views.py:approve_release)
   - Status transitions
   - ReleaseLoad creation
   - Edge cases (already approved, etc.)
   - Effort: 4-6 hours

3. **SSO Authentication** (auth_views.py:sso_callback)
   - Invalid state/code
   - JWT decode failures
   - User creation/update
   - Admin bypass logic
   - Effort: 6-8 hours

### Test Infrastructure Gaps

- No test fixtures/factories
- No integration test suite
- No CI/CD pipeline
- No database fixtures for testing

**Effort to Build Infrastructure:** 4-6 hours

---

## Code Quality Gaps

### Complexity Issues

From Radon analysis:

| Function | File | Complexity | Target | Effort |
|----------|------|------------|--------|--------|
| approve_release | views.py:152 | F (39) | <15 | 3-4 hours |
| confirm_bol | views.py:254 | E (20) | <15 | 2-3 hours |
| sso_callback | auth_views.py:171 | E (19) | <15 | 3-4 hours |

**Total Refactoring Effort:** 8-12 hours

### Documentation Gaps

- Missing docstrings: ~40 functions
- No inline comments explaining WHY (only WHAT)
- No architecture decision records (ADRs)

**Effort:** 4-6 hours

### Code Duplication

- Product/Customer/Carrier/Lot management views are nearly identical
- Could extract to generic CRUD class
- Effort: 4-6 hours (optional refactoring)

---

## Security Gaps

### Critical

1. **JWT Signature Not Verified** (P0-1)
   - Risk: Forged tokens accepted
   - Effort: 6-8 hours

2. **Admin Bypass Active** (P0-2)
   - Risk: Anyone in bypass list = admin
   - Effort: 16-24 hours

### High

3. **No RBAC** (P1-2)
   - Risk: All users have admin access
   - Effort: 16-24 hours

### Medium

4. **CSRF Bypass on API** (P1-6)
   - Risk: Potential CSRF attacks
   - Effort: 2-4 hours (if removing bypass)

5. **No Authentication Audit Log** (P1-3)
   - Risk: No trail of logins/logouts
   - Effort: 2-4 hours

---

## Documentation Gaps

### Missing Documentation

1. **API Documentation**
   - No OpenAPI/Swagger spec
   - No endpoint documentation
   - Effort: 6-8 hours (generate from DRF)

2. **Deployment Guide**
   - DEPLOYMENT.md doesn't exist
   - Manual deployment steps not documented
   - Effort: 2-3 hours

3. **User Manual**
   - No end-user documentation
   - No screenshots/walkthrough
   - Effort: 8-12 hours (post-launch)

4. **Architecture Decision Records**
   - No ADRs documenting key decisions
   - ARCHITECTURE_OVERVIEW.md has some, but not formal ADRs
   - Effort: 2-4 hours

---

## Deployment Checklist

### Pre-Deployment

- [ ] P0-1: JWT Signature Verification implemented
- [ ] P0-2: Admin Bypass removed or formalized
- [ ] P0-3: Client Interface requirements defined and implemented
- [ ] P0-4: Test coverage ≥70%
- [ ] P0-5: Product edit bug fixed
- [ ] P0-6: Migration 0007 applied
- [ ] P0-7: Environment variables documented

### Environment Setup

- [ ] Render account created
- [ ] Neon database created (Ohio region)
- [ ] Environment variables configured in Render dashboard
- [ ] SSO OAuth client created in barge2rail-auth
- [ ] Galactica audit forwarding configured (if used)

### Database Migration

- [ ] Backup existing data (if any)
- [ ] Run migrations on production: `python manage.py migrate`
- [ ] Verify schema matches models
- [ ] Load initial data (products, customers, carriers)

### Static Files

- [ ] Run `python manage.py collectstatic --noinput`
- [ ] Verify static files served via WhiteNoise
- [ ] Test CSS/JS loading on production URL

### Security

- [ ] SECRET_KEY set to random value (not in code)
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enforced (Render automatic)
- [ ] CSRF protection enabled
- [ ] Admin bypass removed (or documented as temporary)

### Testing

- [ ] Manual test: Login via SSO
- [ ] Manual test: Create BOL end-to-end
- [ ] Manual test: Upload release
- [ ] Manual test: Approve release
- [ ] Manual test: View BOL history
- [ ] Manual test: Download BOL PDF
- [ ] Manual test: Logout

### Monitoring

- [ ] Health check endpoint working: `/api/health`
- [ ] Render monitoring configured
- [ ] Error logging working (check Render logs)
- [ ] Galactica audit forwarding working (if enabled)

### Rollback Plan

- [ ] Database backup before deployment
- [ ] Previous Git commit tagged
- [ ] Rollback procedure documented
- [ ] Emergency contact list (who to call if down)

---

## Timeline & Milestones

### Milestone 1: Production Blockers (Weeks 1-2)

**Goal:** Resolve all P0 issues
**Duration:** 2-3 weeks (80-120 hours)
**Deliverables:**
- [ ] JWT signature verification working
- [ ] Admin bypass removed or formalized
- [ ] Client interface defined and implemented
- [ ] Test coverage ≥70%
- [ ] Product edit bug fixed
- [ ] Migration 0007 applied
- [ ] Environment variables documented

**Success Criteria:** All P0 items checked off, no production blockers

---

### Milestone 2: High Priority (Week 3)

**Goal:** Complete P1 recommended items
**Duration:** 1 week (36-54 hours)
**Deliverables:**
- [ ] BOL voiding implemented
- [ ] RBAC implemented
- [ ] Authentication audit logging
- [ ] Product balance calculation fixed
- [ ] Advanced BOL search
- [ ] CSRF protection fixed (if needed)

**Success Criteria:** All P1 items checked off, production-ready with best practices

---

### Milestone 3: Production Launch (Week 4)

**Goal:** Deploy to production, internal testing
**Duration:** 1 week (20-30 hours)
**Activities:**
- [ ] Deploy to Render
- [ ] Run full test suite on production
- [ ] Office team training (2-hour session)
- [ ] Monitor for 1 week (daily check)
- [ ] Fix any urgent bugs

**Success Criteria:** 1 week stable operation, no critical bugs

---

### Milestone 4: Post-Launch Improvements (Weeks 5-8)

**Goal:** Add P2/P3 nice-to-have features
**Duration:** 3-4 weeks (84-124 hours)
**Deliverables:**
- [ ] Code quality improvements (complexity reduction, docstrings)
- [ ] Bulk operations
- [ ] BOL editing (if CTO approves)
- [ ] Report generation
- [ ] Export to CSV
- [ ] Email BOL to customer
- [ ] User management UI

**Success Criteria:** Feature parity with original vision

---

## Total Effort Summary

| Phase | Duration | Effort | Status |
|-------|----------|--------|--------|
| **Phase 1: Production Blockers** | 2-3 weeks | 80-120 hours | ❌ Not Started |
| **Phase 2: High Priority** | 1 week | 36-54 hours | ❌ Not Started |
| **Phase 3: Production Launch** | 1 week | 20-30 hours | ❌ Not Started |
| **Phase 4: Post-Launch** | 3-4 weeks | 84-124 hours | ❌ Not Started |
| **TOTAL** | **7-9 weeks** | **220-328 hours** | **0% Complete** |

**For 1 developer @ 40 hours/week:** 5.5-8.2 weeks to full completion

**Critical Path to Production (P0 + P1):** 3-4 weeks (116-174 hours)

---

## Document Metadata

**Generated:** November 2, 2025
**Generator:** Claude Code (Production Diagnostic)
**Project:** django-primetrade v1.0
**Location:** /Users/cerion/Projects/django-primetrade
**Total Gaps:** 27 items (7 P0, 6 P1, 8 P2, 6 P3)
**Estimated Work:** 220-328 hours (7-9 weeks for 1 developer)
**Next Steps:** Review CTO_HANDOFF.md for strategic decisions needed
