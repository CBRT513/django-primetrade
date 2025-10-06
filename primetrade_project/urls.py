from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.static import serve
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from bol_system import auth_views
import os

@ensure_csrf_cookie
def serve_static_html(request, file_name):
    """Serve static HTML files from the static directory with CSRF cookie"""
    file_path = os.path.join(settings.BASE_DIR, 'static', file_name)
    return serve(request, file_name, document_root=os.path.join(settings.BASE_DIR, 'static'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bol_system.urls')),

    # Authentication URLs
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('', login_required(lambda request: serve_static_html(request, 'index.html')), name='index'),

    # Protected frontend HTML pages
    path('office.html', login_required(lambda request: serve_static_html(request, 'office.html')), name='office'),
    path('client.html', login_required(lambda request: serve_static_html(request, 'client.html')), name='client'),
    path('bol.html', login_required(lambda request: serve_static_html(request, 'bol.html')), name='bol'),
    path('products.html', login_required(lambda request: serve_static_html(request, 'products.html')), name='products'),
    path('customers.html', login_required(lambda request: serve_static_html(request, 'customers.html')), name='customers'),
    path('carriers.html', login_required(lambda request: serve_static_html(request, 'carriers.html')), name='carriers'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')