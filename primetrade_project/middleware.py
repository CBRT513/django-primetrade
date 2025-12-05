"""
Middleware for PrimeTrade role-based PAGE access control and tenant context.

Security Notes (Phase 2 - Nov 2025):
- Middleware controls PAGE access (HTML pages), NOT API access
- Client users can access /api/* endpoints (decorators enforce permissions)
- Client users restricted to /client.html?productId=9 for pages
- Admin/Office users can access all pages
- API access control is enforced by @require_role decorators on each endpoint

Tenant Architecture (Dec 2025):
- TenantMiddleware sets request.tenant from session or JWT claims
- All views filter by request.tenant for data isolation
- Cross-tenant access attempts are logged as security warnings
"""
from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve
import logging

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce page-level access control based on user role.

    Client users:
    - Can access /api/* endpoints (permission checked by decorators)
    - Can access /client.html (dashboard) - data isolation handled by tenant filtering
    - Can access /client-schedule.html (loading schedule)
    - Can access /client-release.html (release details)

    Office and Admin users:
    - Can access all pages and API endpoints

    Multi-Tenant Security (Dec 2025):
    - Removed hardcoded productId=9 restriction
    - Data isolation now handled by TenantMiddleware + API tenant filtering
    - Client sees only their tenant's data via API endpoints
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

        # Client-allowed pages (data isolation handled by tenant filtering)
        self.client_allowed_pages = ['/client.html', '/client-schedule.html', '/client-release.html']

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
                return redirect('/client.html')

            # Allow API access - decorators handle permission checking
            # Data isolation handled by tenant filtering at API level
            if path.startswith('/api/'):
                if settings.DEBUG:
                    logger.debug(f"[RBAC MIDDLEWARE] Client API access - checked by @require_role decorator: {path}")
                return self.get_response(request)

            # Allow client pages - data isolation handled by tenant filtering
            if path in self.client_allowed_pages:
                if settings.DEBUG:
                    logger.debug(f"[RBAC MIDDLEWARE] Client access ALLOWED to {path}")
                return self.get_response(request)
            else:
                # Trying to access unauthorized page - redirect to client dashboard
                logger.warning(f"[RBAC MIDDLEWARE] Client access DENIED to {path}, redirecting to client dashboard")
                return redirect('/client.html')

        # Office and Admin roles can access everything
        if settings.DEBUG:
            logger.debug(f"[RBAC MIDDLEWARE] {user_role} access ALLOWED to {path}")
        return self.get_response(request)


class TenantMiddleware:
    """
    Middleware to inject tenant context into every request.

    Sets request.tenant based on:
    1. Session data (tenant_code from SSO)
    2. JWT claims (tenant_code claim)

    All views should filter queries by request.tenant to ensure data isolation.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._tenant_cache = {}

    def __call__(self, request):
        request.tenant = None

        # Try to get tenant from session first (set during SSO login)
        tenant_code = request.session.get('tenant_code')

        # Fallback: check JWT claims if present
        if not tenant_code and hasattr(request, 'auth') and request.auth:
            tenant_code = getattr(request.auth, 'tenant_code', None)

        # Look up tenant by code
        if tenant_code:
            request.tenant = self._get_tenant_by_code(tenant_code)
            if request.tenant:
                logger.debug(f"[TenantMiddleware] Set tenant: {request.tenant.name}")
            else:
                security_logger.warning(
                    f"[TenantMiddleware] Unknown tenant_code '{tenant_code}' "
                    f"for user {getattr(request.user, 'email', 'anonymous')}"
                )

        return self.get_response(request)

    def _get_tenant_by_code(self, code):
        """Get tenant by code with caching."""
        if code not in self._tenant_cache:
            from bol_system.models import Tenant
            try:
                self._tenant_cache[code] = Tenant.objects.get(code=code, is_active=True)
            except Tenant.DoesNotExist:
                self._tenant_cache[code] = None
        return self._tenant_cache[code]
