import secrets
import requests
import time
import logging
from urllib.parse import urlencode
from django.shortcuts import redirect, render
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponseForbidden
from django.core.cache import cache
import jwt

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
    logger.info(f"Generated OAuth state token: {token[:10]}... (timestamp: {timestamp})")
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


def emergency_login_page(request):
    """Emergency backdoor login - shows legacy login form only"""
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'emergency_login.html')


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
    params = {
        'client_id': settings.SSO_CLIENT_ID,
        'redirect_uri': settings.SSO_REDIRECT_URI,
        'response_type': 'code',
        'scope': settings.SSO_SCOPES,
        'state': state,
    }

    auth_url = f"{settings.SSO_BASE_URL}/auth/authorize/?{urlencode(params)}"
    return redirect(auth_url)


def sso_callback(request):
    """Handle SSO callback after user authenticates - with cache-based state validation"""

    # Get state from callback
    state = request.GET.get('state')
    code = request.GET.get('code')

    logger.info(f"SSO callback received - state: {state[:20] if state else 'None'}..., code: {'present' if code else 'missing'}")

    # Validate state using cache (primary method)
    is_valid, error_msg = validate_and_consume_oauth_state(state, max_age=600)

    if not is_valid:
        # Try session as fallback for backward compatibility
        stored_state = request.session.get('oauth_state')
        if state and stored_state and state == stored_state:
            logger.warning(f"State validated using session fallback: {state[:20]}...")
            # Clear session state
            if 'oauth_state' in request.session:
                del request.session['oauth_state']
                request.session.modified = True
        else:
            security_logger.warning(
                f"OAuth state validation failed - IP: {request.META.get('REMOTE_ADDR')}, "
                f"State: {state[:20] if state else 'None'}..., Error: {error_msg}"
            )
            return HttpResponseForbidden(
                f"Invalid state parameter - {error_msg}. "
                f"This may indicate a CSRF attack or an expired session. "
                f"Please try logging in again."
            )
    else:
        # Clear session state if present
        if 'oauth_state' in request.session:
            del request.session['oauth_state']
            request.session.modified = True

    # Get authorization code
    if not code:
        security_logger.warning("No authorization code received in SSO callback")
        return HttpResponseForbidden("No authorization code received")

    # Exchange code for tokens
    token_url = f"{settings.SSO_BASE_URL}/auth/token/"
    token_data = {
        'code': code,
        'client_id': settings.SSO_CLIENT_ID,
        'client_secret': settings.SSO_CLIENT_SECRET,
        'redirect_uri': settings.SSO_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }

    try:
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        tokens = response.json()
    except requests.RequestException as e:
        return HttpResponseForbidden(f"Token exchange failed: {str(e)}")

    # Decode JWT token to get user info
    access_token = tokens.get('access_token')
    try:
        # For now, decode without verification (will add JWT validation later)
        decoded = jwt.decode(access_token, options={"verify_signature": False})
    except jwt.DecodeError as e:
        return HttpResponseForbidden(f"Invalid JWT token: {str(e)}")

    # Extract user information
    email = decoded.get('email')
    user_roles = tokens.get('user', {}).get('roles', {})
    primetrade_role = user_roles.get('primetrade', {}).get('role')

    if not primetrade_role:
        return HttpResponseForbidden("You don't have access to PrimeTrade. Contact admin.")

    # Get or create Django user
    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            'email': email,
            'first_name': decoded.get('display_name', '').split()[0] if decoded.get('display_name') else '',
        }
    )

    # Store SSO role and tokens in session (for now)
    request.session['sso_role'] = primetrade_role
    request.session['sso_access_token'] = access_token
    request.session['sso_refresh_token'] = tokens.get('refresh_token')

    # Log user into Django
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    # Redirect to home/dashboard
    return redirect('home')


def sso_logout(request):
    """Logout user and clear SSO session"""

    # Clear Django session
    logout(request)

    # Optionally redirect to SSO logout
    sso_logout_url = f"{settings.SSO_BASE_URL}/auth/logout/"
    return redirect(sso_logout_url)
