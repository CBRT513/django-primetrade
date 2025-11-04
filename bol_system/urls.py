from django.urls import path
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from . import views
from . import auth_views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('customers/', views.customer_list, name='customers'),
    path('customers/<int:customer_id>/shiptos/', views.customer_shiptos, name='customer_shiptos'),
    path('customers/branding/', views.customer_branding, name='customer_branding'),
    path('carriers/', views.carrier_list, name='carriers'),
    path('bol/preview/', views.preview_bol, name='preview_bol'),
    path('bol/confirm/', views.confirm_bol, name='confirm_bol'),
    path('releases/pending-loads/', views.pending_release_loads, name='pending_release_loads'),
    path('releases/load/<int:load_id>/', views.load_detail_api, name='load_detail_api'),
    path('bol/', views.confirm_bol, name='create_bol'),  # Backward compatibility
    path('bol/<int:bol_id>/', views.bol_detail, name='bol_detail'),
    path('bol/<int:bol_id>/set-official-weight/', views.set_official_weight, name='set_official_weight'),
    path('balances/', views.balances, name='balances'),
    path('history/', views.bol_history, name='history'),
    path('audit/', views.audit_logs, name='audit_logs'),

    # Release parsing + approvals
    path('releases/upload/', views.upload_release, name='release_upload'),
    path('releases/approve/', views.approve_release, name='release_approve'),
    path('releases/open/', views.open_releases, name='releases_open'),
    path('releases/open/view/', login_required(TemplateView.as_view(template_name='open_releases.html')), name='releases_open_view'),
    path('releases/<int:release_id>/', views.release_detail_api, name='release_detail_api'),
    path('releases/<int:release_id>/view/', login_required(TemplateView.as_view(template_name='release_detail.html')), name='release_detail_view'),

    path('auth/me/', auth_views.current_user, name='current_user'),
]
