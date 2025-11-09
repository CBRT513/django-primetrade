# Test Coverage Improvement Plan

**Created:** November 9, 2025
**Current Coverage:** 40%
**Target Coverage:** 70%+
**Estimated Time:** 5-8 hours over multiple sessions

---

## Phase 1: Security Tests (3 hours)

**Priority:** 🔴 **HIGH** - Must complete before major auth changes

**Target:** `primetrade_project/auth_views.py` from 36% → 85%+

### Tasks

- [ ] **OAuth State Validation Tests (45 min)**
  - Test state generation creates unique tokens
  - Test state storage in cache
  - Test state expiration (10-minute TTL)
  - Test duplicate state detection
  - Test invalid/missing state rejection
  - File: Create `primetrade_project/test_oauth_state.py`

- [ ] **OAuth Callback Flow Tests (60 min)**
  - Test successful OAuth callback with valid code
  - Test callback with missing code parameter
  - Test callback with missing state parameter
  - Test callback with expired state
  - Test callback with invalid state
  - Test token exchange error handling (timeout, 4xx, 5xx)
  - File: Create `primetrade_project/test_oauth_callback.py`

- [ ] **User Creation from SSO Claims Tests (30 min)**
  - Test new user creation from valid JWT claims
  - Test existing user login (no duplicate creation)
  - Test email extraction from JWT
  - Test username assignment
  - Test user with missing email claim
  - File: Add to `primetrade_project/test_oauth_callback.py`

- [ ] **Session Management Tests (30 min)**
  - Test session data storage (role, permissions, tokens)
  - Test session retrieval after login
  - Test session clearing on logout
  - Test access_token storage in session
  - Test refresh_token storage in session
  - File: Create `primetrade_project/test_session_management.py`

- [ ] **Logout Flow Tests (15 min)**
  - Test logout clears Django session
  - Test logout redirects correctly
  - Test logout with unauthenticated user
  - File: Create `primetrade_project/test_logout.py`

### Success Criteria

- [ ] `auth_views.py` coverage ≥ 85%
- [ ] All OAuth flow paths tested (success + error cases)
- [ ] State validation fully tested
- [ ] Token exchange fully tested
- [ ] User creation fully tested

---

## Phase 2: API Endpoint Tests (2 hours)

**Priority:** 🟡 **MEDIUM** - Needed before template replication

**Target:** `bol_system/views.py` from 12% → 50%+

### Tasks

- [ ] **BOL Creation Endpoint Tests (45 min)**
  - Test BOL creation with valid data
  - Test BOL creation with missing required fields
  - Test BOL creation with invalid data types
  - Test BOL creation permission checks (Office/Admin only)
  - Test BOL number auto-increment
  - File: Create `bol_system/test_bol_endpoints.py`

- [ ] **Permission Enforcement Tests (30 min)**
  - Test authenticated user can access protected endpoints
  - Test unauthenticated user gets 401
  - Test Office role can create BOLs
  - Test Admin role can create BOLs
  - Test Client role CANNOT create BOLs
  - File: Add to `bol_system/test_bol_endpoints.py`

- [ ] **Data Validation Tests (30 min)**
  - Test serializer validation catches invalid data
  - Test required field validation
  - Test foreign key validation (Customer, Product, Carrier)
  - Test date field validation
  - Test numeric field validation (weight, quantity)
  - File: Create `bol_system/test_validation.py`

- [ ] **Error Response Tests (15 min)**
  - Test 400 errors return proper JSON
  - Test 403 errors for permission denied
  - Test 404 errors for missing resources
  - Test 500 errors are handled gracefully
  - File: Add to existing test files

### Success Criteria

- [ ] `views.py` coverage ≥ 50%
- [ ] All BOL CRUD endpoints tested
- [ ] Permission enforcement tested
- [ ] Data validation tested
- [ ] Error responses tested

---

## Phase 3: Edge Cases & Polish (2 hours)

**Priority:** 🟢 **LOW** - Nice to have

**Target:** Overall coverage from 50% → 70%+

### Tasks

- [ ] **RBAC Middleware Tests (45 min)**
  - Test Client role restricted to `/client.html?productId=9`
  - Test Client role redirected from other pages
  - Test Office role can access all pages
  - Test Admin role can access all pages
  - Test unauthenticated user handled by @login_required
  - File: Create `primetrade_project/test_rbac_middleware.py`

- [ ] **Decorator Tests (30 min)**
  - Test `@require_primetrade_role` decorator
  - Test permission inheritance
  - Test multiple role requirements
  - File: Create `primetrade_project/test_decorators.py`

- [ ] **Error Handling Coverage (30 min)**
  - Test OAuth token exchange network errors
  - Test SSO server unavailable scenarios
  - Test database connection errors
  - Test cache unavailable scenarios
  - File: Add to existing test files

- [ ] **Management Command Tests (15 min)** *(Optional)*
  - Test `migrate_pdfs_to_s3` with mock S3
  - Test `regenerate_bol_pdf` with test BOL
  - Test `set_bol_counter` validation
  - File: Create `bol_system/test_management_commands.py`

### Success Criteria

- [ ] Overall coverage ≥ 70%
- [ ] RBAC middleware fully tested
- [ ] Decorators fully tested
- [ ] Error handling paths covered

---

## Timeline & Scheduling

### Recommended Schedule

**Option A: Dedicated Sprint**
- Schedule: 1-2 full days before intern project (January 2026)
- Focus: Complete all 3 phases in sequence
- Benefit: Comprehensive coverage before new development

**Option B: Incremental**
- Schedule: 1 hour per week over 8 weeks
- Focus: One test file per week
- Benefit: Gradual improvement without blocking other work

**Option C: Just-In-Time**
- Schedule: When making changes to auth/API
- Focus: Add tests for code being modified
- Benefit: Ensures new code is tested
- Risk: Doesn't address existing gaps

### Milestones

- **Week 1-2:** Phase 1 (Security Tests) → 55% coverage
- **Week 3-4:** Phase 2 (API Tests) → 60% coverage
- **Week 5-6:** Phase 3 (Edge Cases) → 70% coverage

---

## Testing Infrastructure Setup

### Required Tools

Already installed ✅:
- `coverage==7.11.0` - Code coverage measurement
- `django.test` - Django test framework
- `rest_framework.test` - DRF test client

### Test Data Fixtures

Create shared fixtures for common test scenarios:

```python
# bol_system/fixtures.py
def create_test_customer():
    """Create test customer for BOL tests"""
    return Customer.objects.create(
        name="Test Customer",
        address="123 Test St",
        city="Cincinnati",
        state="OH",
        zip_code="45202"
    )

def create_test_bol():
    """Create test BOL with all relationships"""
    customer = create_test_customer()
    product = create_test_product()
    carrier = create_test_carrier()

    return BOL.objects.create(
        customer=customer,
        product=product,
        carrier=carrier,
        quantity=25.5,
        date="2025-01-01"
    )
```

### Mock Helpers

Create mocks for external dependencies:

```python
# primetrade_project/test_helpers.py
from unittest.mock import Mock, patch

def mock_sso_token_exchange(valid=True):
    """Mock SSO token exchange response"""
    if valid:
        return {
            'access_token': 'test_access_token',
            'id_token': create_test_jwt(),
            'refresh_token': 'test_refresh_token'
        }
    else:
        raise requests.HTTPError("Token exchange failed")

def create_test_jwt(claims=None):
    """Create test JWT with specified claims"""
    default_claims = {
        'sub': '12345',
        'email': 'test@barge2rail.com',
        'name': 'Test User',
        'application_roles': {
            'primetrade': {
                'role': 'Admin',
                'permissions': ['read', 'write', 'admin']
            }
        }
    }
    # Merge with provided claims
    # Return signed JWT
```

---

## Test Organization

### File Structure

```
primetrade_project/
├── test_jwt_verification.py       ✅ (100% coverage)
├── test_oauth_state.py             ⏳ (Phase 1)
├── test_oauth_callback.py          ⏳ (Phase 1)
├── test_session_management.py      ⏳ (Phase 1)
├── test_logout.py                  ⏳ (Phase 1)
├── test_rbac_middleware.py         ⏳ (Phase 3)
├── test_decorators.py              ⏳ (Phase 3)
└── test_helpers.py                 ⏳ (Shared utilities)

bol_system/
├── test_auth.py                    ✅ (Legacy auth)
├── test_pdf_watermark.py           ✅ (96% coverage)
├── test_bol_endpoints.py           ⏳ (Phase 2)
├── test_validation.py              ⏳ (Phase 2)
├── test_management_commands.py     ⏳ (Phase 3 - optional)
└── fixtures.py                     ⏳ (Shared test data)
```

---

## Running Tests During Development

### Basic Workflow

```bash
# 1. Run specific test file
python manage.py test primetrade_project.test_oauth_state

# 2. Run with coverage
coverage run --source='.' manage.py test primetrade_project.test_oauth_state
coverage report | grep auth_views

# 3. Check coverage increased
coverage html
open htmlcov/index.html

# 4. Commit when coverage improved
git commit -m "test: add OAuth state validation tests (+15% coverage)"
```

### Coverage Tracking

Track progress in this document:

- **Baseline (Nov 9, 2025):** 40%
- **After Phase 1:** ___ % (target: 55%)
- **After Phase 2:** ___ % (target: 60%)
- **After Phase 3:** ___ % (target: 70%)

---

## Risks & Mitigation

### Risk 1: Tests Reveal Bugs

**Likelihood:** Medium
**Impact:** High

**Mitigation:**
- Good! Finding bugs before production is the goal
- Fix bugs as discovered
- Document bugs in KNOWN_ISSUES.md if deferring fixes

### Risk 2: Time Estimates Too Optimistic

**Likelihood:** High
**Impact:** Medium

**Mitigation:**
- Start with Phase 1 (highest priority)
- If time runs out, at least security is covered
- Adjust timeline based on actual time taken

### Risk 3: Test Setup Complexity

**Likelihood:** Low
**Impact:** Medium

**Mitigation:**
- Use Django's built-in test tools (simple, well-documented)
- Create shared fixtures (reduce duplication)
- Copy patterns from existing tests (test_jwt_verification.py)

---

## Success Metrics

### Quantitative

- [ ] Overall coverage ≥ 70%
- [ ] `auth_views.py` coverage ≥ 85%
- [ ] `views.py` coverage ≥ 50%
- [ ] All tests passing (no failures)

### Qualitative

- [ ] Can modify OAuth flow with confidence (tests catch regressions)
- [ ] Can add new API endpoints following tested pattern
- [ ] Template users have clear testing examples to follow
- [ ] New developers can run tests and understand system behavior

---

## Next Steps

1. **Choose timeline:** Sprint vs. Incremental vs. Just-In-Time
2. **Schedule work:** Block calendar time if choosing Sprint
3. **Start Phase 1:** Create `test_oauth_state.py` (easiest test to start)
4. **Track progress:** Update this document with coverage %
5. **Celebrate wins:** Each phase completion is a milestone!

---

## Related Documentation

- `TESTING.md` - Current coverage status and gaps
- `CLAUDE.md` - Testing philosophy and standards (70% minimum)
- `htmlcov/index.html` - Detailed coverage report

---

## Questions?

**Why not 100% coverage?**
- 70% is the standard for new code (CLAUDE.md)
- Diminishing returns beyond 70% (testing trivial code)
- Some code is hard to test (ASGI/WSGI, management commands)

**Why prioritize auth tests?**
- Security is highest risk
- Auth is most critical to get right
- JWT verification already at 100% (good foundation)

**Why not test management commands?**
- Run manually by admins (low frequency)
- Not part of user-facing workflows
- Can test manually when needed

**When should I run tests?**
- Before every commit (quick check: `python manage.py test`)
- Before every deployment (full suite + coverage)
- After any auth/API changes (regression check)
