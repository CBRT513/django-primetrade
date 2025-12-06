"""
OAuth/SSO authentication views for PrimeTrade.

Handles OAuth flow with barge2rail-auth SSO system.

SECURITY NOTES:
- Never log OAuth tokens (access_token, refresh_token, id_token) at any level
- Never log partial token values (even first N characters can be risky)
- Token presence ('SET' vs 'MISSING') is safe to log for debugging
- State tokens are single-use CSRF protection - don't log values
- User email and role info are safe to log (no credentials)

See: PrimeTrade Security Audit (Nov 2025) - Credential Logging Vulnerability
"""

import secrets
import requests
import time
import logging
from urllib.parse import urlencode
from django.shortcuts import redirect, render
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.core.cache import cache
import jwt
from jwt import PyJWKClient

# Set up loggers
logger = logging.getLogger('primetrade_project.auth_views')
security_logger = logging.getLogger('oauth.security')


# OAuth State Management Functions
def generate_oauth_state():
    """
    Generate secure OAuth state token with timestamp.
    Format: {random_token}:{timestamp}

    Returns:
        str: State token for CSRF protection
    """
    token = secrets.token_urlsafe(32)
    timestamp = str(int(time.time()))
    state = f"{token}:{timestamp}"
    # Security: Never log token values (even partial) - log only that token was generated
    logger.info(f"Generated OAuth state token (timestamp: {timestamp})")
    return state


def store_oauth_state(state, ttl=600):
    """
    Store OAuth state in cache with TTL.

    Args:
        state (str): State token to store
        ttl (int): Time-to-live in seconds (default 10 minutes)

    Returns:
        bool: True if stored successfully
    """
    cache_key = f"oauth_state:{state}"
    try:
        cache.set(cache_key, {'created_at': int(time.time())}, timeout=ttl)
        logger.info(f"Stored OAuth state in cache: {state[:20]}... (TTL: {ttl}s)")
        return True
    except Exception as e:
        security_logger.error(f"Failed to store OAuth state in cache: {e}")
        return False


def validate_and_consume_oauth_state(state, max_age=600):
    """
    Validate OAuth state token and consume it (single-use).

    Args:
        state (str): State token from callback
        max_age (int): Maximum age in seconds (default 10 minutes)

    Returns:
        tuple: (is_valid, error_message)
    """
    if not state:
        security_logger.warning("OAuth state validation failed: No state provided")
        return False, "Missing state parameter"

    # Check format (should be token:timestamp)
    try:
        token, timestamp_str = state.split(':', 1)
        timestamp = int(timestamp_str)
    except (ValueError, AttributeError) as e:
        security_logger.warning(f"OAuth state validation failed: Invalid format - {e}")
        return False, "Invalid state format"

    # Check if state exists in cache
    cache_key = f"oauth_state:{state}"
    cached_data = cache.get(cache_key)

    if cached_data is None:
        security_logger.warning(f"OAuth state validation failed: State not found in cache or already used: {state[:20]}...")
        return False, "Invalid or expired state token"

    # Check timestamp (prevent replay attacks)
    age = int(time.time()) - timestamp
    if age > max_age:
        security_logger.warning(f"OAuth state validation failed: Token expired (age: {age}s)")
        cache.delete(cache_key)  # Clean up
        return False, f"State token expired (age: {age}s, max: {max_age}s)"

    # Delete state from cache (single-use)
    cache.delete(cache_key)
    logger.info(f"OAuth state validated and consumed: {state[:20]}... (age: {age}s)")

    return True, None


def login_page(request):
    """Redirect directly to SSO - no choice screen"""
    if request.user.is_authenticated:
        return redirect('home')
    # Redirect directly to SSO login (no choice screen)
    return redirect('sso_login')


def sso_login(request):
    """Initiate SSO login - redirect to SSO OAuth with cache-based state storage"""

    # Generate state token with timestamp for CSRF protection
    state = generate_oauth_state()

    # Store state in cache (TTL: 10 minutes)
    if not store_oauth_state(state, ttl=600):
        security_logger.error("Failed to store OAuth state - cache unavailable")
        return HttpResponseForbidden("Authentication service temporarily unavailable. Please try again.")

    # Also store in session as backup (for backward compatibility)
    request.session['oauth_state'] = state
    request.session.modified = True

    logger.info(f"Initiating SSO login with state: {state[:20]}...")

    # Build OAuth authorization URL
    # Ensure 'roles' scope is included for application role claims
    scopes = set((settings.SSO_SCOPES or '').split())
    scopes.add('roles')
    scope_str = ' '.join(sorted(scopes))

    params = {
        'client_id': settings.SSO_CLIENT_ID,
        'redirect_uri': settings.SSO_REDIRECT_URI,
        'response_type': 'code',
        'scope': scope_str,
        'state': state,
    }

    auth_url = f"{settings.SSO_BASE_URL}/o/authorize/?{urlencode(params)}"
    return redirect(auth_url)


def sso_callback(request):
    """Handle SSO callback after user authenticates - with cache-based state validation"""

    # Get state from callback
    state = request.GET.get('state')
    code = request.GET.get('code')

    logger.info(f"SSO callback received - state: {state[:20] if state else 'None'}..., code: {'present' if code else 'missing'}")

    # Validate state using cache (primary method)
    is_valid, error_msg = validate_and_consume_oauth_state(state, max_age=600)

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 1] State validation result: is_valid={is_valid}, error_msg={error_msg}")

    if not is_valid:
        # Try session as fallback for backward compatibility
        stored_state = request.session.get('oauth_state')
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 1.1] State validation failed, trying session fallback. stored_state={'present' if stored_state else 'missing'}, matches={state == stored_state if state and stored_state else 'N/A'}")

        if state and stored_state and state == stored_state:
            logger.warning(f"State validated using session fallback: {state[:20]}...")
            if settings.DEBUG_AUTH_FLOW:
                logger.debug(f"[FLOW DEBUG 1.2] Session fallback SUCCESS - proceeding with auth")
            # Clear session state
            if 'oauth_state' in request.session:
                del request.session['oauth_state']
                request.session.modified = True
        else:
            security_logger.warning(
                f"OAuth state validation failed - IP: {request.META.get('REMOTE_ADDR')}, "
                f"State: {state[:20] if state else 'None'}..., Error: {error_msg}"
            )
            if settings.DEBUG_AUTH_FLOW:
                logger.debug(f"[FLOW DEBUG 1.3] State validation FAILED completely - returning 403")
            return HttpResponseForbidden(
                f"Invalid state parameter - {error_msg}. "
                f"This may indicate a CSRF attack or an expired session. "
                f"Please try logging in again."
            )
    else:
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 1.4] State validation SUCCESS via cache")
        # Clear session state if present
        if 'oauth_state' in request.session:
            del request.session['oauth_state']
            request.session.modified = True

    # Get authorization code
    if not code:
        security_logger.warning("No authorization code received in SSO callback")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 2] MISSING authorization code - returning 403")
        return HttpResponseForbidden("No authorization code received")

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 2] Authorization code received: {code[:20]}...")

    # Exchange code for tokens
    token_url = f"{settings.SSO_BASE_URL}/o/token/"
    token_data = {
        'code': code,
        'client_id': settings.SSO_CLIENT_ID,
        'client_secret': settings.SSO_CLIENT_SECRET,
        'redirect_uri': settings.SSO_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 3] About to exchange token:")
        logger.debug(f"[FLOW DEBUG 3.1]   - token_url: {token_url}")
        logger.debug(f"[FLOW DEBUG 3.2]   - client_id: {settings.SSO_CLIENT_ID[:20] if settings.SSO_CLIENT_ID else 'MISSING'}...")
        logger.debug(f"[FLOW DEBUG 3.3]   - client_secret: {'SET (len=' + str(len(settings.SSO_CLIENT_SECRET)) + ')' if settings.SSO_CLIENT_SECRET else 'MISSING'}")
        logger.debug(f"[FLOW DEBUG 3.4]   - redirect_uri: {settings.SSO_REDIRECT_URI}")
        logger.debug(f"[FLOW DEBUG 3.5]   - grant_type: {token_data.get('grant_type')}")
        logger.debug(f"[FLOW DEBUG 3.6]   - code (first 20 chars): {code[:20]}...")

    try:
        response = requests.post(token_url, data=token_data, timeout=10)

        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 4] Token exchange response received:")
            logger.debug(f"[FLOW DEBUG 4.1]   - Status code: {response.status_code}")
            logger.debug(f"[FLOW DEBUG 4.2]   - Headers: {dict(response.headers)}")
            logger.debug(f"[FLOW DEBUG 4.3]   - Body (first 500 chars): {response.text[:500]}")

        response.raise_for_status()
        tokens = response.json()

        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 4.4] Token exchange SUCCESS - received keys: {list(tokens.keys())}")

    except requests.RequestException as e:
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 4.5] Token exchange FAILED:")
            logger.debug(f"[FLOW DEBUG 4.5.1]   - Exception type: {type(e).__name__}")
            logger.debug(f"[FLOW DEBUG 4.5.2]   - Exception message: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.debug(f"[FLOW DEBUG 4.5.3]   - Response status: {e.response.status_code}")
                logger.debug(f"[FLOW DEBUG 4.5.4]   - Response body: {e.response.text}")
        return HttpResponseForbidden(f"Token exchange failed: {str(e)}")

    # Decode JWT token to get user info
    # Note: access_token is an opaque string, id_token is the JWT with user claims
    access_token = tokens.get('access_token')  # Keep for session storage
    id_token = tokens.get('id_token')  # This is the JWT to decode

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 5] Attempting to decode JWT:")
        # Security: Never log token values (even partial) - log only presence
        logger.debug(f"[FLOW DEBUG 5.1]   - id_token present: {'YES' if id_token else 'NO'}")

    try:
        # Fetch JWKS from SSO and verify JWT signature
        jwks_url = f"{settings.SSO_BASE_URL}/api/auth/.well-known/jwks.json"
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 5.3] Fetching JWKS from: {jwks_url}")

        jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 5.4] Retrieved signing key: {signing_key.key_id}")

        # Decode and verify JWT with full validation
        decoded = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.SSO_CLIENT_ID,
            issuer=f"{settings.SSO_BASE_URL}/o",
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            }
        )

        logger.info(f"JWT verified and decoded successfully. Claims: {list(decoded.keys())}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6] JWT verified and decoded successfully:")
            logger.debug(f"[FLOW DEBUG 6.1]   - Available claims: {list(decoded.keys())}")
            logger.debug(f"[FLOW DEBUG 6.2]   - Full decoded JWT: {decoded}")

    except jwt.InvalidSignatureError as e:
        security_logger.error(f"JWT signature verification failed: {str(e)}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6.3] JWT SIGNATURE INVALID: {str(e)}")
        return HttpResponseForbidden("Invalid token signature - authentication failed. Possible token forgery detected.")

    except jwt.ExpiredSignatureError as e:
        security_logger.warning(f"JWT token expired: {str(e)}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6.4] JWT EXPIRED: {str(e)}")
        return HttpResponseForbidden("Authentication token has expired. Please log in again.")

    except jwt.InvalidAudienceError as e:
        security_logger.error(f"JWT audience mismatch: {str(e)}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6.5] JWT AUDIENCE MISMATCH: {str(e)}")
        return HttpResponseForbidden("Invalid token audience - token not intended for this application.")

    except jwt.InvalidIssuerError as e:
        security_logger.error(f"JWT issuer mismatch: {str(e)}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6.6] JWT ISSUER MISMATCH: {str(e)}")
        return HttpResponseForbidden("Invalid token issuer - token from untrusted source.")

    except jwt.DecodeError as e:
        security_logger.error(f"JWT decode failed: {str(e)}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6.7] JWT DECODE FAILED: {str(e)}")
        return HttpResponseForbidden(f"Invalid JWT token format: {str(e)}")

    except Exception as e:
        security_logger.error(f"JWT verification error: {str(e)}", exc_info=True)
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 6.8] JWT VERIFICATION ERROR: {str(e)}")
        return HttpResponseForbidden("Authentication failed. Please try again or contact support.")

    # If application_roles missing, try OIDC userinfo endpoint (fallback)
    if not decoded.get('application_roles') and access_token:
        try:
            ui_resp = requests.get(
                f"{settings.SSO_BASE_URL}/o/userinfo/",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
            if ui_resp.ok:
                userinfo = ui_resp.json()
                # Merge userinfo into decoded claims
                decoded.update(userinfo)
                if settings.DEBUG_AUTH_FLOW:
                    logger.debug(f"[FLOW DEBUG 5.9] userinfo merged. Keys now: {list(decoded.keys())}")
            else:
                if settings.DEBUG_AUTH_FLOW:
                    logger.debug(f"[FLOW DEBUG 5.9] userinfo fetch failed: {ui_resp.status_code} {ui_resp.text[:200]}")
        except Exception as e:
            if settings.DEBUG_AUTH_FLOW:
                logger.debug(f"[FLOW DEBUG 5.9] userinfo request error: {e}")

    # Extract user information from claims
    email = decoded.get('email')
    user_roles = decoded.get('roles', {})

    logger.info(f"Extracted email: {email}, roles: {list(user_roles.keys()) if user_roles else 'none'}")

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 7] User info extracted from JWT:")
        logger.debug(f"[FLOW DEBUG 7.1]   - email: {email}")
        logger.debug(f"[FLOW DEBUG 7.2]   - user_roles: {user_roles}")
        logger.debug(f"[FLOW DEBUG 7.3]   - is_sso_admin: {decoded.get('is_sso_admin', False)}")

    # Validate email is present
    if not email:
        security_logger.warning(f"No email claim in JWT. Available claims: {list(decoded.keys())}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 7.4] MISSING email claim - returning 403")
        return HttpResponseForbidden("No email claim in authentication token. Contact admin.")

    # Check for primetrade role in application_roles claim
    application_roles = decoded.get("application_roles", {})
    primetrade_role = application_roles.get("primetrade")

    # Log full application_roles for diagnostics
    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 7.4] application_roles: {application_roles}")

    if not primetrade_role:
        logger.warning(f"User {email} does not have PrimeTrade role. Available apps: {list(application_roles.keys())}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 7.5] User lacks PrimeTrade role - evaluating bypass")
        # Temporary controlled bypass for admin/testing during rollout
        try:
            bypass_list = getattr(settings, 'ADMIN_BYPASS_EMAILS', [])
        except Exception:
            bypass_list = []
        if email and bypass_list and email.lower() in [x.lower() for x in bypass_list]:
            if settings.DEBUG_AUTH_FLOW:
                logger.debug(f"[FLOW DEBUG 7.5.1] BYPASS engaged for {email} - proceeding as admin")
            primetrade_role = {"role": "admin", "permissions": ["full_access"]}
        else:
            return HttpResponseForbidden("You don't have access to PrimeTrade. Contact admin.")

    # Extract role details for session storage
    role_name = primetrade_role.get("role")
    permissions = primetrade_role.get("permissions", [])

    logger.info(f"User {email} authenticated with PrimeTrade role: {role_name}")
    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 8] Role check PASSED - role: {role_name}, permissions: {permissions}")

    # Get or create Django user
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            'email': email,
            'first_name': decoded.get('given_name', decoded.get('display_name', '').split()[0] if decoded.get('display_name') else ''),
        }
    )

    if created:
        logger.info(f"Created new user: {email}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 9] Created NEW Django user: {email} (ID: {user.id})")
    else:
        logger.info(f"Using existing user: {email}")
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 9] Using EXISTING Django user: {email} (ID: {user.id})")

    # Store SSO role and tokens in session (for now)
    request.session['primetrade_role'] = {
        'role': role_name,
        'permissions': permissions
    }
    # Tenant context (Phase 1: static per deployment)
    request.session['tenant_id'] = settings.TENANT_ID
    request.session['tenant_name'] = settings.TENANT_NAME
    request.session['sso_access_token'] = access_token
    request.session['sso_refresh_token'] = tokens.get('refresh_token')

    # Store application_roles for FeaturePermissionMiddleware (RBAC)
    request.session['application_roles'] = application_roles
    logger.info(f"Stored application_roles in session: {list(application_roles.keys())}")

    # Store feature_permissions directly for quick access
    feature_permissions = primetrade_role.get('features', {})
    request.session['feature_permissions'] = feature_permissions
    logger.info(f"Stored feature_permissions in session: {list(feature_permissions.keys())}")

    # RBAC Debug logging
    logger.info(f"[RBAC DEBUG] application_roles from JWT: {application_roles}")
    logger.info(f"[RBAC DEBUG] primetrade_role from JWT: {primetrade_role}")
    logger.info(f"[RBAC DEBUG] Stored in session - application_roles: {request.session.get('application_roles')}")
    logger.info(f"[RBAC DEBUG] Stored in session - feature_permissions: {request.session.get('feature_permissions')}")

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 10] Session data stored:")
        logger.debug(f"[FLOW DEBUG 10.1]   - primetrade_role: {role_name} with permissions: {permissions}")
        logger.debug(f"[FLOW DEBUG 10.2]   - sso_access_token: {'SET' if access_token else 'MISSING'}")
        logger.debug(f"[FLOW DEBUG 10.3]   - sso_refresh_token: {'SET' if tokens.get('refresh_token') else 'MISSING'}")

    # Log user into Django
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 11] Django login() called:")
        logger.debug(f"[FLOW DEBUG 11.1]   - user authenticated: {user.is_authenticated}")
        logger.debug(f"[FLOW DEBUG 11.2]   - request.user: {request.user}")
        logger.debug(f"[FLOW DEBUG 11.3]   - request.user.is_authenticated: {request.user.is_authenticated}")
        logger.debug(f"[FLOW DEBUG 11.4]   - session key: {request.session.session_key}")

    # Get user's role for role-based landing page redirect
    role = request.session.get('primetrade_role', {}).get('role', 'user')
    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 11.5] User role: {role}")

    # Look up configured redirect for this role
    redirect_url = 'home'  # Default fallback
    try:
        from bol_system.models import RoleRedirectConfig
        config = RoleRedirectConfig.objects.filter(
            role_name=role,
            is_active=True
        ).first()

        if config:
            redirect_url = config.landing_page
            if settings.DEBUG_AUTH_FLOW:
                logger.debug(f"[FLOW DEBUG 11.6] Using role-based redirect: {redirect_url}")
        else:
            if settings.DEBUG_AUTH_FLOW:
                logger.debug(f"[FLOW DEBUG 11.6] No active redirect config for role '{role}', using default")

    except Exception as e:
        if settings.DEBUG_AUTH_FLOW:
            logger.debug(f"[FLOW DEBUG 11.6] Error looking up role redirect: {e}")
        # Safe fallback to default

    if settings.DEBUG_AUTH_FLOW:
        logger.debug(f"[FLOW DEBUG 12] About to redirect to: {redirect_url}")
        logger.debug(f"[FLOW DEBUG 12.1] Full auth flow completed successfully for user: {email}")

    return redirect(redirect_url)


def sso_logout(request):
    """Logout user and redirect to SSO logout with return path to PrimeTrade"""
    from urllib.parse import urlencode

    # Clear Django session
    logout(request)

    # Build post-logout redirect URI (where SSO should send user after logout)
    # Use the configured SSO_REDIRECT_URI as base to get correct scheme/host
    # Then change the path to /auth/login/
    redirect_base = settings.SSO_REDIRECT_URI.rsplit('/auth/callback/', 1)[0]
    post_logout_uri = f"{redirect_base}/auth/login/"

    # SSO logout with OIDC standard parameters
    # client_id is required to validate post_logout_redirect_uri
    logout_params = {
        'client_id': settings.SSO_CLIENT_ID,
        'post_logout_redirect_uri': post_logout_uri,
    }
    logout_query = urlencode(logout_params)
    sso_logout_url = f"{settings.SSO_BASE_URL}/o/logout/?{logout_query}"

    logger.info(f"Logging out and redirecting to SSO with post_logout_redirect_uri={post_logout_uri}")
    return redirect(sso_logout_url)
