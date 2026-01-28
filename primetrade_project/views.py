import os
from datetime import timedelta

from django.http import Http404, HttpResponseRedirect, FileResponse
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.views.static import serve
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone

from primetrade_project.decorators import require_role
from bol_system.permissions import feature_permission_required
from bol_system.models import BOL, Release, ReleaseLoad, Customer


@login_required
@feature_permission_required('dashboard', 'view')
@ensure_csrf_cookie
def dashboard(request):
    """
    Staff dashboard with operational overview.

    Requires 'dashboard:view' permission from SSO RBAC.
    Shows BOLs, releases, schedule, and customers.
    """
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday

    # Summary stats
    total_bols = BOL.objects.count()
    pending_releases = Release.objects.filter(status='OPEN').count()
    week_bols = BOL.objects.filter(
        created_at__date__gte=week_start,
        created_at__date__lte=week_end
    ).count()
    total_customers = Customer.objects.filter(is_active=True).count()

    # Upcoming schedule (release loads with dates in next 7 days)
    upcoming_schedule = ReleaseLoad.objects.select_related(
        'release', 'release__customer_ref', 'release__carrier_ref'
    ).filter(
        date__gte=today,
        date__lte=today + timedelta(days=7),
        status='PENDING'
    ).order_by('date', 'seq')[:10]

    # Recent BOLs
    recent_bols = BOL.objects.select_related(
        'customer', 'carrier', 'product'
    ).order_by('-created_at')[:5]

    # Recent releases
    recent_releases = Release.objects.select_related(
        'customer_ref', 'carrier_ref'
    ).order_by('-created_at')[:5]

    context = {
        'total_bols': total_bols,
        'pending_releases': pending_releases,
        'week_bols': week_bols,
        'total_customers': total_customers,
        'upcoming_schedule': upcoming_schedule,
        'recent_bols': recent_bols,
        'recent_releases': recent_releases,
    }

    return render(request, 'staff_dashboard.html', context)


# =============================================================================
# Frontend Page Views with RBAC
# =============================================================================

def _serve_static(request, filename):
    """Helper to serve static HTML files."""
    return serve(request, filename, document_root=os.path.join(settings.BASE_DIR, 'static'))


@login_required
@feature_permission_required('bol', 'create')
@ensure_csrf_cookie
def office_page(request):
    """Office page - BOL creation interface."""
    return _serve_static(request, 'office.html')


@login_required
@feature_permission_required('bol', 'view')
@ensure_csrf_cookie
def bol_page(request):
    """BOL page - view BOLs."""
    return _serve_static(request, 'bol.html')


@login_required
@feature_permission_required('bol', 'modify')
@ensure_csrf_cookie
def bol_weights_page(request):
    """BOL weights page - set official weights."""
    return serve(request, 'bol-weights.html', document_root=settings.BASE_DIR / 'templates')


@login_required
@feature_permission_required('bol', 'view')
@ensure_csrf_cookie
def bol_list_page(request):
    """BOL list page - view all BOLs with search and pagination."""
    return serve(request, 'bol-list.html', document_root=settings.BASE_DIR / 'templates')


@login_required
@feature_permission_required('products', 'view')
@ensure_csrf_cookie
def products_page(request):
    """Products catalog page."""
    return _serve_static(request, 'products.html')


@login_required
@feature_permission_required('customers', 'view')
@ensure_csrf_cookie
def customers_page(request):
    """Customer database page."""
    return _serve_static(request, 'customers.html')


@login_required
@feature_permission_required('carriers', 'view')
@ensure_csrf_cookie
def carriers_page(request):
    """Carrier management page."""
    return _serve_static(request, 'carriers.html')


@login_required
@feature_permission_required('releases', 'create')
@ensure_csrf_cookie
def releases_upload_page(request):
    """Release upload page - parse PDFs to create releases."""
    return _serve_static(request, 'releases.html')


@login_required
@feature_permission_required('releases', 'view')
@ensure_csrf_cookie
def open_releases_page(request):
    """Open releases list - view releases ready for BOL creation."""
    return serve(request, 'releases.html', document_root=settings.BASE_DIR / 'templates')


@login_required
@feature_permission_required('schedule', 'view')
@ensure_csrf_cookie
def loading_schedule_page(request):
    """Loading schedule page."""
    return serve(request, 'loading-schedule.html', document_root=settings.BASE_DIR / 'templates')


@login_required
@feature_permission_required('reports', 'view')
@ensure_csrf_cookie
def inventory_report_page(request):
    """Inventory report page."""
    return serve(request, 'inventory-report.html', document_root=settings.BASE_DIR / 'templates')


@login_required
@feature_permission_required('client_portal', 'view')
@ensure_csrf_cookie
def client_page(request):
    """Client portal page."""
    return _serve_static(request, 'client.html')


@login_required
@feature_permission_required('client_portal', 'view')
@ensure_csrf_cookie
def client_schedule_page(request):
    """Client schedule page."""
    return serve(request, 'client-schedule.html', document_root=settings.BASE_DIR / 'templates')


@login_required
@feature_permission_required('client_portal', 'view')
@ensure_csrf_cookie
def client_release_page(request):
    """Client release page."""
    return serve(request, 'client-release.html', document_root=settings.BASE_DIR / 'templates')


# =============================================================================
# Media Access
# =============================================================================

@login_required
@require_role('Admin', 'Office', 'Client')
def secure_media_download(request, path):
    """
    Generate signed S3 URL for authenticated users.

    Phase 1: Any authenticated role can download (single-tenant)
    Phase 2: Add tenant filtering to restrict cross-tenant access
    """
    # TODO Phase 2: Add tenant filtering using request.tenant_id

    # Verify file exists in storage
    if not default_storage.exists(path):
        raise Http404("File not found")

    # If using local filesystem storage, stream the file directly to avoid redirect loops
    if not hasattr(default_storage, 'bucket'):
        local_path = default_storage.path(path)
        if not os.path.exists(local_path):
            raise Http404("File not found")
        return FileResponse(open(local_path, 'rb'))

    # Generate signed URL (24-hour expiry via AWS_QUERYSTRING_EXPIRE)
    signed_url = default_storage.url(path)
    return HttpResponseRedirect(signed_url)
