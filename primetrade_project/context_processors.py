"""
Template context processors for PrimeTrade.

Provides global template variables across all templates.
"""
import os
from django.conf import settings


def environment_context(request):
    """
    Add environment information to template context.

    Provides:
    - is_staging: True if running in staging environment
    - is_production: True if running in production environment
    - environment_name: Human-readable environment name
    - debug: Whether DEBUG mode is enabled
    """
    environment = os.environ.get('ENVIRONMENT', 'development')

    # Determine if this is staging (any environment that's not production)
    is_production = environment.lower() == 'production'
    is_staging = environment.lower() == 'staging'
    is_development = environment.lower() in ('development', 'dev', 'local')

    # Show staging banner for non-production environments
    show_staging_banner = not is_production

    return {
        'environment': environment,
        'environment_name': environment.title(),
        'is_staging': is_staging,
        'is_production': is_production,
        'is_development': is_development,
        'show_staging_banner': show_staging_banner,
        'debug': settings.DEBUG,
    }


def branding_context(request):
    """
    Add branding information to template context.

    Provides consistent branding variables for headers and footers.
    """
    return {
        'company_name': 'Cincinnati Barge & Rail Terminal',
        'company_short_name': 'CBRT',
        'company_website': 'https://barge2rail.com',
        'brand_name': 'PrimeTrade',
        'current_year': __import__('datetime').datetime.now().year,
    }
