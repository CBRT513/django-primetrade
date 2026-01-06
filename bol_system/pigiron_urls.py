"""
Pig Iron workflow URL patterns.

URL pattern: /tenant/{tenant_code}/pigiron/...

These URLs implement the PrimeTrade pig iron workflow per spec section 10.
"""
from django.urls import path
from . import pigiron_views

app_name = 'pigiron'

urlpatterns = [
    # Release management
    path('releases/', pigiron_views.release_list, name='release_list'),
    path('releases/upload/', pigiron_views.upload_release, name='upload_release'),
    path('releases/approve/', pigiron_views.approve_release, name='approve_release'),
    path('releases/<int:release_id>/', pigiron_views.release_detail, name='release_detail'),

    # Pending loads (all PENDING across all releases)
    path('pending-loads/', pigiron_views.pending_loads, name='pending_loads'),

    # BOL management
    path('bol/create/', pigiron_views.create_bol, name='create_bol'),
    path('bol/<int:bol_id>/', pigiron_views.bol_detail, name='bol_detail'),
    path('bol/<int:bol_id>/pdf/', pigiron_views.bol_pdf, name='bol_pdf'),
    path('bol/<int:bol_id>/void/', pigiron_views.void_bol, name='void_bol'),
    path('bol/<int:bol_id>/official-weight/', pigiron_views.set_official_weight, name='set_official_weight'),

    # Inventory and reference data
    path('inventory/', pigiron_views.inventory_report, name='inventory_report'),
    path('products/', pigiron_views.product_list, name='product_list'),
    path('lots/', pigiron_views.lot_list, name='lot_list'),
]
