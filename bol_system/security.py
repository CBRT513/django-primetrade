"""
Tenant Security Utilities for PrimeTrade.

Provides shared validation functions for cross-tenant access control.
"""

import logging

security_logger = logging.getLogger('security')


def validate_tenant_access(request, tenant_id):
    """
    Validate that the requesting user has access to the specified tenant.

    Args:
        request: Django request object (must have tenant attribute from TenantMiddleware)
        tenant_id: ID of the tenant being accessed

    Returns:
        Tenant object if access is allowed, None otherwise

    Security:
        - Logs cross-tenant access attempts as warnings
        - Returns None (not 403) to allow graceful handling by calling code
    """
    from bol_system.models import Tenant

    if not tenant_id:
        return None

    try:
        requested_tenant = Tenant.objects.get(id=tenant_id, is_active=True)
    except Tenant.DoesNotExist:
        return None

    # Get user's tenant from middleware
    user_tenant = getattr(request, 'tenant', None)

    # If user has a tenant context, ensure they can only access their own tenant
    if user_tenant and user_tenant.id != requested_tenant.id:
        security_logger.warning(
            f"Cross-tenant access attempt: user_tenant={user_tenant.code} "
            f"tried to access tenant_id={tenant_id} "
            f"user={getattr(request.user, 'email', 'anonymous')} "
            f"path={request.path}"
        )
        return None

    return requested_tenant


def get_tenant_filter(request, field_prefix=''):
    """
    Get a filter dict for queryset filtering by tenant.

    Args:
        request: Django request object
        field_prefix: Prefix for the tenant field (e.g., 'product__' for related lookups)

    Returns:
        Dict to use in .filter() or empty dict if no tenant context

    Example:
        products = Product.objects.filter(**get_tenant_filter(request))
        bols = BOL.objects.filter(**get_tenant_filter(request, 'product__'))
    """
    tenant = getattr(request, 'tenant', None)
    if tenant:
        return {f'{field_prefix}tenant': tenant}
    return {}
