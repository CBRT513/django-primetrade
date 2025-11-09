"""
Middleware for PrimeTrade role-based page access control.
"""
from django.shortcuts import redirect
from django.urls import resolve
import logging

logger = logging.getLogger(__name__)


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce page-level access control based on user role.

    Client users can only access /client.html?productId=9
    Office and Admin users can access all pages
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
            '/media/',
            '/api/',
        ]

        # Client-only allowed path
        self.client_allowed_path = '/client.html'
        self.client_required_product_id = '9'

    def __call__(self, request):
        # Skip check for public paths
        path = request.path
        if any(path.startswith(public_path) for public_path in self.public_paths):
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
