from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.static import serve
import os

def serve_static_html(request, file_name):
    """Serve static HTML files from the static directory"""
    file_path = os.path.join(settings.BASE_DIR, 'static', file_name)
    return serve(request, file_name, document_root=os.path.join(settings.BASE_DIR, 'static'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bol_system.urls')),

    # Frontend HTML pages
    path('', serve_static_html, {'file_name': 'index.html'}, name='index'),
    path('office.html', serve_static_html, {'file_name': 'office.html'}, name='office'),
    path('client.html', serve_static_html, {'file_name': 'client.html'}, name='client'),
    path('bol.html', serve_static_html, {'file_name': 'bol.html'}, name='bol'),
    path('products.html', serve_static_html, {'file_name': 'products.html'}, name='products'),
    path('customers.html', serve_static_html, {'file_name': 'customers.html'}, name='customers'),
    path('carriers.html', serve_static_html, {'file_name': 'carriers.html'}, name='carriers'),
    path('login.html', serve_static_html, {'file_name': 'login.html'}, name='login'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')