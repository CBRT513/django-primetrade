from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from bol_system import auth_views
from primetrade_project import auth_views as sso_auth_views
from primetrade_project import api_views
from primetrade_project import views as primetrade_views
import os

@ensure_csrf_cookie
def serve_static_html(request, file_name):
    """Serve static HTML files from the static directory with CSRF cookie"""
    file_path = os.path.join(settings.BASE_DIR, 'static', file_name)
    return serve(request, file_name, document_root=os.path.join(settings.BASE_DIR, 'static'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bol_system.urls')),

    # User Context API for RBAC (frontend permission checking)
    path('api/user/context/', api_views.user_context, name='user_context'),

    # SSO Authentication URLs (OAuth) - Primary authentication method
    path('login/', sso_auth_views.login_page, name='login'),  # Redirects to SSO automatically
    path('auth/login/', sso_auth_views.sso_login, name='sso_login'),
    path('auth/callback/', sso_auth_views.sso_callback, name='sso_callback'),
    path('auth/logout/', sso_auth_views.sso_logout, name='sso_logout'),

    # Legacy logout endpoint (preserved for backward compatibility)
    path('logout/', auth_views.logout_view, name='logout'),

    path('', login_required(lambda request: serve_static_html(request, 'index.html')), name='home'),

    # Protected frontend HTML pages
    path('office.html', login_required(lambda request: serve_static_html(request, 'office.html')), name='office'),
    path('client.html', login_required(lambda request: serve_static_html(request, 'client.html')), name='client'),
    path('bol.html', login_required(lambda request: serve_static_html(request, 'bol.html')), name='bol'),
    path('products.html', login_required(lambda request: serve_static_html(request, 'products.html')), name='products'),
    path('customers.html', login_required(lambda request: serve_static_html(request, 'customers.html')), name='customers'),
    path('carriers.html', login_required(lambda request: serve_static_html(request, 'carriers.html')), name='carriers'),
    path('releases.html', login_required(lambda request: serve_static_html(request, 'releases.html')), name='releases'),
    path('open-releases/', login_required(TemplateView.as_view(template_name='open_releases.html')), name='open_releases'),
    path('loading-schedule.html', login_required(TemplateView.as_view(template_name='loading-schedule.html')), name='loading_schedule'),
    path('client-schedule.html', login_required(TemplateView.as_view(template_name='client-schedule.html')), name='client_schedule'),
    path('client-release.html', login_required(TemplateView.as_view(template_name='client-release.html')), name='client_release'),
    path('bol-weights.html', login_required(TemplateView.as_view(template_name='bol-weights.html')), name='bol_weights'),
    path('inventory-report.html', login_required(TemplateView.as_view(template_name='inventory-report.html')), name='inventory_report_page'),

    # Authenticated media access (signed URLs for PDFs)
    path('media/<path:path>', primetrade_views.secure_media_download, name='secure_media'),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
