# OAuth Endpoint Fix - Django OAuth Toolkit Compatibility

## Problem
PrimeTrade was using incorrect OAuth endpoint paths that don't match django-oauth-toolkit's URL structure.

## Root Cause
The SSO service (barge2rail-auth) uses django-oauth-toolkit, which serves OAuth endpoints under `/o/` not `/auth/`.

## Changes Made

### File: `primetrade_project/auth_views.py`

**Line 142 - Authorization Endpoint**
```python
# BEFORE (WRONG):
auth_url = f"{settings.SSO_BASE_URL}/auth/authorize/?{urlencode(params)}"

# AFTER (CORRECT):
auth_url = f"{settings.SSO_BASE_URL}/o/authorize/?{urlencode(params)}"
```

**Line 199 - Token Endpoint**
```python
# BEFORE (WRONG):
token_url = f"{settings.SSO_BASE_URL}/auth/token/"

# AFTER (CORRECT):
token_url = f"{settings.SSO_BASE_URL}/o/token/"
```

**Line 338 - Logout Endpoint**
```python
# BEFORE (WRONG):
sso_logout_url = f"{settings.SSO_BASE_URL}/auth/logout/"

# AFTER (CORRECT):
sso_logout_url = f"{settings.SSO_BASE_URL}/o/logout/"
```

## Correct OAuth Flow

1. **Authorization Request** → `https://sso.barge2rail.com/o/authorize/`
2. **Token Exchange** → `https://sso.barge2rail.com/o/token/`
3. **Logout** → `https://sso.barge2rail.com/o/logout/`

## Django OAuth Toolkit Standard Endpoints

All django-oauth-toolkit installations use these standard paths:
- `/o/authorize/` - Authorization endpoint
- `/o/token/` - Token endpoint
- `/o/revoke_token/` - Token revocation endpoint
- `/o/introspect/` - Token introspection endpoint

## No Environment Variable Changes Required

The `.env` file only contains `SSO_BASE_URL`, which is correct:
```bash
SSO_BASE_URL=http://127.0.0.1:8000  # (dev)
SSO_BASE_URL=https://sso.barge2rail.com  # (production)
```

The endpoint paths are constructed in the code, not stored as config.

## Testing

### Local Testing (Development)
```bash
# Start PrimeTrade on port 8002
source venv/bin/activate
python manage.py runserver 127.0.0.1:8002

# Navigate to login
# http://127.0.0.1:8002/login/
```

**Expected Flow:**
1. Click "Login with SSO"
2. Redirects to: `http://127.0.0.1:8000/o/authorize/?client_id=...&redirect_uri=...&state=...`
3. After login, callback to: `http://127.0.0.1:8002/auth/callback/`
4. Token exchange to: `http://127.0.0.1:8000/o/token/`
5. User logged in and redirected to dashboard

### Production Testing (After Deployment)
```bash
# Navigate to production login
# https://prt.barge2rail.com/login/
```

**Expected Flow:**
1. Click "Login with SSO"
2. Redirects to: `https://sso.barge2rail.com/o/authorize/?...`
3. After login, callback to: `https://prt.barge2rail.com/auth/callback/`
4. Token exchange to: `https://sso.barge2rail.com/o/token/`
5. User logged in and redirected to dashboard

## Deployment Checklist

- [x] Updated auth_views.py with correct OAuth paths
- [x] Verified no hardcoded paths remain in Python code
- [x] Confirmed .env files don't need changes
- [ ] **Test locally with SSO service running**
- [ ] **Commit changes to git**
- [ ] **Push to GitHub**
- [ ] **Deploy to Render**
- [ ] **Test production OAuth flow**

## Git Commit

```bash
git add primetrade_project/auth_views.py OAUTH_ENDPOINT_FIX.md
git commit -m "Fix: Update OAuth endpoints to django-oauth-toolkit standard paths (/o/ not /auth/)

- Update authorization endpoint: /auth/authorize/ → /o/authorize/
- Update token endpoint: /auth/token/ → /o/token/
- Update logout endpoint: /auth/logout/ → /o/logout/

Fixes OAuth integration with barge2rail-auth SSO service which uses django-oauth-toolkit.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## References

- Django OAuth Toolkit Documentation: https://django-oauth-toolkit.readthedocs.io/
- OAuth 2.0 RFC: https://datatracker.ietf.org/doc/html/rfc6749
- Barge2Rail SSO (django-oauth-toolkit based): http://127.0.0.1:8000/o/ (dev)

## Related Files

- **Changed**: `primetrade_project/auth_views.py:142,199,338`
- **No changes needed**: `primetrade_project/settings.py`
- **No changes needed**: `.env`, `.env.backup`, `.env.example`
- **Documentation only**: `SSO_IMPLEMENTATION.md`, `CACHE_BASED_OAUTH_STATE.md`, `SSO_DIRECT_LOGIN.md`
