"""
Feature-level permission utilities for PrimeTrade (RBAC).

This module provides utilities to check feature-level permissions
from the SSO RBAC system.

PrimeTrade Features:
    - dashboard: Main dashboard
    - bol: Bill of Lading
    - releases: Release management
    - schedule: Loading schedule
    - products: Product catalog
    - customers: Customer database
    - carriers: Carrier management
    - reports: Reporting and exports
    - admin: Administration

Permissions per feature:
    - view: Can see/read data
    - create: Can create new records
    - modify: Can update existing records
    - delete: Can delete records
    - export: Can export/download data

JWT claim structure (from SSO):
{
    "application_roles": {
        "primetrade": {
            "role": "Office",
            "permissions": ["read", "write"],
            "features": {
                "dashboard": ["view"],
                "bol": ["view", "create", "modify"],
                "releases": ["view", "create", "modify"],
                ...
            }
        }
    }
}

Usage:
    # Check single permission
    if has_permission(request, 'bol', 'modify'):
        # User can modify BOL

    # Decorator for views
    @feature_permission_required('releases', 'modify')
    def edit_release(request, release_id):
        ...

    # Check any of multiple permissions
    if has_any_permission(request, 'bol', ['create', 'modify']):
        # User can create or modify BOL
"""

import logging
from functools import wraps

from django.http import JsonResponse

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("django.security")

# Application slug used to look up permissions in JWT claims
APP_SLUG = "primetrade"


def get_feature_permissions(request):
    """
    Extract feature permissions from request.

    Returns:
        dict: Feature permissions dict, e.g., {"bol": ["view", "create"], ...}
        Empty dict if no permissions found.
    """
    # Permissions are set by middleware from JWT claims
    feature_perms = getattr(request, "feature_permissions", None)
    if feature_perms:
        return feature_perms

    # Fallback: try to extract from session (for session-based auth)
    app_roles = request.session.get("application_roles", {})
    app_data = app_roles.get(APP_SLUG, {})
    return app_data.get("features", {})


def has_permission(request, feature: str, permission: str) -> bool:
    """
    Check if user has a specific permission for a feature.

    Args:
        request: Django request object
        feature: Feature code (e.g., 'bol', 'releases')
        permission: Permission code (e.g., 'view', 'create', 'modify', 'delete')

    Returns:
        bool: True if user has the permission

    Example:
        if has_permission(request, 'bol', 'modify'):
            bol.save()
    """
    feature_perms = get_feature_permissions(request)
    permissions = feature_perms.get(feature, [])
    return permission in permissions


def has_any_permission(request, feature: str, permissions: list) -> bool:
    """
    Check if user has any of the specified permissions for a feature.

    Args:
        request: Django request object
        feature: Feature code (e.g., 'bol')
        permissions: List of permission codes to check

    Returns:
        bool: True if user has at least one of the permissions

    Example:
        if has_any_permission(request, 'bol', ['create', 'modify']):
            show_edit_button = True
    """
    feature_perms = get_feature_permissions(request)
    user_perms = feature_perms.get(feature, [])
    return any(p in user_perms for p in permissions)


def has_all_permissions(request, feature: str, permissions: list) -> bool:
    """
    Check if user has ALL specified permissions for a feature.

    Args:
        request: Django request object
        feature: Feature code (e.g., 'bol')
        permissions: List of permission codes required

    Returns:
        bool: True if user has all the permissions

    Example:
        if has_all_permissions(request, 'bol', ['view', 'export']):
            allow_export = True
    """
    feature_perms = get_feature_permissions(request)
    user_perms = feature_perms.get(feature, [])
    return all(p in user_perms for p in permissions)


def feature_permission_required(feature: str, permission: str):
    """
    Decorator that restricts view access based on feature permissions.

    Usage:
        @feature_permission_required('bol', 'modify')
        def edit_bol(request, bol_id):
            ...

    Returns 403 JSON response for AJAX requests, renders error page otherwise.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_permission(request, feature, permission):
                user_email = getattr(request.user, "email", "unknown")
                security_logger.warning(
                    f"Permission denied: user={user_email}, "
                    f"feature={feature}, permission={permission}, path={request.path}"
                )

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Permission denied",
                            "message": f"You don't have '{permission}' permission for '{feature}'",
                        },
                        status=403,
                    )

                from django.shortcuts import render

                return render(
                    request,
                    "403.html",
                    {
                        "message": f"You don't have '{permission}' permission for '{feature}'.",
                        "feature": feature,
                        "permission": permission,
                    },
                    status=403,
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def any_feature_permission_required(feature: str, permissions: list):
    """
    Decorator that allows access if user has ANY of the listed permissions.

    Usage:
        @any_feature_permission_required('bol', ['create', 'modify'])
        def save_bol(request, bol_id=None):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_any_permission(request, feature, permissions):
                user_email = getattr(request.user, "email", "unknown")
                security_logger.warning(
                    f"Permission denied: user={user_email}, "
                    f"feature={feature}, required_any={permissions}, path={request.path}"
                )

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "Permission denied",
                            "message": f"You need one of these permissions for '{feature}': {', '.join(permissions)}",
                        },
                        status=403,
                    )

                from django.shortcuts import render

                return render(
                    request,
                    "403.html",
                    {
                        "message": f"You need one of these permissions for '{feature}': {', '.join(permissions)}",
                        "feature": feature,
                        "permissions": permissions,
                    },
                    status=403,
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# PrimeTrade Feature Codes
# =============================================================================

FEATURES = [
    "dashboard",
    "bol",
    "releases",
    "schedule",
    "products",
    "customers",
    "carriers",
    "reports",
    "admin",
]

# Permission codes
PERMISSIONS = ["view", "create", "modify", "delete", "export"]

# Map legacy roles to feature permissions for backward compatibility
LEGACY_ROLE_PERMISSIONS = {
    "admin": {
        "dashboard": ["view", "create", "modify", "delete", "export"],
        "bol": ["view", "create", "modify", "delete", "export"],
        "releases": ["view", "create", "modify", "delete", "export"],
        "schedule": ["view", "create", "modify", "delete", "export"],
        "products": ["view", "create", "modify", "delete", "export"],
        "customers": ["view", "create", "modify", "delete", "export"],
        "carriers": ["view", "create", "modify", "delete", "export"],
        "reports": ["view", "create", "modify", "delete", "export"],
        "admin": ["view", "create", "modify", "delete", "export"],
    },
    "office": {
        "dashboard": ["view", "create", "modify"],
        "bol": ["view", "create", "modify"],
        "releases": ["view", "create", "modify"],
        "schedule": ["view", "create", "modify"],
        "products": ["view", "create", "modify"],
        "customers": ["view", "create", "modify"],
        "carriers": ["view", "create", "modify"],
        "reports": ["view", "export"],
        "admin": [],
    },
    "client": {
        "dashboard": ["view"],
        "bol": ["view"],
        "releases": ["view"],
        "schedule": ["view"],
        "products": ["view"],
        "customers": [],
        "carriers": [],
        "reports": ["view"],
        "admin": [],
    },
}


def get_permissions_from_legacy_role(role: str) -> dict:
    """
    Get feature permissions based on legacy role.

    This is used when the user doesn't have RBAC permissions
    but does have a legacy role assignment.

    Args:
        role: Legacy role name (admin/office/client)

    Returns:
        dict: Feature permissions derived from role
    """
    return LEGACY_ROLE_PERMISSIONS.get(role.lower(), {})


def get_effective_permissions(request) -> dict:
    """
    Get effective permissions, preferring RBAC over legacy role.

    This helper checks for RBAC feature permissions first,
    then falls back to deriving permissions from the legacy role.

    Args:
        request: Django request object

    Returns:
        dict: Effective feature permissions
    """
    # Try RBAC permissions first
    feature_perms = get_feature_permissions(request)
    if feature_perms:
        return feature_perms

    # Fall back to legacy role
    legacy_role = getattr(request, "user_role", None)
    if legacy_role:
        return get_permissions_from_legacy_role(legacy_role)

    return {}
