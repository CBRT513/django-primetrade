from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import HttpResponse
from bol_system import auth_views
from primetrade_project import auth_views as sso_auth_views
from primetrade_project import api_views
from primetrade_project import views as primetrade_views
import os


def robots_txt(request):
    content = """User-agent: *
Allow: /
Disallow: /cbrt-ops/
Disallow: /api/
Disallow: /auth/
Disallow: /tenant/
"""
    return HttpResponse(content, content_type="text/plain")

@ensure_csrf_cookie
def serve_static_html(request, file_name):
    """Serve static HTML files from the static directory with CSRF cookie"""
    file_path = os.path.join(settings.BASE_DIR, 'static', file_name)
    return serve(request, file_name, document_root=os.path.join(settings.BASE_DIR, 'static'))

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('cbrt-ops/', admin.site.urls),
    path('api/', include('bol_system.urls')),
    path('kiosk/', include('kiosk.urls')),

    # Tenant-scoped pigiron workflow (spec section 10)
    # Pattern: /tenant/{tenant_code}/pigiron/...
    path('tenant/<str:tenant_code>/pigiron/', include('bol_system.pigiron_urls')),

    # User Context API for RBAC (frontend permission checking)
    path('api/user/context/', api_views.user_context, name='user_context'),

    # Cross-application API for Sacks Command Center
    path('api/open-releases/', api_views.open_releases, name='open_releases_api'),

    # SSO Authentication URLs (OAuth) - Primary authentication method
    path('login/', sso_auth_views.login_page, name='login'),  # Redirects to SSO automatically
    path('auth/login/', sso_auth_views.sso_login, name='sso_login'),
    path('auth/callback/', sso_auth_views.sso_callback, name='sso_callback'),
    path('auth/logout/', sso_auth_views.sso_logout, name='sso_logout'),

    # Legacy logout endpoint (preserved for backward compatibility)
    path('logout/', auth_views.logout_view, name='logout'),

    # Dashboard with RBAC enforcement - requires 'dashboard:view' permission
    path('', primetrade_views.dashboard, name='home'),

    # Protected frontend HTML pages with RBAC
    path('office.html', primetrade_views.office_page, name='office'),
    path('client.html', primetrade_views.client_page, name='client'),
    path('bol.html', primetrade_views.bol_page, name='bol'),
    path('products.html', primetrade_views.products_page, name='products'),
    path('customers.html', primetrade_views.customers_page, name='customers'),
    path('carriers.html', primetrade_views.carriers_page, name='carriers'),
    path('releases.html', primetrade_views.releases_upload_page, name='releases'),
    path('open-releases/', primetrade_views.open_releases_page, name='open_releases'),
    path('loading-schedule/', primetrade_views.loading_schedule_page, name='loading_schedule'),
    path('loading-schedule.html', primetrade_views.loading_schedule_page),  # Legacy URL
    path('client-schedule.html', primetrade_views.client_schedule_page, name='client_schedule'),
    path('client-release.html', primetrade_views.client_release_page, name='client_release'),
    path('bol-weights.html', primetrade_views.bol_weights_page, name='bol_weights'),
    path('inventory-report.html', primetrade_views.inventory_report_page, name='inventory_report_page'),

    # Authenticated media access (signed URLs for PDFs)
    path('media/<path:path>', primetrade_views.secure_media_download, name='secure_media'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
