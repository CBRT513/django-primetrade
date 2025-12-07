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

    Session data (set during OAuth callback):
    - primetrade_role: {"role": "Office", "permissions": []}
    - feature_permissions: {"customers": ["view", "create"], ...}

    Permission Logic (RBAC Dec 2025):
    - can_write: true if user has "create" or "modify" for any feature
    - is_admin: true if role is "Admin" or has "full_access" permission

    Examples:
    - Admin: permissions=["full_access"] -> can_write=true, is_admin=true
    - Office: features={"bol": ["create", "modify"]} -> can_write=true
    - Client: features={"bol": ["view"]} -> can_write=false

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

    # Get feature permissions from session (RBAC system)
    feature_permissions = request.session.get("feature_permissions", {})

    # Check for write access:
    # 1. Legacy: "write" in top-level permissions array
    # 2. Admin: "full_access" in top-level permissions
    # 3. RBAC: Any feature has "create" or "modify" permission
    has_write_permission = (
        "write" in permissions
        or "full_access" in permissions
        or any(
            "create" in perms or "modify" in perms
            for perms in feature_permissions.values()
        )
    )

    # Check for admin access:
    # 1. "full_access" in top-level permissions
    # 2. Role is "Admin" (case-insensitive)
    is_admin = "full_access" in permissions or role.lower() == "admin"

    return JsonResponse(
        {
            "user": {"email": request.user.email, "role": role},
            "can_write": has_write_permission,
            "is_admin": is_admin,
            "permissions": permissions,  # Legacy permissions for debugging
            "features": feature_permissions,  # RBAC feature permissions
        }
    )
