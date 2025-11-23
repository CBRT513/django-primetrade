"""
Middleware for PrimeTrade role-based PAGE access control.

Security Notes (Phase 2 - Nov 2025):
- Middleware controls PAGE access (HTML pages), NOT API access
- Client users can access /api/* endpoints (decorators enforce permissions)
- Client users restricted to /client.html?productId=9 for pages
- Admin/Office users can access all pages
- API access control is enforced by @require_role decorators on each endpoint
"""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve
import logging

logger = logging.getLogger(__name__)


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce page-level access control based on user role.

    Client users:
    - Can access /api/* endpoints (permission checked by decorators)
    - Can access /client.html?productId=9 (dashboard)
    - Can access /client-schedule.html (loading schedule)

    Office and Admin users:
    - Can access all pages and API endpoints
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Pages that don't require authentication
        self.public_paths = [
            '/login/',
            '/auth/login/',
            '/auth/callback/',
            '/auth/logout/',
            '/static/',
            # /api/ REMOVED - All API endpoints now use @require_role decorators
        ]

        # Specific public API paths (rare - most APIs require auth)
        self.public_api_paths = [
            '/api/health/',  # Health check endpoint can stay public
        ]

        # Client-only allowed path
        self.client_allowed_path = '/client.html'
        self.client_required_product_id = '9'

    def __call__(self, request):
        # Skip check for public paths
        path = request.path
        if any(path.startswith(public_path) for public_path in self.public_paths):
            return self.get_response(request)

        # Check specific public API paths
        if path in self.public_api_paths:
            return self.get_response(request)

        # Skip check for unauthenticated users (will be handled by @login_required)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Attach tenant context to request (Phase 1: static)
        request.tenant_id = request.session.get('tenant_id')
        request.tenant_name = request.session.get('tenant_name')

        # Get user role from session
        role_info = request.session.get('primetrade_role', {})
        user_role = role_info.get('role', 'viewer')

        if settings.DEBUG:
            logger.debug(f"[RBAC MIDDLEWARE] User: {request.user.email}, Role: {user_role}, Path: {path}")

        # Client role restrictions
        if user_role == 'Client':
            # Block access to admin HTML pages disguised as API endpoints
            # Example: /api/releases/19/view/ returns HTML with edit forms
            if path.startswith('/api/releases/') and path.endswith('/view/'):
                logger.warning(f"[RBAC MIDDLEWARE] Client access DENIED to admin release page: {path}")
                return redirect(f'{self.client_allowed_path}?productId={self.client_required_product_id}')
            
            # Allow API access - decorators handle permission checking
            if path.startswith('/api/'):
                if settings.DEBUG:
                    logger.debug(f"[RBAC MIDDLEWARE] Client API access - checked by @require_role decorator: {path}")
                return self.get_response(request)

            # Allow client pages (dashboard and schedule)
            if path in ['/client.html', '/client-schedule.html']:
                # For /client.html, require productId=9
                if path == '/client.html':
                    product_id = request.GET.get('productId')
                    if product_id == self.client_required_product_id:
                        if settings.DEBUG:
                            logger.debug(f"[RBAC MIDDLEWARE] Client access ALLOWED to {path}?productId={product_id}")
                        return self.get_response(request)
                    else:
                        logger.warning(f"[RBAC MIDDLEWARE] Client access DENIED to {path} (wrong/missing productId)")
                        return redirect(f'{self.client_allowed_path}?productId={self.client_required_product_id}')
                else:
                    # /client-schedule.html - no productId required
                    if settings.DEBUG:
                        logger.debug(f"[RBAC MIDDLEWARE] Client access ALLOWED to {path}")
                    return self.get_response(request)
            else:
                # Trying to access unauthorized page - redirect to client page
                logger.warning(f"[RBAC MIDDLEWARE] Client access DENIED to {path}, redirecting to client page")
                return redirect(f'{self.client_allowed_path}?productId={self.client_required_product_id}')

        # Office and Admin roles can access everything
        if settings.DEBUG:
            logger.debug(f"[RBAC MIDDLEWARE] {user_role} access ALLOWED to {path}")
        return self.get_response(request)
