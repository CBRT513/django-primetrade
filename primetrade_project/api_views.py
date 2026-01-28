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
from datetime import date, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import models
from primetrade_project.decorators import require_role
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('oauth.security')


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


def _verify_bearer_jwt(request):
    """
    Verify JWT Bearer token from Authorization header.

    For cross-app API calls (e.g., Sacks Command Center), the token may have
    been issued for a different app's client_id. We skip audience verification
    but still verify signature, issuer, and expiration.

    Returns:
        tuple: (decoded_claims, error_response)
        - If valid: (claims_dict, None)
        - If invalid: (None, JsonResponse with error)
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None, JsonResponse(
            {'error': 'Missing or invalid Authorization header'},
            status=401
        )

    token = auth_header[7:]  # Strip 'Bearer '

    try:
        # Fetch JWKS from SSO and verify JWT signature
        jwks_url = f"{settings.SSO_BASE_URL}/api/auth/.well-known/jwks.json"
        jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and verify JWT - skip audience check for cross-app tokens
        # Security: signature, issuer, and expiration are still verified
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=f"{settings.SSO_BASE_URL}/o",
            options={
                "verify_signature": True,
                "verify_aud": False,  # Skip - token may be for different app
                "verify_iss": True,
                "verify_exp": True,
            }
        )
        return decoded, None

    except jwt.InvalidSignatureError:
        security_logger.warning("JWT Bearer token signature verification failed")
        return None, JsonResponse(
            {'error': 'Invalid token signature'},
            status=401
        )
    except jwt.ExpiredSignatureError:
        return None, JsonResponse(
            {'error': 'Token expired'},
            status=401
        )
    except jwt.InvalidIssuerError:
        security_logger.warning("JWT Bearer token issuer mismatch")
        return None, JsonResponse(
            {'error': 'Invalid token issuer'},
            status=401
        )
    except Exception as e:
        security_logger.error(f"JWT Bearer token verification error: {e}")
        return None, JsonResponse(
            {'error': 'Token verification failed'},
            status=401
        )


@csrf_exempt
@require_http_methods(["GET"])
def open_releases(request):
    """
    Open Releases API for Sacks Command Center integration.

    Returns open releases grouped by tenant for cross-application dashboard.

    Authentication:
        Bearer JWT token in Authorization header (from SSO)
        Requires Admin or Office role in primetrade application_roles

    Query Parameters:
        days (int): Filter releases created in last N days (default: 30)

    Response:
        {
            "tenants": [
                {
                    "tenant_code": "PRT",
                    "tenant_name": "PrimeTrade",
                    "dashboard_url": "https://prt.barge2rail.com/",
                    "releases": [
                        {
                            "id": 123,
                            "release_number": "PO-12345",
                            "customer": "St. Marys",
                            "ship_to_name": "Plant 1",
                            "next_scheduled_date": "2026-01-29",
                            "loads_pending": 3,
                            "loads_shipped": 2,
                            "total_tons": 150.0,
                            "tons_remaining": 90.0,
                            "release_url": "/api/releases/123/"
                        }
                    ]
                }
            ]
        }
    """
    # Verify JWT Bearer token
    claims, error_response = _verify_bearer_jwt(request)
    if error_response:
        return error_response

    # Check for Admin or Office role in ANY barge2rail app
    # Cross-app API calls (e.g., from Sacks Command Center) may have roles
    # in a different app than primetrade
    application_roles = claims.get('application_roles', {})
    has_access = False
    user_role = None

    for app_name, app_role in application_roles.items():
        role = app_role.get('role', '').lower() if isinstance(app_role, dict) else ''
        if role in ('admin', 'office'):
            has_access = True
            user_role = f"{app_name}:{role}"
            break

    if not has_access:
        logger.warning(f"[OPEN_RELEASES] Access denied - no Admin/Office role in any app")
        return JsonResponse(
            {'error': 'Access denied. Requires Admin or Office role.'},
            status=403
        )

    logger.info(f"[OPEN_RELEASES] Access granted via {user_role}")

    # Get query parameters
    try:
        days = int(request.GET.get('days', 30))
        days = max(1, min(days, 365))  # Clamp to 1-365
    except ValueError:
        days = 30

    # Calculate date filter
    cutoff_date = date.today() - timedelta(days=days)

    # Import models here to avoid circular imports
    from bol_system.models import Release, Tenant

    # Get all active tenants
    tenants = Tenant.objects.filter(is_active=True).order_by('name')

    result = {"tenants": []}

    for tenant in tenants:
        # Get open releases for this tenant
        releases = Release.objects.filter(
            tenant=tenant,
            status='OPEN',
            created_at__date__gte=cutoff_date
        ).select_related('customer_ref').prefetch_related('loads').order_by('-created_at')

        if not releases.exists():
            continue

        tenant_releases = []
        for release in releases:
            # Calculate load stats
            loads = release.loads.all()
            loads_pending = loads.filter(status='PENDING').count()
            loads_shipped = loads.filter(status='SHIPPED').count()

            # Calculate tonnage
            total_tons = float(release.quantity_net_tons or 0)

            # Shipped tons: official weight if available, otherwise planned
            shipped_loads = loads.filter(status='SHIPPED')
            tons_official = float(shipped_loads.filter(
                bol__official_weight_tons__isnull=False
            ).aggregate(sum=models.Sum('bol__official_weight_tons'))['sum'] or 0)
            tons_planned = float(shipped_loads.filter(
                bol__official_weight_tons__isnull=True
            ).aggregate(sum=models.Sum('planned_tons'))['sum'] or 0)
            tons_shipped = tons_official + tons_planned
            tons_remaining = max(0.0, total_tons - tons_shipped)

            # Next scheduled date from pending loads
            next_load = loads.filter(status='PENDING').order_by('date').first()
            next_scheduled_date = None
            if next_load and next_load.date:
                next_scheduled_date = (
                    next_load.date.isoformat()
                    if hasattr(next_load.date, 'isoformat')
                    else str(next_load.date)
                )

            tenant_releases.append({
                'id': release.id,
                'release_number': release.release_number,
                'customer': release.customer_id_text,
                'ship_to_name': release.ship_to_name or '',
                'next_scheduled_date': next_scheduled_date,
                'loads_pending': loads_pending,
                'loads_shipped': loads_shipped,
                'total_tons': total_tons,
                'tons_remaining': tons_remaining,
                'release_url': f"/releases/{release.id}/view/",
            })

        # Build dashboard URL based on settings
        base_url = getattr(settings, 'PRIMETRADE_BASE_URL', 'https://prt.barge2rail.com')

        result["tenants"].append({
            'tenant_code': tenant.code,
            'tenant_name': tenant.name,
            'dashboard_url': f"{base_url}/",
            'releases': tenant_releases,
        })

    logger.info(f"[OPEN_RELEASES] Returned {sum(len(t['releases']) for t in result['tenants'])} releases across {len(result['tenants'])} tenants")
    return JsonResponse(result)
