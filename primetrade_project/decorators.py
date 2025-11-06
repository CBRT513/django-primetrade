"""
Reusable RBAC decorators for barge2rail SSO applications.

This pattern works for ANY app using barge2rail SSO:
- PrimeTrade
- RepairTracker (future)
- BargeTracking (future)
- Customer Database (future)

Each app stores role in session during OAuth callback.
Decorators read session and enforce permissions.

Role Definitions (from SSO):
- admin: Full access (read + write + admin functions)
- user: Standard access (read + write)
- viewer: Read-only access (no create/edit/delete)
- operator: Operator access (custom per-app)

Usage:
    from primetrade_project.decorators import require_role

    @require_role('admin', 'user')  # Allow multiple roles
    def create_bol(request):
        # Only admin and user can execute this
        pass

    @require_role('admin')  # Single role
    def delete_bol(request):
        # Only admin can execute this
        pass
"""

from functools import wraps
from django.http import HttpResponseForbidden
import logging

logger = logging.getLogger('primetrade.security')


def require_role(*allowed_roles):
    """
    Require specific role(s) for view access.

    Reads role from request.session['primetrade_role']['role'] which is set
    during OAuth callback in primetrade_project/auth_views.py.

    Args:
        *allowed_roles: Variable number of role strings (e.g., 'admin', 'user', 'viewer')

    Returns:
        Decorator function that wraps the view

    Behavior:
        - If user has one of the allowed roles: Execute view normally
        - If user lacks required role: Return 403 Forbidden with clear message
        - If session missing role data: Return 403 with re-login prompt

    Security:
        - Logs all access denials for audit trail
        - Includes user email, attempted view, and role mismatch details

    Example:
        @require_role('admin', 'user')
        @api_view(['POST'])
        def confirm_bol(request):
            # Viewers will be blocked with 403
            # Admin and user roles can proceed
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get role from session (set during OAuth callback)
            app_role = request.session.get('primetrade_role', {})
            user_role = app_role.get('role')
            user_email = request.user.email if request.user.is_authenticated else 'unknown'

            # Edge case: Session missing role data (expired or corrupted)
            if not app_role:
                logger.error(
                    f"Missing primetrade_role in session for {user_email} "
                    f"attempting {view_func.__name__}"
                )
                return HttpResponseForbidden(
                    "Session expired or missing role data. Please log out and log in again."
                )

            # Check if user has one of the allowed roles
            if user_role in allowed_roles:
                # Access granted - execute view
                return view_func(request, *args, **kwargs)

            # Access denied - log for security audit and return 403
            logger.warning(
                f"Access denied: {user_email} (role={user_role or 'none'}) "
                f"attempted {view_func.__name__}. "
                f"Required roles: {', '.join(allowed_roles)}"
            )

            return HttpResponseForbidden(
                f"Access denied. This action requires one of the following roles: "
                f"{', '.join(allowed_roles)}. Your current role: {user_role or 'none'}. "
                f"Contact your administrator if you believe this is incorrect."
            )

        return wrapped_view
    return decorator


def require_role_for_writes(*allowed_roles):
    """
    Require specific role(s) for write operations (POST, PUT, PATCH, DELETE).

    GET requests pass through without role check (allows read-only users to view data).
    Write operations (POST, PUT, PATCH, DELETE) require one of the allowed roles.

    This is useful for endpoints that mix read and write operations in one view.

    Args:
        *allowed_roles: Variable number of role strings (e.g., 'admin', 'user')

    Returns:
        Decorator function that wraps the view

    Example:
        @require_role_for_writes('admin', 'user')
        @api_view(['GET', 'POST'])
        def customer_list(request):
            # GET requests: Anyone authenticated can view
            # POST requests: Only admin and user can create/update
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Allow GET requests without role check (read-only access)
            if request.method == 'GET':
                return view_func(request, *args, **kwargs)

            # For write operations, check role
            app_role = request.session.get('primetrade_role', {})
            user_role = app_role.get('role')
            user_email = request.user.email if request.user.is_authenticated else 'unknown'

            # Edge case: Session missing role data
            if not app_role:
                logger.error(
                    f"Missing primetrade_role in session for {user_email} "
                    f"attempting {view_func.__name__} {request.method}"
                )
                return HttpResponseForbidden(
                    "Session expired or missing role data. Please log out and log in again."
                )

            # Check if user has one of the allowed roles
            if user_role in allowed_roles:
                # Access granted
                return view_func(request, *args, **kwargs)

            # Access denied
            logger.warning(
                f"Access denied: {user_email} (role={user_role or 'none'}) "
                f"attempted {view_func.__name__} {request.method}. "
                f"Required roles: {', '.join(allowed_roles)}"
            )

            return HttpResponseForbidden(
                f"Access denied. This action requires one of the following roles: "
                f"{', '.join(allowed_roles)}. Your current role: {user_role or 'none'}. "
                f"Contact your administrator if you believe this is incorrect."
            )

        return wrapped_view
    return decorator
