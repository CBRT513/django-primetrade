"""
API views for PrimeTrade user context and RBAC.

This module provides API endpoints for frontend JavaScript to query
user permissions and role information.

SECURITY NOTES:
- Never log OAuth tokens (access_token, refresh_token) at any level
- Never log full session contents with dict(request.session) or dict(request.session.items())
- Session keys (not values) can be logged at DEBUG level for troubleshooting
- User email and role info are safe to log (no credentials)

See: PrimeTrade Security Audit (Nov 2025) - Credential Logging Vulnerability
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from primetrade_project.decorators import require_role

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET"])
@require_role('Admin', 'Office', 'Client')  # All authenticated users - Phase 2 fix
def user_context(request):
    """
    Return user context for RBAC frontend.

    Frontend (rbac.js) expects:
    {
        "user": {"email": "...", "role": "..."},
        "can_write": boolean,
        "is_admin": boolean
    }

    Backend stores in session (set during OAuth callback):
    request.session['primetrade_role'] = {
        'role': 'Office',  # Admin, Office, or Client
        'permissions': ['read', 'write', 'delete']
    }

    Permission Logic:
    - Admin: ['full_access'] -> can_write=true, is_admin=true
    - Office: ['read', 'write', 'delete'] -> can_write=true, is_admin=false
    - Client: ['read'] -> can_write=false, is_admin=false

    Security (Phase 2 Fix):
    - All authenticated users (Admin, Office, Client) can access
    - Required for client dashboard initialization

    Returns:
        JsonResponse: User context with permissions as booleans
    """
    # Security: Never log tokens, session contents, or sensitive credentials
    logger.info(f"[USER_CONTEXT] Request from {request.META.get('REMOTE_ADDR')}, user={request.user.email if request.user.is_authenticated else 'anonymous'}")

    if not request.user.is_authenticated:
        return JsonResponse(
            {
                "error": "Not authenticated",
                "user": None,
                "can_write": False,
                "is_admin": False,
            },
            status=401,
        )

    # Get role info from session (stored during OAuth callback)
    role_info = request.session.get("primetrade_role", {})
    role = role_info.get("role", "Client")  # Default to Client
    permissions = role_info.get("permissions", [])

    # Convert permissions array to boolean flags for frontend
    can_write = "write" in permissions or "full_access" in permissions
    is_admin = "full_access" in permissions

    return JsonResponse(
        {
            "user": {"email": request.user.email, "role": role},
            "can_write": can_write,
            "is_admin": is_admin,
            "permissions": permissions,  # Include raw permissions for debugging
        }
    )
