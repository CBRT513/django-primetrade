"""
API views for PrimeTrade user context and RBAC.

This module provides API endpoints for frontend JavaScript to query
user permissions and role information.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required


@login_required
@require_http_methods(["GET"])
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

    Returns:
        JsonResponse: User context with permissions as booleans
    """
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
    role = role_info.get("role", "viewer")
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
