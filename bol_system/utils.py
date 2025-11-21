"""
Utility functions for PrimeTrade BOL system.

SECURITY: Customer association for Client role users.
"""

import logging
from django.contrib.auth import get_user_model
from .models import Customer

logger = logging.getLogger('primetrade.security')
User = get_user_model()


def get_customer_for_user(user):
    """
    Get the Customer instance associated with a user.

    For Client role users, this determines which customer's data they can see.
    For Admin/Office users, returns None (they see all data regardless).

    Current implementation: Match by email domain to customer name.
    If user has email lbryant@primetradeusa.com, tries to find customer
    with name containing "primetradeusa" or "primetrade".

    Security:
    - Returns None for unmatched users (secure default - no data access)
    - Logs association attempts for audit trail
    - Case-insensitive matching

    Future enhancement: If User model gets customer foreign key, use that instead.

    Args:
        user: Django User instance

    Returns:
        Customer instance or None

    Examples:
        >>> user = User.objects.get(email='lbryant@primetradeusa.com')
        >>> customer = get_customer_for_user(user)
        >>> # Returns Customer with name containing "primetrade"

        >>> office_user = User.objects.get(email='staff@barge2rail.com')
        >>> customer = get_customer_for_user(office_user)
        >>> # Returns None (office users see all data)
    """
    if not user or not user.is_authenticated:
        return None

    # Check if user has direct customer link (future enhancement)
    if hasattr(user, 'customer') and user.customer:
        logger.info(f"Customer association via user.customer: {user.email} -> {user.customer}")
        return user.customer

    # Extract email domain
    email = user.email
    if not email or '@' not in email:
        logger.warning(f"Invalid email format for user: {email}")
        return None

    email_domain = email.split('@')[1].lower()
    email_local = email.split('@')[0].lower()

    # Extract company name from domain (remove .com, .net, etc.)
    domain_name = email_domain.split('.')[0]  # primetradeusa.com -> primetradeusa

    # Try to find customer by matching domain to customer name
    # Strategy 1: Exact match (case-insensitive)
    customers = Customer.objects.filter(customer__iexact=domain_name)
    if customers.exists():
        customer = customers.first()
        logger.info(f"Customer association (exact): {email} -> {customer.customer}")
        return customer

    # Strategy 2: Partial match (domain contained in customer name)
    customers = Customer.objects.filter(customer__icontains=domain_name)
    if customers.exists():
        customer = customers.first()
        logger.info(f"Customer association (partial): {email} -> {customer.customer}")
        return customer

    # Strategy 3: Try matching parts of domain
    # Example: primetradeusa -> look for "primetrade" or "prime"
    if len(domain_name) > 5:
        # Try first significant part
        domain_parts = [domain_name[:len(domain_name)//2], domain_name]
        for part in domain_parts:
            if len(part) < 4:  # Skip very short matches
                continue
            customers = Customer.objects.filter(customer__icontains=part)
            if customers.exists():
                customer = customers.first()
                logger.info(f"Customer association (partial match): {email} -> {customer.customer}")
                return customer

    # No match found - secure default
    logger.warning(
        f"No customer association found for {email}. "
        f"Domain: {email_domain}, searched for: {domain_name}. "
        f"User will have no data access."
    )
    return None


def get_role_from_session(request):
    """
    Extract role name from session.

    Helper function to safely get role from session with fallback.

    Args:
        request: Django request object

    Returns:
        str: Role name ('admin', 'office', 'client', or 'unknown')
    """
    role_info = request.session.get('primetrade_role', {})
    role = role_info.get('role', 'unknown')
    return role.lower() if role else 'unknown'


def is_internal_staff(request):
    """
    Check if user is internal staff (Admin or Office role).

    Internal staff can see all data.
    Client users are external customers with filtered data access.

    Args:
        request: Django request object

    Returns:
        bool: True if Admin or Office, False if Client or unknown
    """
    role = get_role_from_session(request)
    return role in ['admin', 'office']
