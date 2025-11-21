"""
Middleware for PrimeTrade role-based PAGE access control.

Security Notes (Phase 2 - Nov 2025):
- Middleware controls PAGE access (HTML pages), NOT API access
- Client users can access /api/* endpoints (decorators enforce permissions)
- Client users restricted to /client.html?productId=9 for pages
- Admin/Office users can access all pages
- API access control is enforced by @require_role decorators on each endpoint
"""
from django.shortcuts import redirect
from django.urls import resolve
import logging

logger = logging.getLogger(__name__)


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce page-level access control based on user role.

    Client users:
    - Can access /api/* endpoints (permission checked by decorators)
    - Can only access /client.html?productId=9 page

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
            '/media/',  # TODO Phase 3: Secure media/PDF access
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

        # Get user role from session
        role_info = request.session.get('primetrade_role', {})
        user_role = role_info.get('role', 'viewer')

        logger.info(f"[RBAC MIDDLEWARE] User: {request.user.email}, Role: {user_role}, Path: {path}")

        # Client role restrictions
        if user_role == 'Client':
            # Allow API access - decorators handle permission checking
            if path.startswith('/api/'):
                logger.info(f"[RBAC MIDDLEWARE] Client API access - will be checked by @require_role decorator: {path}")
                return self.get_response(request)

            # Check if accessing the allowed client page with correct product ID
            if path == self.client_allowed_path:
                product_id = request.GET.get('productId')
                if product_id == self.client_required_product_id:
                    # Allowed access
                    logger.info(f"[RBAC MIDDLEWARE] Client access ALLOWED to {path}?productId={product_id}")
                    return self.get_response(request)
                else:
                    # Wrong or missing product ID - redirect to correct page
                    logger.warning(f"[RBAC MIDDLEWARE] Client access DENIED to {path} (wrong/missing productId)")
                    return redirect(f'{self.client_allowed_path}?productId={self.client_required_product_id}')
            else:
                # Trying to access unauthorized page - redirect to client page
                logger.warning(f"[RBAC MIDDLEWARE] Client access DENIED to {path}, redirecting to client page")
                return redirect(f'{self.client_allowed_path}?productId={self.client_required_product_id}')

        # Office and Admin roles can access everything
        logger.info(f"[RBAC MIDDLEWARE] {user_role} access ALLOWED to {path}")
        return self.get_response(request)
